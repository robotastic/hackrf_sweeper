#!/usr/bin/env python3

"""
Example configuration script for the new time-averaging waterfall display.

This demonstrates the improved waterfall system that:
- Measures available display height to determine number of rows
- Calculates time per row to fit target history into available height  
- Averages incoming spectrum data over each time period
- Provides natural resolution without scaling artifacts
"""

import sys
import numpy as np
import time
from spectrum_analyzer_ui import SpectrumDisplay
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox

class WaterfallConfigDemo(QMainWindow):
    """Demo application showing configurable time-averaging waterfall."""
    
    def __init__(self):
        super().__init__()
        self.spectrum_display = SpectrumDisplay()
        self.setup_ui()
        
        # Start demo data generation
        from PyQt5.QtCore import QTimer
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.generate_demo_data)
        self.data_timer.start(50)  # 20Hz data generation
        
        # Track data generation
        self.demo_start_time = time.time()
        self.demo_data_count = 0
        
    def setup_ui(self):
        """Setup the demo UI with configuration controls."""
        self.setWindowTitle("Waterfall Time-Averaging Configuration Demo")
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Configuration controls
        config_layout = QHBoxLayout()
        
        # Time history control
        config_layout.addWidget(QLabel("History (s):"))
        self.history_spin = QDoubleSpinBox()
        self.history_spin.setRange(5.0, 300.0)
        self.history_spin.setValue(30.0)
        self.history_spin.valueChanged.connect(self.update_config)
        config_layout.addWidget(self.history_spin)
        
        # Update rate control
        config_layout.addWidget(QLabel("Update Rate (Hz):"))
        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(1.0, 100.0)
        self.rate_spin.setValue(20.0)
        self.rate_spin.valueChanged.connect(self.update_config)
        config_layout.addWidget(self.rate_spin)
        
        # Pixels per bin control
        config_layout.addWidget(QLabel("Pixels per freq bin:"))
        self.pixels_spin = QSpinBox()
        self.pixels_spin.setRange(1, 10)
        self.pixels_spin.setValue(1)
        self.pixels_spin.valueChanged.connect(self.update_config)
        config_layout.addWidget(self.pixels_spin)
        
        # Preset buttons
        preset_layout = QHBoxLayout()
        
        btn1 = QPushButton("High Time Resolution (10s, 50Hz)")
        btn1.clicked.connect(lambda: self.apply_preset(10, 50, 2))
        preset_layout.addWidget(btn1)
        
        btn2 = QPushButton("Long History (60s, 10Hz)")
        btn2.clicked.connect(lambda: self.apply_preset(60, 10, 1))
        preset_layout.addWidget(btn2)
        
        btn3 = QPushButton("High Freq Detail (30s, 20Hz, 4px/bin)")
        btn3.clicked.connect(lambda: self.apply_preset(30, 20, 4))
        preset_layout.addWidget(btn3)
        
        btn4 = QPushButton("Default (30s, 20Hz)")
        btn4.clicked.connect(lambda: self.apply_preset(30, 20, 1))
        preset_layout.addWidget(btn4)
        
        config_layout.addStretch()
        preset_layout.addStretch()
        
        layout.addLayout(config_layout)
        layout.addLayout(preset_layout)
        
        # Add spectrum display
        layout.addWidget(self.spectrum_display)
        
        # Status display
        self.status_label = QLabel("Starting demo...")
        layout.addWidget(self.status_label)
        
    def apply_preset(self, history_s, rate_hz, pixels_per_bin):
        """Apply a configuration preset."""
        print(f"\nApplying preset: {history_s}s history, {rate_hz}Hz, {pixels_per_bin}px/bin")
        
        # Update controls
        self.history_spin.setValue(history_s)
        self.rate_spin.setValue(rate_hz)
        self.pixels_spin.setValue(pixels_per_bin)
        
        # Apply configuration
        self.spectrum_display.configure_waterfall(
            history_seconds=history_s,
            update_rate_hz=rate_hz,
            pixels_per_bin=pixels_per_bin
        )
        
        self.update_status()
        
    def update_config(self):
        """Update waterfall configuration from controls."""
        history = self.history_spin.value()
        rate = self.rate_spin.value()
        pixels = self.pixels_spin.value()
        
        self.spectrum_display.configure_waterfall(
            history_seconds=history,
            update_rate_hz=rate,
            pixels_per_bin=pixels
        )
        
        self.update_status()
        
    def update_status(self):
        """Update status display."""
        if hasattr(self.spectrum_display, 'time_per_row') and self.spectrum_display.time_per_row:
            height = self.spectrum_display.waterfall_height or 0
            width = self.spectrum_display.waterfall_width or 0
            time_per_row = self.spectrum_display.time_per_row
            
            status = f"Waterfall: {height} rows × {width} cols, {time_per_row:.3f}s per row"
            if height > 0:
                total_display_time = height * time_per_row
                status += f", {total_display_time:.1f}s total"
        else:
            status = "Waterfall initializing..."
            
        self.status_label.setText(status)
        
    def generate_demo_data(self):
        """Generate synthetic spectrum data for demonstration."""
        self.demo_data_count += 1
        elapsed = time.time() - self.demo_start_time
        
        # Create synthetic frequency range (Bluetooth band)
        frequencies = np.linspace(2400, 2500, 512)  # MHz
        
        # Generate synthetic spectrum with moving signals
        power_levels = np.random.normal(-85, 8, 512)  # Base noise
        
        # Add moving signals
        signal1_freq_idx = int(100 + 50 * np.sin(elapsed * 0.5))  # Slow moving signal
        signal2_freq_idx = int(300 + 30 * np.sin(elapsed * 2.0))  # Fast moving signal
        signal3_freq_idx = int(400 + 20 * np.cos(elapsed * 1.0))  # Medium moving signal
        
        # Add signals with varying intensity
        power_levels[signal1_freq_idx-5:signal1_freq_idx+5] = -45 + 10 * np.sin(elapsed * 0.3)
        power_levels[signal2_freq_idx-3:signal2_freq_idx+3] = -35 + 5 * np.cos(elapsed * 1.5)
        power_levels[signal3_freq_idx-2:signal3_freq_idx+2] = -40 + 8 * np.sin(elapsed * 0.8)
        
        # Add some random spikes
        if np.random.random() < 0.1:  # 10% chance
            spike_idx = np.random.randint(50, 450)
            power_levels[spike_idx-1:spike_idx+1] = -25
            
        # Update display
        self.spectrum_display.update_spectrum(frequencies, power_levels)
        
        # Update status periodically
        if self.demo_data_count % 50 == 0:
            self.update_status()
            rate = self.demo_data_count / elapsed if elapsed > 0 else 0
            print(f"Demo: {self.demo_data_count} spectra generated at {rate:.1f}Hz after {elapsed:.1f}s")

def main():
    """Run the waterfall configuration demo."""
    app = QApplication(sys.argv)
    
    print("=" * 60)
    print("WATERFALL TIME-AVERAGING CONFIGURATION DEMO")
    print("=" * 60)
    print()
    print("This demo shows the new waterfall display capabilities:")
    print("• Measures available display height")
    print("• Calculates time per row to fit target history")
    print("• Averages spectrum data over each time period")
    print("• Provides configurable time history and frequency resolution")
    print()
    print("Try the preset buttons to see different configurations!")
    print("=" * 60)
    
    window = WaterfallConfigDemo()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 