"""
HackRF Spectrum Analyzer UI
Main window with spectrum display and control panel.
"""

import sys
import os
import numpy as np
from scipy.interpolate import interp1d
from collections import deque
from PyQt5.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
                             QSplitter, QGroupBox, QFormLayout, QSpinBox, 
                             QDoubleSpinBox, QComboBox, QCheckBox, QLineEdit, 
                             QPushButton, QLabel, QFileDialog, QMessageBox,
                             QStatusBar, QFrame, QTextEdit, QScrollArea)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor

import pyqtgraph as pg

from hackrf_interface import HackRFInterface, HackRFSweepConfig

import time


class ControlPanel(QScrollArea):
    """Control panel widget with all HackRF sweep parameters."""
    
    config_changed = pyqtSignal(HackRFSweepConfig)
    
    def __init__(self):
        super().__init__()
        self.config = HackRFSweepConfig()
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the control panel UI."""
        self.setWidgetResizable(True)
        self.setMinimumWidth(300)
        self.setMaximumWidth(400)
        
        # Main widget and layout
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(10)
        
        # Device Configuration
        device_group = self.create_device_group()
        layout.addWidget(device_group)
        
        # Frequency Configuration
        freq_group = self.create_frequency_group()
        layout.addWidget(freq_group)
        
        # Gain Configuration
        gain_group = self.create_gain_group()
        layout.addWidget(gain_group)
        
        # FFT Configuration
        fft_group = self.create_fft_group()
        layout.addWidget(fft_group)
        
        # Sweep Configuration
        sweep_group = self.create_sweep_group()
        layout.addWidget(sweep_group)
        
        # Output Configuration
        output_group = self.create_output_group()
        layout.addWidget(output_group)
        
        # Control Buttons
        button_group = self.create_button_group()
        layout.addWidget(button_group)
        
        layout.addStretch()
        self.setWidget(main_widget)
    
    def create_device_group(self):
        """Create device configuration group."""
        group = QGroupBox("Device Configuration")
        layout = QFormLayout()
        
        self.serial_edit = QLineEdit()
        self.serial_edit.setPlaceholderText("Auto-detect")
        layout.addRow("Serial Number:", self.serial_edit)
        
        self.amp_check = QCheckBox()
        layout.addRow("RF Amplifier:", self.amp_check)
        
        self.antenna_check = QCheckBox()
        layout.addRow("Antenna Power:", self.antenna_check)
        
        group.setLayout(layout)
        return group
    
    def create_frequency_group(self):
        """Create frequency configuration group."""
        group = QGroupBox("Frequency Configuration")
        layout = QFormLayout()
        
        self.freq_min_spin = QDoubleSpinBox()
        self.freq_min_spin.setRange(0, 6000)
        self.freq_min_spin.setValue(0)
        self.freq_min_spin.setSuffix(" MHz")
        self.freq_min_spin.setDecimals(3)
        self.freq_min_spin.valueChanged.connect(self.apply_config)
        layout.addRow("Min Frequency:", self.freq_min_spin)
        
        self.freq_max_spin = QDoubleSpinBox()
        self.freq_max_spin.setRange(0, 6000)
        self.freq_max_spin.setValue(6000)
        self.freq_max_spin.setSuffix(" MHz")
        self.freq_max_spin.setDecimals(3)
        self.freq_max_spin.valueChanged.connect(self.apply_config)
        layout.addRow("Max Frequency:", self.freq_max_spin)
        
        group.setLayout(layout)
        return group
    
    def create_gain_group(self):
        """Create gain configuration group."""
        group = QGroupBox("Gain Configuration")
        layout = QFormLayout()
        
        self.lna_gain_spin = QSpinBox()
        self.lna_gain_spin.setRange(0, 40)
        self.lna_gain_spin.setValue(16)
        self.lna_gain_spin.setSingleStep(8)
        self.lna_gain_spin.setSuffix(" dB")
        layout.addRow("LNA (IF) Gain:", self.lna_gain_spin)
        
        self.vga_gain_spin = QSpinBox()
        self.vga_gain_spin.setRange(0, 62)
        self.vga_gain_spin.setValue(20)
        self.vga_gain_spin.setSingleStep(2)
        self.vga_gain_spin.setSuffix(" dB")
        layout.addRow("VGA (BB) Gain:", self.vga_gain_spin)
        
        group.setLayout(layout)
        return group
    
    def create_fft_group(self):
        """Create FFT configuration group."""
        group = QGroupBox("🔧 FFT Configuration - High Resolution (100 kHz)")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #4CAF50;
                font-size: 14px;
            }
        """)
        layout = QVBoxLayout()
        
        # Main bin width control with enhanced labeling
        bin_layout = QFormLayout()
        
        # Create a prominent label with explanation
        bin_label = QLabel("FFT Bin Width (High Resolution Mode):")
        bin_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        bin_label.setToolTip("High frequency resolution mode optimized for detailed analysis")
        
        self.bin_width_spin = QSpinBox()
        self.bin_width_spin.setRange(50000, 200000)  # Limit range around 100kHz
        self.bin_width_spin.setValue(100000)  # Default to 100kHz
        self.bin_width_spin.setSuffix(" Hz")
        self.bin_width_spin.setStyleSheet("""
            QSpinBox {
                font-weight: bold;
                font-size: 12px;
                padding: 4px;
                border: 2px solid #2196F3;
                border-radius: 4px;
            }
        """)
        self.bin_width_spin.setToolTip("FFT bin width optimized for high resolution analysis (50-200 kHz range)")
        
        bin_layout.addRow(bin_label, self.bin_width_spin)
        layout.addLayout(bin_layout)
        
        # Add separator
        separator = QFrame()
        separator.setFrameStyle(QFrame.HLine | QFrame.Sunken)
        separator.setStyleSheet("margin: 10px 0px;")
        layout.addWidget(separator)
        
        # Advanced FFT options
        advanced_layout = QFormLayout()
        
        self.fftw_plan_combo = QComboBox()
        self.fftw_plan_combo.addItems(["estimate", "measure", "patient", "exhaustive"])
        self.fftw_plan_combo.setCurrentText("measure")
        self.fftw_plan_combo.setToolTip("FFTW planning strategy - 'measure' is usually best")
        advanced_layout.addRow("FFTW Plan:", self.fftw_plan_combo)
        
        self.wisdom_edit = QLineEdit()
        self.wisdom_edit.setPlaceholderText("Optional wisdom file path")
        self.wisdom_edit.setToolTip("Optional FFTW wisdom file for optimization")
        advanced_layout.addRow("Wisdom File:", self.wisdom_edit)
        
        wisdom_button = QPushButton("Browse...")
        wisdom_button.clicked.connect(self.browse_wisdom_file)
        advanced_layout.addRow("", wisdom_button)
        
        layout.addLayout(advanced_layout)
        
        group.setLayout(layout)
        return group
    
    def create_sweep_group(self):
        """Create sweep configuration group."""
        group = QGroupBox("Sweep Configuration")
        layout = QFormLayout()
        
        self.one_shot_check = QCheckBox()
        layout.addRow("One Shot Mode:", self.one_shot_check)
        
        self.num_sweeps_spin = QSpinBox()
        self.num_sweeps_spin.setRange(0, 999999)
        self.num_sweeps_spin.setValue(0)
        self.num_sweeps_spin.setSpecialValueText("Infinite")
        layout.addRow("Number of Sweeps:", self.num_sweeps_spin)
        
        self.timestamp_norm_check = QCheckBox()
        layout.addRow("Normalize Timestamps:", self.timestamp_norm_check)
        
        group.setLayout(layout)
        return group
    
    def create_output_group(self):
        """Create output configuration group."""
        group = QGroupBox("Output Configuration")
        layout = QFormLayout()
        
        self.output_mode_combo = QComboBox()
        self.output_mode_combo.addItems(["text", "binary", "ifft"])
        layout.addRow("Output Mode:", self.output_mode_combo)
        
        self.output_file_edit = QLineEdit()
        self.output_file_edit.setPlaceholderText("Optional output file")
        layout.addRow("Output File:", self.output_file_edit)
        
        output_button = QPushButton("Browse...")
        output_button.clicked.connect(self.browse_output_file)
        layout.addRow("", output_button)
        
        group.setLayout(layout)
        return group
    
    def create_button_group(self):
        """Create control buttons."""
        group = QGroupBox("Control")
        layout = QVBoxLayout()
        
        self.start_button = QPushButton("Start Sweep")
        self.start_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        self.start_button.clicked.connect(self.start_sweep_clicked)
        layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Stop Sweep")
        self.stop_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; }")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_sweep_clicked)
        layout.addWidget(self.stop_button)
        
        apply_button = QPushButton("Apply Configuration")
        apply_button.clicked.connect(self.apply_config)
        layout.addWidget(apply_button)
        
        # Debug waterfall button
        debug_button = QPushButton("Debug Waterfall")
        debug_button.setToolTip("Force refresh waterfall display for debugging")
        debug_button.clicked.connect(self.debug_waterfall_clicked)
        layout.addWidget(debug_button)
        
        group.setLayout(layout)
        return group
    
    def browse_wisdom_file(self):
        """Browse for FFTW wisdom file."""
        filename, _ = QFileDialog.getOpenFileName(self, "Select FFTW Wisdom File", "", "All Files (*)")
        if filename:
            self.wisdom_edit.setText(filename)
    
    def browse_output_file(self):
        """Browse for output file."""
        filename, _ = QFileDialog.getSaveFileName(self, "Select Output File", "", "All Files (*)")
        if filename:
            self.output_file_edit.setText(filename)
    
    def start_sweep_clicked(self):
        """Handle start sweep button click."""
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.apply_config()
    
    def stop_sweep_clicked(self):
        """Handle stop sweep button click."""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
    
    def apply_config(self):
        """Apply current configuration and emit signal."""
        self.config.serial_number = self.serial_edit.text()
        self.config.amp_enable = self.amp_check.isChecked()
        self.config.antenna_enable = self.antenna_check.isChecked()
        self.config.freq_min_mhz = self.freq_min_spin.value()
        self.config.freq_max_mhz = self.freq_max_spin.value()
        self.config.lna_gain = self.lna_gain_spin.value()
        self.config.vga_gain = self.vga_gain_spin.value()
        self.config.bin_width = self.bin_width_spin.value()
        self.config.fftw_plan_type = self.fftw_plan_combo.currentText()
        self.config.one_shot = self.one_shot_check.isChecked()
        self.config.num_sweeps = self.num_sweeps_spin.value()
        self.config.output_mode = self.output_mode_combo.currentText()
        self.config.normalized_timestamp = self.timestamp_norm_check.isChecked()
        self.config.wisdom_file = self.wisdom_edit.text()
        
        self.config_changed.emit(self.config)
    
    def debug_waterfall_clicked(self):
        """Handle debug waterfall button click."""
        # Signal to trigger waterfall debug - will be connected to spectrum display
        print("Debug waterfall button clicked - signaling parent window...")


