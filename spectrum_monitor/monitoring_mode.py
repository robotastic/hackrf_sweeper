"""
Monitoring Mode Module
Implements spectrum monitoring functionality with baseline comparison and alerting.
"""

import numpy as np
import time
import threading
from typing import Optional, Dict, Any, List, Tuple
import keyboard

from hackrf_interface import HackRFInterface
from storage import BaselineStorage
from display import CLIDisplay
from config import Configuration


class Alert:
    """Represents a spectrum alert."""
    
    def __init__(self, frequency: float, signal_power: float, baseline_power: float, 
                 threshold_buffer: float, detection_time: float):
        """Initialize alert.
        
        Args:
            frequency: Alert frequency in MHz
            signal_power: Detected signal power in dB
            baseline_power: Baseline power level in dB
            threshold_buffer: Threshold buffer used in dB
            detection_time: Time of detection
        """
        self.frequency = frequency
        self.signal_power = signal_power
        self.baseline_power = baseline_power
        self.threshold_buffer = threshold_buffer
        self.detection_time = detection_time
        self.first_detection_time = detection_time
        self.last_detection_time = detection_time
        self.detection_count = 1
    
    def update_detection(self, signal_power: float, detection_time: float):
        """Update alert with new detection.
        
        Args:
            signal_power: New signal power level
            detection_time: Time of new detection
        """
        self.signal_power = max(self.signal_power, signal_power)  # Keep highest power
        self.last_detection_time = detection_time
        self.detection_count += 1
    
    def get_duration(self) -> float:
        """Get detection duration in seconds."""
        return self.last_detection_time - self.first_detection_time
    
    def should_alert(self, min_duration: float) -> bool:
        """Check if alert meets minimum duration requirement."""
        return self.get_duration() >= min_duration


