"""
Configuration Management Module
Handles loading and validation of spectrum monitor configuration.
"""

import yaml
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SpectrumConfig:
    """Spectrum scanning configuration."""
    freq_min_mhz: float
    freq_max_mhz: float
    bin_width: int


@dataclass 
class HackRFConfig:
    """HackRF device configuration."""
    lna_gain: int
    vga_gain: int
    amp_enable: bool
    antenna_enable: bool
    one_shot: bool
    serial_number: str
    dc_spike_removal: bool
    dc_spike_width: int


@dataclass
class MonitoringConfig:
    """Monitoring mode configuration."""
    threshold_buffer_db: float
    update_rate_hz: float
    min_detection_duration_s: float


@dataclass
class StorageConfig:
    """Data storage configuration."""
    baseline_file: str
    learning_history: int
    data_directory: str


@dataclass
class DisplayConfig:
    """Display and output configuration."""
    show_frequency_mhz: bool
    precision_digits: int
    power_precision: int
    alert_beep: bool


@dataclass
class PerformanceConfig:
    """Performance and optimization configuration."""
    max_display_points: int
    processing_threads: int


class Configuration:
    """Main configuration manager for the spectrum monitor."""
    
    def __init__(self, config_file: str = "config.yaml"):
        """Initialize configuration from file.
        
        Args:
            config_file: Path to YAML configuration file
        """
        self.config_file = config_file
        self.spectrum: SpectrumConfig = None
        self.hackrf: HackRFConfig = None
        self.monitoring: MonitoringConfig = None
        self.storage: StorageConfig = None
        self.display: DisplayConfig = None
        self.performance: PerformanceConfig = None
        
        self.load()
    
    def load(self) -> None:
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        
        with open(self.config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Load each configuration section
        self.spectrum = SpectrumConfig(**config_data.get('spectrum', {}))
        self.hackrf = HackRFConfig(**config_data.get('hackrf', {}))
        self.monitoring = MonitoringConfig(**config_data.get('monitoring', {}))
        self.storage = StorageConfig(**config_data.get('storage', {}))
        self.display = DisplayConfig(**config_data.get('display', {}))
        self.performance = PerformanceConfig(**config_data.get('performance', {}))
        
        # Validate configuration
        self.validate()
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        # Spectrum validation
        if self.spectrum.freq_min_mhz < 0:
            raise ValueError("freq_min_mhz must be non-negative")
        if self.spectrum.freq_max_mhz <= self.spectrum.freq_min_mhz:
            raise ValueError("freq_max_mhz must be greater than freq_min_mhz")
        if self.spectrum.freq_max_mhz > 7250:
            raise ValueError("freq_max_mhz cannot exceed 7250 MHz (HackRF limit)")
        if self.spectrum.bin_width < 245000 or self.spectrum.bin_width > 5000000:
            raise ValueError("bin_width must be between 245 kHz and 5 MHz")
        
        # HackRF validation
        if not (0 <= self.hackrf.lna_gain <= 40):
            raise ValueError("lna_gain must be between 0 and 40 dB")
        if not (0 <= self.hackrf.vga_gain <= 62):
            raise ValueError("vga_gain must be between 0 and 62 dB")
        if self.hackrf.lna_gain % 8 != 0:
            raise ValueError("lna_gain must be in 8 dB steps")
        if self.hackrf.vga_gain % 2 != 0:
            raise ValueError("vga_gain must be in 2 dB steps")
        if self.hackrf.dc_spike_width < 0:
            raise ValueError("dc_spike_width must be non-negative")
        if self.hackrf.dc_spike_width > 10:
            raise ValueError("dc_spike_width should not exceed 10 bins")
        
        # Monitoring validation
        if self.monitoring.threshold_buffer_db < 0:
            raise ValueError("threshold_buffer_db must be non-negative")
        if self.monitoring.update_rate_hz <= 0:
            raise ValueError("update_rate_hz must be positive")
        if self.monitoring.min_detection_duration_s < 0:
            raise ValueError("min_detection_duration_s must be non-negative")
        
        # Storage validation
        if self.storage.learning_history <= 0:
            raise ValueError("learning_history must be positive")
        if not os.path.isdir(self.storage.data_directory):
            try:
                os.makedirs(self.storage.data_directory, exist_ok=True)
            except OSError as e:
                raise ValueError(f"Cannot create data directory: {e}")
        
        # Performance validation
        if self.performance.max_display_points <= 0:
            raise ValueError("max_display_points must be positive")
        if self.performance.processing_threads <= 0:
            raise ValueError("processing_threads must be positive")
    
    def save(self, config_file: Optional[str] = None) -> None:
        """Save current configuration to YAML file.
        
        Args:
            config_file: Optional different file path to save to
        """
        save_file = config_file or self.config_file
        
        config_data = {
            'spectrum': {
                'freq_min_mhz': self.spectrum.freq_min_mhz,
                'freq_max_mhz': self.spectrum.freq_max_mhz,
                'bin_width': self.spectrum.bin_width
            },
            'hackrf': {
                'lna_gain': self.hackrf.lna_gain,
                'vga_gain': self.hackrf.vga_gain,
                'amp_enable': self.hackrf.amp_enable,
                'antenna_enable': self.hackrf.antenna_enable,
                'one_shot': self.hackrf.one_shot,
                'serial_number': self.hackrf.serial_number,
                'dc_spike_removal': self.hackrf.dc_spike_removal,
                'dc_spike_width': self.hackrf.dc_spike_width
            },
            'monitoring': {
                'threshold_buffer_db': self.monitoring.threshold_buffer_db,
                'update_rate_hz': self.monitoring.update_rate_hz,
                'min_detection_duration_s': self.monitoring.min_detection_duration_s
            },
            'storage': {
                'baseline_file': self.storage.baseline_file,
                'learning_history': self.storage.learning_history,
                'data_directory': self.storage.data_directory
            },
            'display': {
                'show_frequency_mhz': self.display.show_frequency_mhz,
                'precision_digits': self.display.precision_digits,
                'power_precision': self.display.power_precision,
                'alert_beep': self.display.alert_beep
            },
            'performance': {
                'max_display_points': self.performance.max_display_points,
                'processing_threads': self.performance.processing_threads
            }
        }
        
        with open(save_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)
    
    def get_baseline_file_path(self) -> str:
        """Get full path to baseline file."""
        return os.path.join(self.storage.data_directory, self.storage.baseline_file)
    
    def update_threshold_buffer(self, new_value: float) -> None:
        """Update threshold buffer value.
        
        Args:
            new_value: New threshold buffer in dB
        """
        if new_value < 0:
            raise ValueError("Threshold buffer must be non-negative")
        self.monitoring.threshold_buffer_db = new_value
    
    def __str__(self) -> str:
        """String representation of configuration."""
        return (
            f"Spectrum Monitor Configuration:\n"
            f"  Frequency Range: {self.spectrum.freq_min_mhz} - {self.spectrum.freq_max_mhz} MHz\n"
            f"  Bin Width: {self.spectrum.bin_width / 1e6:.3f} MHz\n"
            f"  LNA Gain: {self.hackrf.lna_gain} dB\n"
            f"  VGA Gain: {self.hackrf.vga_gain} dB\n"
            f"  Threshold Buffer: {self.monitoring.threshold_buffer_db} dB\n"
            f"  Update Rate: {self.monitoring.update_rate_hz} Hz\n"
            f"  Baseline File: {self.get_baseline_file_path()}"
        ) 