class SpectrumDisplay(QWidget):
    """Spectrum display widget with waterfall and smoothed spectrum plot."""
    
    def __init__(self):
        super().__init__()
        self.freq_min = 0
        self.freq_max = 6000
        
        # Persistent spectrum data
        self.persistent_frequencies = None
        self.persistent_power = None
        self.persistent_peak = None
        
        # Waterfall configuration - CONFIGURABLE: freq=Y, time=X (90° clockwise)
        self.waterfall_history_seconds = 30.0  # Configurable time history
        self.waterfall_update_rate = 20.0      # Hz - updates per second
        self.waterfall_min_freq_pixel_height = 1  # Minimum pixels per frequency bin
        self.waterfall_height = None  # Will be calculated based on frequency bins
        self.waterfall_width = None   # Will be calculated based on time history
        self.waterfall_display_array = None  # Will be allocated when size is known
        
        # Waterfall state
        self.waterfall_lines_added = 0  # Total lines added (for timing calculation)
        self.waterfall_start_time = None  # For accurate timing
        self.waterfall_initialized = False  # Track if waterfall has been sized
        
        # Time averaging variables for display-fitted waterfall
        self.time_per_row = None  # Seconds of data per row (calculated when waterfall is initialized)
        self.row_data_accumulator = None  # Accumulates data for current row
        self.row_samples_count = 0  # Number of samples accumulated for current row
        self.last_row_time = None  # Time when last row was completed
        
        # Spectrum smoothing parameters - optimized for performance
        self.smooth_factor = 1.2
        self.max_display_points = 1000
        
        print(f"Waterfall configured: {self.waterfall_history_seconds}s history at {self.waterfall_update_rate}Hz rate")
        
        self.setup_ui()
        self.setup_plots()
        
    def set_waterfall_history(self, seconds):
        """Set the waterfall time history duration."""
        if seconds > 0:
            self.waterfall_history_seconds = float(seconds)
            print(f"Waterfall history set to {self.waterfall_history_seconds} seconds")
            # Reinitialize with new dimensions
            if hasattr(self, 'waterfall_plot'):
                self.initialize_waterfall_array()
    
    def set_waterfall_update_rate(self, rate_hz):
        """Set the waterfall update rate in Hz."""
        if rate_hz > 0:
            self.waterfall_update_rate = float(rate_hz)
            print(f"Waterfall update rate set to {self.waterfall_update_rate} Hz")
            # Reinitialize with new dimensions
            if hasattr(self, 'waterfall_plot'):
                self.initialize_waterfall_array()
    
    def set_waterfall_freq_resolution(self, min_pixels_per_bin):
        """Set minimum pixels per frequency bin."""
        if min_pixels_per_bin > 0:
            self.waterfall_min_freq_pixel_height = int(min_pixels_per_bin)
            print(f"Waterfall frequency resolution set to {self.waterfall_min_freq_pixel_height} pixels per bin minimum")
            # Reinitialize with new dimensions
            if hasattr(self, 'waterfall_plot'):
                self.initialize_waterfall_array()
    
    def configure_waterfall(self, history_seconds=None, update_rate_hz=None, pixels_per_bin=None):
        """Configure waterfall parameters in one call."""
        if history_seconds is not None:
            self.waterfall_history_seconds = float(history_seconds)
        if update_rate_hz is not None:
            self.waterfall_update_rate = float(update_rate_hz)
        if pixels_per_bin is not None:
            self.waterfall_min_freq_pixel_height = int(pixels_per_bin)
        
        print(f"Waterfall configured: {self.waterfall_history_seconds}s history, {self.waterfall_update_rate}Hz rate, {self.waterfall_min_freq_pixel_height}px/bin")
        
        # Reinitialize with new dimensions
        if hasattr(self, 'waterfall_plot'):
            self.initialize_waterfall_array()
        
    def calculate_waterfall_dimensions(self):
        """Calculate waterfall dimensions based on available display space."""
        if not hasattr(self, 'waterfall_plot') or self.waterfall_plot is None:
            print("WARNING: Waterfall plot not ready, using defaults")
            return 400, 800  # height, width (freq×time)
        
        # Get multiple size measurements for debugging
        measurements = {}
        
        try:
            # Method 1: ViewBox screen geometry
            plot_rect = self.waterfall_plot.getViewBox().screenGeometry()
            measurements['screenGeometry'] = (plot_rect.width(), plot_rect.height())
        except Exception as e:
            measurements['screenGeometry'] = f"Error: {e}"
        
        try:
            # Method 2: ViewBox size
            vb_size = self.waterfall_plot.getViewBox().size()
            measurements['viewBoxSize'] = (vb_size.width(), vb_size.height())
        except Exception as e:
            measurements['viewBoxSize'] = f"Error: {e}"
        
        try:
            # Method 3: Plot widget size
            widget_size = self.waterfall_plot.size()
            measurements['widgetSize'] = (widget_size.width(), widget_size.height())
        except Exception as e:
            measurements['widgetSize'] = f"Error: {e}"
        
        try:
            # Method 4: Plot widget geometry
            widget_geom = self.waterfall_plot.geometry()
            measurements['widgetGeometry'] = (widget_geom.width(), widget_geom.height())
        except Exception as e:
            measurements['widgetGeometry'] = f"Error: {e}"
        
        try:
            # Method 5: Parent widget size
            parent_size = self.plot_widget.size()
            measurements['parentSize'] = (parent_size.width(), parent_size.height())
        except Exception as e:
            measurements['parentSize'] = f"Error: {e}"
        
        # Print all measurements for debugging
        print("\n=== WATERFALL DISPLAY AREA MEASUREMENTS ===")
        for method, size in measurements.items():
            print(f"  {method}: {size}")
        
        # Choose the best available measurement
        available_width = 800
        available_height = 400
        
        # Try to get actual dimensions from any working method
        for method, size in measurements.items():
            if isinstance(size, tuple) and size[0] > 0 and size[1] > 0:
                available_width, available_height = size
                print(f"  Using {method} for dimensions: {available_width}×{available_height}")
                break
        else:
            print(f"  Using fallback dimensions: {available_width}×{available_height}")
        
        # Check if dimensions seem too small (widget might not be fully laid out)
        if available_height < 200 or available_width < 400:
            print(f"  WARNING: Available space seems very small ({available_width}×{available_height})")
            print(f"  This might indicate the widget isn't fully initialized yet")
            print(f"  Using reasonable minimums instead")
            available_width = max(available_width, 800)
            available_height = max(available_height, 300)
        
        # Calculate waterfall dimensions to FIT DISPLAY and average time accordingly
        
        # Height: Use available display height to determine number of rows
        if available_height > 100:
            height = available_height - 20  # Leave some margin
        else:
            height = 200  # Minimum reasonable height
        
        # Width: Calculate based on time history - each column = time sample
        # Use update rate to determine time resolution
        target_time_columns = int(self.waterfall_history_seconds * self.waterfall_update_rate)
        width = target_time_columns
        
        # Calculate time per row based on fitting target history into available height
        time_per_row = self.waterfall_history_seconds / height
        
        print(f"  DISPLAY-FITTED dimensions:")
        print(f"  Available height: {available_height}, using {height} rows")
        print(f"  Each row represents {time_per_row:.3f} seconds of data")
        print(f"  Total time span: {height * time_per_row:.1f} seconds")
        print(f"  Width: {width} columns for time resolution")
        
        print(f"\n=== CALCULATED WATERFALL DIMENSIONS ===")
        print(f"  Available display area: {available_width}×{available_height}")
        print(f"  Natural array size: {height}×{width} (freq×time)")
        print(f"  No scaling applied - 1:1 pixel mapping")
        print(f"  Array aspect ratio: {width/height:.1f}:1 (width:height)")
        print(f"  Time history: {width/self.waterfall_update_rate:.1f} seconds at {self.waterfall_update_rate}Hz rate")
        print(f"  Frequency resolution: {height} pixels (display-fitted)")
        
        return height, width, time_per_row
        
    def _estimate_frequency_bins(self):
        """Estimate the number of frequency bins from current spectrum data."""
        # Try to get frequency bin count from persistent data
        if hasattr(self, 'persistent_frequencies') and self.persistent_frequencies is not None:
            return len(self.persistent_frequencies)
        
        # Try to get from last spectrum update
        if hasattr(self, '_last_spectrum_size'):
            return self._last_spectrum_size
        
        # Default fallback - reasonable assumption for typical spectrum analyzer
        return 512
        
    def initialize_waterfall_array(self):
        """Initialize or resize the waterfall array based on current widget size."""
        new_height, new_width, time_per_row = self.calculate_waterfall_dimensions()
        
        # Check if we need to resize
        needs_resize = (
            self.waterfall_display_array is None or
            self.waterfall_height != new_height or
            self.waterfall_width != new_width
        )
        
        if needs_resize:
            print(f"Initializing waterfall array: {new_height}×{new_width} (freq×time)")
            print(f"  Array shape will be: ({new_height}, {new_width})")
            print(f"  This creates a {'WIDE' if new_width > new_height else 'TALL'} waterfall ({new_width/new_height:.1f}:1 ratio)")
            
            # Store old data if resizing
            old_array = None
            if self.waterfall_display_array is not None:
                old_array = self.waterfall_display_array.copy()
                old_height, old_width = old_array.shape
                print(f"  Preserving data from old {old_height}×{old_width} array")
            
            # Update dimensions
            self.waterfall_height = new_height
            self.waterfall_width = new_width
            self.time_per_row = time_per_row  # Store for data averaging logic
            
            # Initialize time averaging variables
            self.row_data_accumulator = None  # Accumulates data for current row
            self.row_samples_count = 0  # Number of samples accumulated for current row
            self.last_row_time = None  # Time when last row was completed
            
            # Create new array
            self.waterfall_display_array = np.zeros((self.waterfall_height, self.waterfall_width), dtype=np.float32)
            
            # Preserve data if resizing (not initial creation)
            if old_array is not None:
                # Copy what we can from the old array
                copy_height = min(old_height, new_height)
                copy_width = min(old_width, new_width)
                if copy_width > 0 and copy_height > 0:
                    # Copy the most recent data (rightmost columns)
                    self.waterfall_display_array[:copy_height, -copy_width:] = old_array[:copy_height, -copy_width:]
                    print(f"Preserved {copy_height}×{copy_width} of existing waterfall data")
            
            self.waterfall_initialized = True
            
            # Update plot ranges
            if hasattr(self, 'waterfall_plot') and self.waterfall_plot is not None:
                self.waterfall_plot.setXRange(0, self.waterfall_width)
                self.waterfall_plot.setYRange(0, self.waterfall_height)
                
                # Initialize the image with dummy data at natural resolution
                if hasattr(self, 'waterfall_img') and self.waterfall_img is not None:
                    # Set initial dummy image data - no scaling applied
                    dummy_image = np.zeros((self.waterfall_height, self.waterfall_width), dtype=np.float32)
                    self.waterfall_img.setImage(dummy_image)
                    
                    # Don't call setRect - let image be at natural 1:1 pixel resolution
                
                # Disable auto-range to maintain explicit control
                self.waterfall_plot.enableAutoRange(False)
        
    def setup_ui(self):
        """Setup the display UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create plot widget
        self.plot_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plot_widget)
        
        # Add clear peak hold button
        button_layout = QHBoxLayout()
        self.clear_peak_button = QPushButton("Clear Peak Hold")
        self.clear_peak_button.clicked.connect(self.clear_peak_hold)
        button_layout.addWidget(self.clear_peak_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
    def setup_plots(self):
        """Setup the spectrum and waterfall plots."""
        # Set background color on the widget
        self.plot_widget.setBackground('k')
        
        # Main spectrum plot (top)
        self.spectrum_plot = self.plot_widget.addPlot(
            title="HackRF Spectrum Analyzer - Bluetooth Band Analysis",
            labels={'left': 'Power (dB)', 'bottom': ''}
        )
        
        self.spectrum_plot.setLabel('left', 'Power', units='dB')
        self.spectrum_plot.showGrid(x=True, y=True)
        self.spectrum_plot.setYRange(-120, -20)
        
        # Spectrum curve - smooth line
        self.spectrum_curve = self.spectrum_plot.plot(
            pen=pg.mkPen(color='#00FF00', width=2),
            name='Spectrum'
        )
        
        # Peak hold curve
        self.peak_curve = self.spectrum_plot.plot(
            pen=pg.mkPen(color='#FF0000', width=1, style=Qt.DashLine),
            name='Peak Hold'
        )
        
        # Set initial X-axis range
        self.spectrum_plot.setXRange(self.freq_min, self.freq_max)
        
        # Add legend
        self.spectrum_plot.addLegend()
        
        # Move to next row for waterfall
        self.plot_widget.nextRow()
        
        # Waterfall plot (bottom) - optimized for wide and short display
        self.waterfall_plot = self.plot_widget.addPlot(
            title="Waterfall Display",
            labels={'left': 'Time', 'bottom': 'Frequency (MHz)'},
            row=1, col=0  # Explicitly set position
        )
        
        self.waterfall_plot.setLabel('left', 'Time', units='s')
        self.waterfall_plot.setLabel('bottom', 'Frequency', units='MHz')
        
        # Let the waterfall plot use whatever space is available naturally
        # Remove artificial size constraints to allow dynamic scaling
        
        # Try to give the waterfall plot more horizontal space preference
        try:
            # Set the layout to give waterfall more space
            layout = self.plot_widget.ci.layout
            layout.setRowStretchFactor(1, 2)  # Give waterfall row more stretch
            layout.setColumnStretchFactor(0, 1)  # Ensure column uses full width
        except Exception as e:
            print(f"Could not set layout stretch factors: {e}")
        
        # Force background color for debugging (use ViewBox method)
        self.waterfall_plot.getViewBox().setBackgroundColor('black')
        
        # Debug plot layout
        print(f"Waterfall plot created, size: {self.waterfall_plot.size()}")
        print(f"Plot widget layout: {self.plot_widget.ci.layout}")
        # Count layout items properly for QGraphicsGridLayout
        try:
            item_count = 0
            for row in range(self.plot_widget.ci.layout.rowCount()):
                for col in range(self.plot_widget.ci.layout.columnCount()):
                    if self.plot_widget.ci.layout.itemAt(row, col) is not None:
                        item_count += 1
            print(f"Number of plots in layout: {item_count}")
        except Exception as e:
            print(f"Could not count layout items: {e}")
        
        # Waterfall image item
        self.waterfall_img = pg.ImageItem()
        
        # Try different colormap options
        try:
            # Use a high-contrast colormap
            colormap = pg.colormap.get('plasma')  # Very visible purple to yellow
            self.waterfall_img.setColorMap(colormap)
            print("Using plasma colormap")
        except:
            try:
                colormap = pg.colormap.get('viridis')  # Fallback
                self.waterfall_img.setColorMap(colormap)
                print("Using viridis colormap")
            except:
                print("Using default colormap")
        
        # Ensure the image is visible (ImageItem should be visible by default)
        self.waterfall_img.setVisible(True)
        
        # Add item to plot
        self.waterfall_plot.addItem(self.waterfall_img)
        print(f"Added ImageItem to waterfall plot")
        
        # Set waterfall X-axis range
        self.waterfall_plot.setXRange(self.freq_min, self.freq_max)
        
        # Initial ranges will be set when waterfall is initialized
        # Do not enable auto-range as we want explicit control over scaling
        
        # Force the plot to show (use proper Qt widget methods)
        self.waterfall_plot.show()
        # Note: PlotItem doesn't have setVisible, it's automatically visible when added
        
        # Note: Not linking X-axes since they use different coordinate systems
        # Spectrum plot: MHz coordinates, Waterfall plot: array indices
        
        # Initialize waterfall dimensions after plots are created
        self.initialize_waterfall_array()
        
    def resizeEvent(self, event):
        """Handle widget resize events to adjust waterfall dimensions."""
        super().resizeEvent(event)
        
        # Reinitialize waterfall with new size after a short delay
        # This prevents excessive resizing during window dragging
        if hasattr(self, 'waterfall_plot') and self.waterfall_plot is not None:
            # Use a timer to debounce resize events
            if not hasattr(self, '_resize_timer'):
                from PyQt5.QtCore import QTimer
                self._resize_timer = QTimer()
                self._resize_timer.timeout.connect(self._handle_delayed_resize)
                self._resize_timer.setSingleShot(True)
            
            self._resize_timer.start(200)  # 200ms delay
    
    def _handle_delayed_resize(self):
        """Handle the delayed resize to avoid excessive array reallocations."""
        print("Handling window resize - reinitializing waterfall dimensions")
        self.initialize_waterfall_array()
        
    def update_spectrum(self, frequencies, power_levels):
        """Update the spectrum display with new data."""
        # Minimal debug output for performance
        if not hasattr(self, '_update_count'):
            self._update_count = 0
        self._update_count += 1
        
        # Only print debug info occasionally
        if self._update_count % 50 == 1:
            print(f"Spectrum update #{self._update_count}: {len(frequencies)} frequencies, {len(power_levels)} power values")
        
        try:
            # Initialize persistent arrays if needed
            if self.persistent_frequencies is None:
                self._initialize_persistent_data()
                if self._update_count % 50 == 1:
                    print("Initialized persistent data arrays")
            
            # Update persistent data with new segment
            self._update_persistent_segment(frequencies, power_levels)
            
            # Create smoothed spectrum for display
            smooth_freqs, smooth_power, smooth_peak = self._create_smooth_spectrum()
            
            # Limit data points for performance
            if len(smooth_freqs) > self.max_display_points:
                step = len(smooth_freqs) // self.max_display_points
                smooth_freqs = smooth_freqs[::step]
                smooth_power = smooth_power[::step] 
                smooth_peak = smooth_peak[::step]
            
            # Update spectrum display with smoothed data
            if len(smooth_freqs) > 0 and len(smooth_power) > 0:
                self.spectrum_curve.setData(smooth_freqs, smooth_power)
                self.peak_curve.setData(smooth_freqs, smooth_peak)
                
                # Periodically ensure spectrum plot has correct ranges (avoid interfering with user zoom)
                if not hasattr(self, '_spectrum_range_set') or self._spectrum_range_set < 10:
                    self.spectrum_plot.setXRange(self.freq_min, self.freq_max)
                    self.spectrum_plot.setYRange(-120, -20)  # dB range for spectrum
                    self._spectrum_range_set = getattr(self, '_spectrum_range_set', 0) + 1
            
            # Update waterfall display - CORRECTED ORIENTATION: freq=Y, time=X (scrolls left).
            if self._update_count % 3 == 0:  # Every 3rd update instead of every 10th
                self._update_waterfall(smooth_freqs, smooth_power)
            
        except Exception as e:
            # Silent failure to avoid performance impact
            pass
        
    def _initialize_persistent_data(self):
        """Initialize persistent spectrum data arrays."""
        # Create frequency array covering the full configured range
        # Use reasonable resolution for performance (0.1 MHz = 100 kHz steps)
        freq_step = 0.1  # MHz - balanced resolution vs performance
        num_points = int((self.freq_max - self.freq_min) / freq_step) + 1
        
        # Limit maximum points for performance
        if num_points > self.max_display_points:
            num_points = self.max_display_points
            freq_step = (self.freq_max - self.freq_min) / (num_points - 1)
        
        self.persistent_frequencies = np.linspace(self.freq_min, self.freq_max, num_points)
        self.persistent_power = np.full(num_points, -120.0)  # Initialize to noise floor
        self.persistent_peak = np.full(num_points, -120.0)   # Initialize to noise floor
    
    def _update_persistent_segment(self, frequencies, power_levels):
        """Update persistent data with new frequency segment."""
        if self.persistent_frequencies is None:
            return
        
        # Find indices in persistent array that correspond to new data
        for i, freq in enumerate(frequencies):
            # Find closest index in persistent array
            idx = np.argmin(np.abs(self.persistent_frequencies - freq))
            
            # Update power data
            self.persistent_power[idx] = power_levels[i]
            
            # Update peak hold
            self.persistent_peak[idx] = max(self.persistent_peak[idx], power_levels[i])
    
    def _create_smooth_spectrum(self):
        """Create smoothed spectrum for continuous line display."""
        if self.persistent_frequencies is None:
            return np.array([]), np.array([]), np.array([])
        
        # For performance, use the persistent data directly with minimal smoothing
        freq_range = self.persistent_frequencies
        power_data = self.persistent_power
        peak_data = self.persistent_peak
        
        # Only apply interpolation if we have a small dataset and smooth_factor > 1
        if len(freq_range) < 500 and self.smooth_factor > 1.0:
            try:
                # Light interpolation for small datasets only
                target_points = min(int(len(freq_range) * self.smooth_factor), self.max_display_points)
                fine_frequencies = np.linspace(self.freq_min, self.freq_max, target_points)
                
                # Use linear interpolation (much faster than cubic)
                power_interp = interp1d(freq_range, power_data, 
                                      kind='linear', bounds_error=False, fill_value=-120.0)
                fine_power = power_interp(fine_frequencies)
                
                peak_interp = interp1d(freq_range, peak_data, 
                                     kind='linear', bounds_error=False, fill_value=-120.0)
                fine_peak = peak_interp(fine_frequencies)
                
                return fine_frequencies, fine_power, fine_peak
                
            except Exception:
                # Fallback to original data if interpolation fails
                pass
        
        # Default: return original data (no interpolation for performance)
        return freq_range, power_data, peak_data
    
    def _update_waterfall(self, frequencies, power_levels):
        """Update the waterfall display with TIME-BASED AVERAGING to fit target history into available height."""
        if len(frequencies) == 0 or len(power_levels) == 0:
            return
        
        # Ensure waterfall is initialized with current widget size
        if not self.waterfall_initialized or self.waterfall_display_array is None:
            self.initialize_waterfall_array()
            if self.waterfall_display_array is None:
                return  # Still not ready
        
        current_time = time.time()
        
        # Initialize timing and accumulator on first update
        if self.last_row_time is None:
            self.last_row_time = current_time
            self.waterfall_start_time = current_time
            self.spectrum_updates_received = 0
            # Initialize accumulator for frequency data
            if len(power_levels) != self.waterfall_height:
                indices = np.linspace(0, len(power_levels)-1, self.waterfall_height).astype(int)
                self.row_data_accumulator = power_levels[indices].astype(np.float64)  # Use double precision for averaging
            else:
                self.row_data_accumulator = power_levels.astype(np.float64)
            self.row_samples_count = 1
            print(f"Waterfall time-averaging started: {self.time_per_row:.3f}s per row, {self.waterfall_height} rows for {self.waterfall_history_seconds}s history")
            return  # Start accumulating from next update
        
        # Count all spectrum updates (for statistics)
        self.spectrum_updates_received += 1
        
        # Pre-process incoming data to match frequency bins
        if len(power_levels) != self.waterfall_height:
            indices = np.linspace(0, len(power_levels)-1, self.waterfall_height).astype(int)
            processed_data = power_levels[indices].astype(np.float64)
        else:
            processed_data = power_levels.astype(np.float64)
        
        # Accumulate data for current row
        if self.row_data_accumulator is None:
            self.row_data_accumulator = processed_data.copy()
            self.row_samples_count = 1
        else:
            self.row_data_accumulator += processed_data
            self.row_samples_count += 1
        
        # Check if enough time has passed for a new row
        time_since_last_row = current_time - self.last_row_time
        
        if time_since_last_row >= self.time_per_row:
            # Average the accumulated data
            if self.row_samples_count > 0:
                averaged_row = (self.row_data_accumulator / self.row_samples_count).astype(np.float32)
            else:
                averaged_row = processed_data.astype(np.float32)
            
            # Add the averaged row to waterfall - HORIZONTAL SCROLLING
            self.waterfall_display_array[:, :-1] = self.waterfall_display_array[:, 1:]  # Shift left
            self.waterfall_display_array[:, -1] = averaged_row  # Add new averaged data at right
            
            # Update counters and timing
            self.waterfall_lines_added += 1
            self.last_row_time = current_time
            
            # Reset accumulator for next row
            self.row_data_accumulator = None
            self.row_samples_count = 0
            
            # Calculate statistics
            elapsed_time = current_time - self.waterfall_start_time
            actual_waterfall_rate = self.waterfall_lines_added / elapsed_time if elapsed_time > 0 else 0
            spectrum_rate = self.spectrum_updates_received / elapsed_time if elapsed_time > 0 else 0
            
            # Only recalculate color levels occasionally (efficient)
            if self.waterfall_lines_added % 20 == 0:
                sample_data = self.waterfall_display_array[:, -min(50, self.waterfall_width):]
                if sample_data.size > 0:
                    self.current_level_min = np.min(sample_data) - 5
                    self.current_level_max = np.max(sample_data) + 5
            
            # Use cached levels if available
            if not hasattr(self, 'current_level_min'):
                self.current_level_min = -120
                self.current_level_max = -20
            
            # Update display
            try:
                # Debug info occasionally
                if self.waterfall_lines_added % 50 == 1:
                    print(f"Waterfall: {self.waterfall_lines_added} rows added, {elapsed_time:.1f}s elapsed")
                    print(f"  Averaging: {self.time_per_row:.3f}s per row, {self.row_samples_count} samples accumulated")
                    print(f"  Rates: {actual_waterfall_rate:.2f}Hz waterfall / {spectrum_rate:.0f}Hz spectrum")
                    print(f"  Array shape: {self.waterfall_display_array.shape} (freq×time), fits in {self.waterfall_height} display rows")
                
                # Update image with averaged data
                self.waterfall_img.setImage(self.waterfall_display_array)
                self.waterfall_img.setLevels([self.current_level_min, self.current_level_max])
                
                # Set plot ranges to show the exact data dimensions
                self.waterfall_plot.setXRange(0, self.waterfall_width)
                self.waterfall_plot.setYRange(0, self.waterfall_height)
                self.waterfall_plot.enableAutoRange(False)
                
                # Update labels with actual time information
                if self.waterfall_lines_added % 25 == 0:
                    actual_time_span = self.waterfall_lines_added * self.time_per_row
                    max_time_span = min(actual_time_span, self.waterfall_history_seconds)
                    self.waterfall_plot.setLabel('bottom', f'Time ({max_time_span:.1f}s history, {self.time_per_row:.3f}s/row)')
                    self.waterfall_plot.setLabel('left', 'Frequency (fits display)')
                
            except Exception as e:
                print(f"Waterfall display update failed: {e}")
                pass
    
    def set_frequency_range(self, freq_min, freq_max):
        """Set the frequency range for the display."""
        self.freq_min = freq_min
        self.freq_max = freq_max
        
        # Update the X-axis ranges
        self.spectrum_plot.setXRange(freq_min, freq_max)
        self.waterfall_plot.setXRange(freq_min, freq_max)
        
        # Reinitialize persistent data for new frequency range
        self.persistent_frequencies = None
        self.persistent_power = None
        self.persistent_peak = None
        
        # Clear spectrum displays
        self.spectrum_curve.clear()
        self.peak_curve.clear()
        
        # Reset waterfall completely (clears data and state)
        self.reset_waterfall()
        
        # Update plot titles for Bluetooth analysis
        if freq_min >= 2400 and freq_max <= 2500:
            self.spectrum_plot.setTitle("Bluetooth Band Spectrum Analysis (2.4-2.5 GHz)")
        else:
            self.spectrum_plot.setTitle("HackRF Spectrum Analyzer")
    
    def clear_peak_hold(self):
        """Clear peak hold data."""
        if self.persistent_peak is not None:
            # Reset peak hold to current power levels
            self.persistent_peak = self.persistent_power.copy()
            # Update display
            smooth_freqs, smooth_power, smooth_peak = self._create_smooth_spectrum()
            self.peak_curve.setData(smooth_freqs, smooth_peak)
        else:
            # Fallback: clear curve if no persistent data
            self.peak_curve.clear()
    
    def reset_waterfall(self):
        """Reset waterfall display state - fixes issues when starting/stopping sweeps."""
        print("Resetting waterfall display state...")
        
        # Reinitialize with current widget size
        self.initialize_waterfall_array()
        
        # Reset scrolling waterfall and timing
        if self.waterfall_display_array is not None:
            self.waterfall_display_array.fill(0)
        self.waterfall_lines_added = 0
        self.waterfall_start_time = None
        self.waterfall_last_update = None
        self.spectrum_updates_received = 0
        # Reset time averaging variables
        self.row_data_accumulator = None
        self.row_samples_count = 0
        self.last_row_time = None
        self.waterfall_img.clear()
        
        # Reset cached color levels
        if hasattr(self, 'current_level_min'):
            delattr(self, 'current_level_min')
        if hasattr(self, 'current_level_max'):
            delattr(self, 'current_level_max')
        
        # Reset all state variables that could cause issues
        if hasattr(self, '_update_count'):
            delattr(self, '_update_count')
        if hasattr(self, '_waterfall_ranges_set'):
            delattr(self, '_waterfall_ranges_set')
        if hasattr(self, '_spectrum_range_set'):
            delattr(self, '_spectrum_range_set')
        
        # Clear any lingering plot items
        try:
            # Remove any test items that might be in the waterfall plot
            for item in self.waterfall_plot.listDataItems():
                self.waterfall_plot.removeItem(item)
        except:
            pass
        
        # Reset waterfall plot ranges and scaling - HORIZONTAL SCROLLING ORIENTATION
        if self.waterfall_height is not None and self.waterfall_width is not None:
            # Set plot ranges to natural data coordinates
            self.waterfall_plot.setXRange(0, self.waterfall_width)   # X = time (newest at right)
            self.waterfall_plot.setYRange(0, self.waterfall_height) # Y = frequency (aligns with spectrum)
            
            # No image scaling - use natural 1:1 pixel resolution
            # This eliminates compression and jittery scrolling
            
            # Disable auto-ranging to maintain natural coordinates
            self.waterfall_plot.enableAutoRange(False)
            
            # Update labels
            self.waterfall_plot.setLabel('bottom', f'Time (up to {self.waterfall_history_seconds}s history, newest at right)')
            self.waterfall_plot.setLabel('left', 'Frequency (aligns with spectrum)')
            
            print(f"Waterfall reset completed - {self.waterfall_height}×{self.waterfall_width} buffer (freq×time) ready with horizontal scrolling and {self.waterfall_update_rate}Hz rate limiting")
        else:
            print("Waterfall reset completed - dimensions will be calculated when widget is ready")
    
    def force_waterfall_update(self):
        """Force an immediate waterfall display update for debugging."""
        if self.waterfall_lines_added > 0:
            try:
                print(f"Forcing waterfall update with {self.waterfall_lines_added} columns in {self.waterfall_height}×{self.waterfall_width} buffer (freq×time)")
                
                # Calculate actual time span
                if self.waterfall_start_time:
                    elapsed_time = time.time() - self.waterfall_start_time
                    rate = self.waterfall_lines_added / elapsed_time if elapsed_time > 0 else 0
                    print(f"Elapsed: {elapsed_time:.1f}s, Rate: {rate:.1f}Hz")
                
                # Get current display data - horizontal scrolling (freq=Y, time=X)
                display_data = self.waterfall_display_array
                print(f"Display array shape: {display_data.shape} (freq×time)")
                
                # Calculate data range
                data_min = np.min(display_data)
                data_max = np.max(display_data)
                print(f"Data range: {data_min:.1f} to {data_max:.1f} dB")
                
                # Simple color levels
                level_min = data_min - 5
                level_max = data_max + 5
                print(f"Using color levels: {level_min:.1f} to {level_max:.1f} dB")
                
                # Direct image update - array is already correctly oriented
                self.waterfall_img.setImage(display_data)
                self.waterfall_img.setLevels([level_min, level_max])
                
                # Set plot ranges - X=time, Y=frequency
                self.waterfall_plot.setXRange(0, self.waterfall_width)
                self.waterfall_plot.setYRange(0, self.waterfall_height)
                
                print("Waterfall force update completed successfully")
                
            except Exception as e:
                print(f"Waterfall force update failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("No waterfall data available for update - creating test pattern")
            self.create_test_waterfall_pattern()
    
    def add_simple_shape_test(self):
        """Add simple shapes to waterfall plot to verify it can display anything."""
        print("Adding simple shape test to waterfall plot...")
        
        try:
            # Add a simple rectangle to see if the plot can display anything
            from PyQt5.QtWidgets import QGraphicsRectItem
            from PyQt5.QtCore import QRectF
            from PyQt5.QtGui import QPen, QBrush, QColor
            
            rect = QGraphicsRectItem(QRectF(100, 10, 200, 50))
            rect.setPen(QPen(QColor(255, 0, 0), 3))  # Red border
            rect.setBrush(QBrush(QColor(255, 255, 0, 180)))  # Yellow fill
            
            self.waterfall_plot.addItem(rect)
            print("✓ Added test rectangle to waterfall plot")
            
            # Add a line for good measure
            from pyqtgraph import PlotDataItem
            line_item = PlotDataItem([50, 450], [25, 25], pen=pg.mkPen('cyan', width=3))
            self.waterfall_plot.addItem(line_item)
            print("✓ Added test line to waterfall plot")
            
            # Force update (use proper PyQtGraph method)
            self.waterfall_plot.getViewBox().update()
            
        except Exception as e:
            print(f"Shape test failed: {e}")
            import traceback
            traceback.print_exc()

    def create_initial_test_pattern(self):
        """Create a small initial test pattern to verify waterfall display works."""
        print("Creating initial waterfall test pattern...")
        
        # Ensure waterfall is initialized
        if not self.waterfall_initialized or self.waterfall_display_array is None:
            self.initialize_waterfall_array()
            if self.waterfall_display_array is None:
                print("Cannot create test pattern - waterfall not initialized")
                return
        
        # Reset the buffer first
        self.waterfall_display_array.fill(0)
        self.waterfall_lines_added = 0
        self.waterfall_start_time = time.time()
        
        # Create a simple test pattern using the circular buffer - NEW ORIENTATION
        num_test_columns = 10
        
        for i in range(num_test_columns):
            # Create test data column with HIGH contrast - frequency data (Y-axis)
            test_column = np.full(self.waterfall_height, -100.0, dtype=np.float32)
            
            # Create frequency patterns for visibility
            for j in range(0, self.waterfall_height, 40):
                if (j // 40) % 2 == 0:
                    test_column[j:j+20] = -40.0  # Bright frequency bands
                else:
                    test_column[j:j+20] = -100.0  # Dark frequency bands
            
            # Add a moving bright frequency line that moves up/down
            bright_freq_idx = int((i / num_test_columns) * self.waterfall_height)
            if bright_freq_idx < self.waterfall_height - 5:
                test_column[bright_freq_idx:bright_freq_idx+5] = -20.0
            
            # Add using horizontal scrolling (shift left, add at right)
            self.waterfall_display_array[:, :-1] = self.waterfall_display_array[:, 1:]  # Shift left
            self.waterfall_display_array[:, -1] = test_column  # Add new data at right
            self.waterfall_lines_added += 1
        
        print(f"Created initial test pattern with {self.waterfall_lines_added} columns")
        
        # Force update the display
        try:
            display_data = self.waterfall_display_array
            self.waterfall_img.setImage(display_data)
            self.waterfall_img.setLevels([-120, -10])
            
            self.waterfall_plot.setXRange(0, self.waterfall_width)
            self.waterfall_plot.setYRange(0, self.waterfall_height)
            
            print("✓ Initial test pattern displayed successfully")
            
        except Exception as e:
            print(f"Failed to display initial test pattern: {e}")
            import traceback
            traceback.print_exc()

    def create_test_waterfall_pattern(self):
        """Create test pattern to verify the waterfall display functionality."""
        print("Creating comprehensive waterfall test pattern...")
        
        # Ensure waterfall is initialized
        if not self.waterfall_initialized or self.waterfall_display_array is None:
            self.initialize_waterfall_array()
            if self.waterfall_display_array is None:
                print("Cannot create test pattern - waterfall not initialized")
                return
        
        # Reset the buffer completely
        self.waterfall_display_array.fill(0)
        self.waterfall_lines_added = 0
        self.waterfall_start_time = time.time()
        
        # Create test pattern with varying intensity - NEW ORIENTATION
        num_test_columns = 50  # More comprehensive test
        
        for i in range(num_test_columns):
            # Base noise floor (frequency column)
            test_column = np.random.normal(-90, 10, self.waterfall_height).astype(np.float32)
            
            # Add multiple signal features at different frequencies
            # Strong signal at 1/4 frequency
            quarter_freq = self.waterfall_height // 4
            test_column[quarter_freq-10:quarter_freq+10] = -30 + np.sin(i * 0.3) * 10
            
            # Medium signal at center frequency (moving)
            center_offset = int(20 * np.sin(i * 0.1))
            center_freq = self.waterfall_height // 2 + center_offset
            if 0 <= center_freq < self.waterfall_height:
                test_column[center_freq-5:center_freq+5] = -40 + np.random.normal(0, 5)
            
            # Weak signal at 3/4 frequency (intermittent)
            if i % 3 == 0:
                three_quarter_freq = 3 * self.waterfall_height // 4
                test_column[three_quarter_freq-3:three_quarter_freq+3] = -50
            
            # Add some random spikes
            spike_freq = np.random.randint(0, self.waterfall_height)
            test_column[spike_freq] = -20
            
            # Add using horizontal scrolling (shift left, add at right)
            self.waterfall_display_array[:, :-1] = self.waterfall_display_array[:, 1:]  # Shift left
            self.waterfall_display_array[:, -1] = test_column  # Add new data at right
            self.waterfall_lines_added += 1
        
        print(f"Created test pattern with {self.waterfall_lines_added} columns")
        
        # Force update the display
        try:
            display_data = self.waterfall_display_array
            data_min = np.min(display_data)
            data_max = np.max(display_data)
            print(f"Test pattern data range: {data_min:.1f} to {data_max:.1f} dB")
            
            self.waterfall_img.setImage(display_data)
            self.waterfall_img.setLevels([data_min - 5, data_max + 5])
            
            self.waterfall_plot.setXRange(0, self.waterfall_width)
            self.waterfall_plot.setYRange(0, self.waterfall_height)
            
            print("✓ Test pattern displayed successfully")
            
        except Exception as e:
            print(f"Failed to display test pattern: {e}")
            import traceback
            traceback.print_exc()



class SpectrumAnalyzerMainWindow(QMainWindow):
    """Main window for the HackRF Spectrum Analyzer with Bluetooth analysis focus."""
    
    def __init__(self):
        super().__init__()
        self.hackrf = HackRFInterface()
        
        # Statistics tracking for status bar
        self.current_sweep_count = 0
        self.current_sweep_rate = 0.0
        self.current_data_rate = 0.0
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Setup the main window UI."""
        self.setWindowTitle("HackRF Spectrum Analyzer - Bluetooth Band Analysis")
        self.setGeometry(100, 100, 1400, 900)  # Taller for waterfall
        
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Main splitter (control panel | spectrum display)
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Control panel (left side)
        self.control_panel = ControlPanel()
        main_splitter.addWidget(self.control_panel)
        
        # Spectrum display with waterfall (right side - full height)
        self.spectrum_display = SpectrumDisplay()
        main_splitter.addWidget(self.spectrum_display)
        
        # Set splitter proportions (control panel smaller, spectrum larger)
        main_splitter.setSizes([300, 1100])
        
        # Status bar with sweep statistics
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status_bar()
        
    def connect_signals(self):
        """Connect signals between components."""
        # Control panel signals
        self.control_panel.config_changed.connect(self.hackrf.update_config)
        self.control_panel.config_changed.connect(self.update_display_range)
        self.control_panel.start_button.clicked.connect(self.start_sweep)
        self.control_panel.stop_button.clicked.connect(self.stop_sweep)
        
        # Connect debug waterfall button
        # Find the debug button and connect it
        for widget in self.control_panel.findChildren(QPushButton):
            if widget.text() == "Debug Waterfall":
                widget.clicked.connect(self.spectrum_display.force_waterfall_update)
                break
        
        # HackRF interface signals
        self.hackrf.spectrum_data_ready.connect(self.spectrum_display.update_spectrum)
        self.hackrf.sweep_status_changed.connect(self.update_status_message)
        self.hackrf.error_occurred.connect(self.show_error)
        self.hackrf.sweep_stats_updated.connect(self.update_sweep_stats)
        
        # Set initial frequency range from control panel
        self.update_display_range(self.control_panel.config)
        
        # Set default to Bluetooth range
        self.control_panel.freq_min_spin.setValue(2400)
        self.control_panel.freq_max_spin.setValue(2500)
        
        # Set smaller FFT bin width for better Bluetooth resolution
        self.control_panel.bin_width_spin.setValue(100000)  # 100 kHz bins
    
    def update_display_range(self, config):
        """Update the spectrum display frequency range from configuration."""
        self.spectrum_display.set_frequency_range(config.freq_min_mhz, config.freq_max_mhz)
        
        # Update status bar to show current frequency range
        self.update_status_bar()
        
    def update_sweep_stats(self, sweep_count, sweep_rate, data_rate):
        """Update sweep statistics."""
        self.current_sweep_count = sweep_count
        self.current_sweep_rate = sweep_rate
        self.current_data_rate = data_rate
        self.update_status_bar()
    
    def update_status_message(self, message):
        """Update status message in status bar."""
        # Just update the main status message, stats are shown separately
        freq_range = f"{self.control_panel.config.freq_min_mhz:.0f}-{self.control_panel.config.freq_max_mhz:.0f} MHz"
        stats = f"Sweeps: {self.current_sweep_count} | Rate: {self.current_sweep_rate:.1f}/s | Data: {self.current_data_rate:.1f} KB/s"
        
        self.status_bar.showMessage(f"{message} | {freq_range} | {stats}")
    
    def update_status_bar(self):
        """Update the status bar with current information."""
        freq_range = f"{self.control_panel.config.freq_min_mhz:.0f}-{self.control_panel.config.freq_max_mhz:.0f} MHz"
        stats = f"Sweeps: {self.current_sweep_count} | Rate: {self.current_sweep_rate:.1f}/s | Data: {self.current_data_rate:.1f} KB/s"
        
        if self.hackrf.is_running:
            status = "Running"
        else:
            status = "Ready"
            
        self.status_bar.showMessage(f"{status} | {freq_range} | {stats}")
        
    def start_sweep(self):
        """Start the spectrum sweep."""
        # Validate configuration
        valid, message = self.hackrf.validate_config()
        if not valid:
            QMessageBox.warning(self, "Configuration Error", message)
            self.control_panel.start_button.setEnabled(True)
            self.control_panel.stop_button.setEnabled(False)
            return
        
        # Reset waterfall display state to ensure it works after restart
        self.spectrum_display.reset_waterfall()
        
        self.hackrf.start_sweep()
        self.update_status_bar()
        
    def stop_sweep(self):
        """Stop the spectrum sweep."""
        self.hackrf.stop_sweep()
        # Reset waterfall state when stopping to ensure clean restart
        self.spectrum_display.reset_waterfall()
        self.update_status_bar()
        
    def show_error(self, message):
        """Show error message."""
        QMessageBox.critical(self, "Error", message)
        error_freq_range = f"{self.control_panel.config.freq_min_mhz:.0f}-{self.control_panel.config.freq_max_mhz:.0f} MHz"
        self.status_bar.showMessage(f"ERROR: {message} | {error_freq_range}")
        
    def closeEvent(self, event):
        """Handle window close event."""
        if self.hackrf.is_running:
            self.hackrf.stop_sweep()
        event.accept() 