class MonitoringMode:
    """Implements monitoring mode with baseline comparison and alerting."""
    
    def __init__(self, config: Configuration, display: CLIDisplay):
        """Initialize monitoring mode.
        
        Args:
            config: Configuration object
            display: Display object for output
        """
        self.config = config
        self.display = display
        
        # HackRF interface
        self.hackrf = HackRFInterface()
        
        # Storage for baselines
        self.storage = BaselineStorage(config.get_baseline_file_path())
        
        # Monitoring state
        self.is_monitoring = False
        self.should_stop = False
        self.start_time = 0
        
        # Baseline data
        self.baseline_frequencies = None
        self.baseline_power_levels = None
        
        # Detection state
        self.current_threshold_buffer = config.monitoring.threshold_buffer_db
        self.active_alerts = {}  # frequency -> Alert
        self.alert_history = []
        self.sweep_count = 0
        
        # Statistics
        self.last_sweep_time = 0
        self.sweep_rate = 0.0
        self.total_alerts = 0
        
        # Thread synchronization
        self.data_lock = threading.Lock()
        self.keyboard_thread = None
        
        # Configure HackRF
        self._configure_hackrf()
    
    def _configure_hackrf(self):
        """Configure HackRF parameters from config."""
        print(f"DEBUG: Monitoring mode configuring HackRF...")
        
        self.hackrf.config.freq_min_mhz = self.config.spectrum.freq_min_mhz
        self.hackrf.config.freq_max_mhz = self.config.spectrum.freq_max_mhz
        self.hackrf.config.bin_width = self.config.spectrum.bin_width
        self.hackrf.config.lna_gain = self.config.hackrf.lna_gain
        self.hackrf.config.vga_gain = self.config.hackrf.vga_gain
        self.hackrf.config.amp_enable = self.config.hackrf.amp_enable
        self.hackrf.config.antenna_enable = self.config.hackrf.antenna_enable
        self.hackrf.config.one_shot = self.config.hackrf.one_shot
        self.hackrf.config.serial_number = self.config.hackrf.serial_number
        self.hackrf.config.dc_spike_removal = self.config.hackrf.dc_spike_removal
        self.hackrf.config.dc_spike_width = self.config.hackrf.dc_spike_width
        
        # Set data callback
        self.hackrf.set_data_callback(self._on_spectrum_data)
    
    def _load_baselines(self) -> bool:
        """Load baseline data from storage.
        
        Returns:
            True if baselines loaded successfully, False otherwise
        """
        if not self.storage.load_baselines():
            return False
        
        # Get baseline data
        self.baseline_frequencies, self.baseline_power_levels = self.storage.get_baselines()
        
        if self.baseline_frequencies is None or self.baseline_power_levels is None:
            return False
        
        # Check frequency coverage
        is_covered, message = self.storage.check_frequency_coverage(
            self.config.spectrum.freq_min_mhz,
            self.config.spectrum.freq_max_mhz
        )
        
        if not is_covered:
            self.display.print_error(message)
            return False
        
        return True
    
    def _on_spectrum_data(self, frequencies: np.ndarray, power_levels: np.ndarray):
        """Callback for new spectrum data.
        
        Args:
            frequencies: Frequency array in MHz
            power_levels: Power levels in dB
        """
        with self.data_lock:
            if not self.is_monitoring:
                return
            
            # Update statistics
            self.sweep_count += 1
            current_time = time.time()
            if self.last_sweep_time > 0:
                self.sweep_rate = 1.0 / (current_time - self.last_sweep_time)
            self.last_sweep_time = current_time
            
            # Interpolate baselines to match current frequency grid
            interpolated_baselines = self.storage.interpolate_baselines(frequencies)
            if interpolated_baselines is None:
                return
            
            # Calculate threshold levels
            threshold_levels = interpolated_baselines + self.current_threshold_buffer
            
            # Find frequencies exceeding threshold
            exceedances = power_levels > threshold_levels
            exceeding_indices = np.where(exceedances)[0]
            
            current_alerts = []
            
            # Process each exceedance
            for idx in exceeding_indices:
                freq = frequencies[idx]
                signal_power = power_levels[idx]
                baseline_power = interpolated_baselines[idx]
                
                # Create frequency key (rounded for grouping nearby frequencies)
                freq_key = round(freq, 2)
                
                if freq_key in self.active_alerts:
                    # Update existing alert
                    self.active_alerts[freq_key].update_detection(signal_power, current_time)
                else:
                    # Create new alert
                    alert = Alert(freq, signal_power, baseline_power, 
                                self.current_threshold_buffer, current_time)
                    self.active_alerts[freq_key] = alert
                
                current_alerts.append({
                    'frequency': freq,
                    'signal_power': signal_power,
                    'baseline_power': baseline_power,
                    'threshold_buffer': self.current_threshold_buffer
                })
            
            # Display all active alerts immediately
            alerts_to_display = []
            
            for freq_key, alert in self.active_alerts.items():
                #if alert.should_alert(self.config.monitoring.min_detection_duration_s):
                    # Alert meets duration requirement
                if freq_key not in [a['frequency_key'] for a in alerts_to_display]:
                    alerts_to_display.append({
                        'frequency': alert.frequency,
                        'signal_power': alert.signal_power,
                        'baseline_power': alert.baseline_power,
                        'threshold_buffer': alert.threshold_buffer,
                        'frequency_key': freq_key
                    })
            
            # Add completed alerts to history and remove from active
            alerts_to_remove = []
            for freq_key, alert in self.active_alerts.items():
                # Check if alert has been inactive for a while (cleanup old alerts)
                time_since_last = current_time - alert.last_detection_time
                if time_since_last > 5.0:  # 5 second cleanup timeout
                    if alert.should_alert(self.config.monitoring.min_detection_duration_s):
                        # Add to history if it met duration requirement
                        self.alert_history.append(alert)
                        self.total_alerts += 1
                    alerts_to_remove.append(freq_key)
            
            # Remove old alerts
            for freq_key in alerts_to_remove:
                del self.active_alerts[freq_key]
            
            # Display alerts
            if alerts_to_display:
                if len(alerts_to_display) == 1:
                    alert = alerts_to_display[0]
                    self.display.print_alert(
                        alert['frequency'],
                        alert['signal_power'],
                        alert['baseline_power'],
                        alert['threshold_buffer']
                    )
                else:
                    self.display.print_multiple_alerts(alerts_to_display)
            
            # Update display status
            #self._update_display()
    
    def _update_display(self):
        """Update the monitoring mode display."""
        # alerts_detected = self.display.get_alert_count()
        
        # self.display.print_monitoring_status(
        #     self.sweep_count,
        #     self.current_threshold_buffer,
        #     self.sweep_rate,
        #     alerts_detected
        # )
    
    def _keyboard_monitor(self):
        """Monitor for keyboard input to control monitoring."""
        try:
            while self.is_monitoring and not self.should_stop:
                # Check for key press
                if keyboard.read_event():
                    event = keyboard.read_event()
                    if event.event_type == keyboard.KEY_DOWN:
                        key_name = event.name.lower()
                        
                        if key_name == 'q':
                            # Quit monitoring
                            self.should_stop = True
                            break
                        elif key_name == '+' or key_name == '=':
                            # Increase threshold buffer
                            self.current_threshold_buffer += 1.0
                            self.config.update_threshold_buffer(self.current_threshold_buffer)
                            self.display.update_threshold_display(self.current_threshold_buffer)
                        elif key_name == '-':
                            # Decrease threshold buffer
                            if self.current_threshold_buffer > 1.0:
                                self.current_threshold_buffer -= 1.0
                                self.config.update_threshold_buffer(self.current_threshold_buffer)
                                self.display.update_threshold_display(self.current_threshold_buffer)
                        elif key_name == 'r':
                            # Reset threshold buffer to config default
                            self.current_threshold_buffer = self.config.monitoring.threshold_buffer_db
                            self.display.update_threshold_display(self.current_threshold_buffer)
                        elif key_name == 's':
                            # Show statistics
                            stats = self.get_statistics()
                            self.display.print_statistics(stats)
                
                time.sleep(0.1)
                
        except Exception as e:
            self.display.print_warning(f"Keyboard monitoring error: {e}")
    
    def run(self) -> bool:
        """Run monitoring mode.
        
        Returns:
            True if monitoring completed successfully, False otherwise
        """
        try:
            # Display header
            self.display.clear()
            self.display.print_header("HackRF Spectrum Monitor - Monitoring Mode")
            
            # Load baselines
            if not self._load_baselines():
                self.display.print_error("Failed to load baseline data. Run learning mode first.")
                return False
            
            # Display configuration
            config_info = {
                'freq_min': self.config.spectrum.freq_min_mhz,
                'freq_max': self.config.spectrum.freq_max_mhz,
                'baseline_file': self.config.get_baseline_file_path(),
                'threshold_buffer': self.current_threshold_buffer
            }
            self.display.print_config_info(config_info)
            
            # Display baseline info
            metadata = self.storage.get_metadata()
            if metadata:
                baseline_info = metadata.get('baseline_stats', {})
                print(f"Baseline Coverage: {metadata.get('num_frequency_bins', 0)} frequency bins")
                print(f"Learned from: {metadata.get('num_sweeps_learned', 0)} sweeps")
                print(f"Created: {metadata.get('creation_date', 'Unknown')}")
                print()
            
            # Display controls
            self.display.print_controls('monitoring')
            
 
            
            print("Monitoring for signals exceeding learned baselines...")
            print()
            
            # Initialize monitoring state
            self.is_monitoring = True
            self.should_stop = False
            self.start_time = time.time()
            self.sweep_count = 0
            self.active_alerts = {}
            self.alert_history = []
            self.total_alerts = 0
            self.display.reset_alert_count()
            
            # Start keyboard monitoring thread
            self.keyboard_thread = threading.Thread(target=self._keyboard_monitor)
            self.keyboard_thread.daemon = True
            self.keyboard_thread.start()
            
            # Start HackRF sweep

            self.hackrf.start_sweep()
            
            # Wait for completion or stop signal
            try:
                while self.is_monitoring and not self.should_stop:
                    time.sleep(0.1)
                
            except KeyboardInterrupt:
                self.display.print_info("Monitoring interrupted by user")
                self.should_stop = True
            
            # Stop sweep
            self.hackrf.stop_sweep()
            self.is_monitoring = False
            
            # Calculate duration
            duration = time.time() - self.start_time
            
            # Display completion message
            self.display.print_completion_message(
                'monitoring',
                '',
                self.sweep_count,
                duration
            )
            
            # Display final statistics
            final_stats = self.get_statistics()
            final_stats['total_duration_s'] = duration
            self.display.print_statistics(final_stats)
            
            return True
            
        except Exception as e:
            self.display.print_error(f"Monitoring mode error: {e}")
            return False
        finally:
            self.cleanup()
    
    def stop(self):
        """Stop monitoring mode."""
        self.should_stop = True
        self.is_monitoring = False
    
    def cleanup(self):
        """Clean up resources."""
        try:
            self.is_monitoring = False
            self.should_stop = True
            
            if self.hackrf:
                self.hackrf.stop_sweep()
            
            # Wait for keyboard thread to finish
            if self.keyboard_thread and self.keyboard_thread.is_alive():
                self.keyboard_thread.join(timeout=1.0)
                
        except Exception as e:
            self.display.print_warning(f"Cleanup error: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current monitoring statistics.
        
        Returns:
            Dictionary with current statistics
        """
        with self.data_lock:
            stats = {
                'sweep_count': self.sweep_count,
                'sweep_rate_hz': self.sweep_rate,
                'threshold_buffer_db': self.current_threshold_buffer,
                'active_alerts': len(self.active_alerts),
                'total_alerts_displayed': self.display.get_alert_count(),
                'total_alert_events': self.total_alerts,
                'alert_history_length': len(self.alert_history)
            }
            
            if self.baseline_frequencies is not None:
                stats.update({
                    'baseline_frequency_bins': len(self.baseline_frequencies),
                    'baseline_freq_range_mhz': [
                        float(self.baseline_frequencies.min()),
                        float(self.baseline_frequencies.max())
                    ]
                })
            
            if self.start_time > 0:
                stats['elapsed_time_s'] = time.time() - self.start_time
            
            # Alert duration statistics
            if self.alert_history:
                durations = [alert.get_duration() for alert in self.alert_history]
                stats.update({
                    'avg_alert_duration_s': np.mean(durations),
                    'max_alert_duration_s': np.max(durations),
                    'min_alert_duration_s': np.min(durations)
                })
            
            return stats
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of alert activity.
        
        Returns:
            Dictionary with alert summary
        """
        summary = {
            'total_alerts': len(self.alert_history),
            'active_alerts': len(self.active_alerts),
            'alert_frequencies': []
        }
        
        # Frequency distribution of alerts
        freq_counts = {}
        for alert in self.alert_history:
            freq_rounded = round(alert.frequency, 1)
            freq_counts[freq_rounded] = freq_counts.get(freq_rounded, 0) + 1
        
        # Sort by frequency
        sorted_freqs = sorted(freq_counts.items())
        summary['alert_frequencies'] = [
            {'frequency_mhz': freq, 'count': count}
            for freq, count in sorted_freqs
        ]
        
        return summary 