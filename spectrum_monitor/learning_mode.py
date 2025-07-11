"""
Learning Mode Module
Implements spectrum learning functionality to establish baseline power profiles.
"""

import numpy as np
import time
import threading
from typing import Optional, Dict, Any, Tuple
import keyboard

from hackrf_interface import HackRFInterface
from storage import BaselineStorage
from display import CLIDisplay
from config import Configuration


class LearningMode:
    """Implements learning mode to establish baseline spectrum profiles."""
    
    def __init__(self, config: Configuration, display: CLIDisplay):
        """Initialize learning mode.
        
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
        
        # Learning state
        self.is_learning = False
        self.should_stop = False
        self.start_time = 0
        
        # Spectrum data collection
        self.power_history = []
        self.current_frequencies = None
        self.max_power_levels = None
        self.sweep_count = 0
        
        # Statistics
        self.new_maxima_count = 0
        self.last_sweep_time = 0
        self.sweep_rate = 0.0
        
        # Thread synchronization
        self.data_lock = threading.Lock()
        self.keyboard_thread = None
        
        # Configure HackRF
        self._configure_hackrf()
    
    def _configure_hackrf(self):
        """Configure HackRF parameters from config."""
        print(f"DEBUG: Learning mode configuring HackRF...")
        
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
    
    def _on_spectrum_data(self, frequencies: np.ndarray, power_levels: np.ndarray):
        """Callback for new spectrum data.
        
        Args:
            frequencies: Frequency array in MHz
            power_levels: Power levels in dB
        """
        with self.data_lock:
            if not self.is_learning:
                return
            
            # Initialize or update frequency coverage
            if self.current_frequencies is None:
                # First segment - initialize arrays
                self.current_frequencies = frequencies.copy()
                self.max_power_levels = power_levels.copy()
                self.new_maxima_count = len(frequencies)
            else:
                # Subsequent segments - merge frequency ranges
                # Combine frequencies and power levels, handling overlaps
                combined_freq, combined_power, combined_max = self._merge_frequency_segments(
                    self.current_frequencies, self.max_power_levels,
                    frequencies, power_levels
                )
                
                # Count new maxima
                if len(combined_max) == len(self.max_power_levels):
                    new_maxima_mask = combined_max > self.max_power_levels
                    self.new_maxima_count = np.sum(new_maxima_mask)
                else:
                    # Length changed due to new frequency bins
                    old_power_interp = np.interp(combined_freq, self.current_frequencies, self.max_power_levels, 
                                                left=-np.inf, right=-np.inf)
                    new_maxima_mask = combined_max > old_power_interp
                    self.new_maxima_count = np.sum(new_maxima_mask & (old_power_interp > -np.inf))
                
                # Update stored arrays
                self.current_frequencies = combined_freq
                self.max_power_levels = combined_max
            
            # Store power history (limit to configured history size)
            self.power_history.append(self.max_power_levels.copy())
            if len(self.power_history) > self.config.storage.learning_history:
                self.power_history.pop(0)
            
            # Update statistics
            self.sweep_count += 1
            current_time = time.time()
            if self.last_sweep_time > 0:
                self.sweep_rate = 1.0 / (current_time - self.last_sweep_time)
            self.last_sweep_time = current_time
            
            # Update display
            self._update_display()
    
    def _merge_frequency_segments(self, freq1: np.ndarray, power1: np.ndarray, 
                                 freq2: np.ndarray, power2: np.ndarray) -> tuple:
        """Merge two frequency segments, handling overlaps.
        
        Args:
            freq1, power1: First frequency segment
            freq2, power2: Second frequency segment
            
        Returns:
            Combined frequency array, combined power array, combined max power array
        """
        # Combine all frequencies and sort
        all_freqs = np.concatenate([freq1, freq2])
        all_powers_1 = np.concatenate([power1, np.full(len(freq2), -np.inf)])
        all_powers_2 = np.concatenate([np.full(len(freq1), -np.inf), power2])
        
        # Sort by frequency
        sort_indices = np.argsort(all_freqs)
        sorted_freqs = all_freqs[sort_indices]
        sorted_powers_1 = all_powers_1[sort_indices]
        sorted_powers_2 = all_powers_2[sort_indices]
        
        # Remove duplicates and interpolate missing values
        unique_freqs, unique_indices = np.unique(sorted_freqs, return_index=True)
        
        # Interpolate power values for each segment to the unique frequency grid
        power1_interp = np.interp(unique_freqs, freq1, power1, left=-np.inf, right=-np.inf)
        power2_interp = np.interp(unique_freqs, freq2, power2, left=-np.inf, right=-np.inf)
        
        # Take the maximum of available power values
        combined_power = np.maximum(power1_interp, power2_interp)
        
        # Only keep frequencies where we have valid data
        valid_mask = (power1_interp > -np.inf) | (power2_interp > -np.inf)
        
        return unique_freqs[valid_mask], combined_power[valid_mask], combined_power[valid_mask]
            
    def _update_display(self):
        """Update the learning mode display."""
        total_bins = len(self.current_frequencies) if self.current_frequencies is not None else 0
        
        self.display.print_learning_status(
            self.sweep_count,
            self.new_maxima_count,
            total_bins,
            self.sweep_rate
        )
    
    def _keyboard_monitor(self):
        """Monitor for keyboard input to stop learning."""
        try:
            while self.is_learning and not self.should_stop:
                # Check for any key press
                if keyboard.read_event():
                    event = keyboard.read_event()
                    if event.event_type == keyboard.KEY_DOWN:
                        self.should_stop = True
                        break
                time.sleep(0.1)
        except Exception as e:
            self.display.print_warning(f"Keyboard monitoring error: {e}")
            # Fallback to time-based stop or user interrupt
    
    def run(self) -> bool:
        """Run learning mode.
        
        Returns:
            True if learning completed successfully, False otherwise
        """
        try:
            # Display header
            self.display.clear()
            self.display.print_header("HackRF Spectrum Monitor - Learning Mode")
            
            # Display configuration
            config_info = {
                'freq_min': self.config.spectrum.freq_min_mhz,
                'freq_max': self.config.spectrum.freq_max_mhz,
                'baseline_file': self.config.get_baseline_file_path()
            }
            self.display.print_config_info(config_info)
            
            # Display controls
            self.display.print_controls('learning')

            
            print("Scanning spectrum... Press any key to stop and save baselines.")
            print()
            
            # Initialize learning state
            self.is_learning = True
            self.should_stop = False
            self.start_time = time.time()
            self.sweep_count = 0
            self.power_history = []
            self.current_frequencies = None
            self.max_power_levels = None
            
            # Start keyboard monitoring thread
            self.keyboard_thread = threading.Thread(target=self._keyboard_monitor)
            self.keyboard_thread.daemon = True
            self.keyboard_thread.start()
            

            self.hackrf.start_sweep()
            
            # Wait for completion or stop signal
            try:
                while self.is_learning and not self.should_stop:
                    time.sleep(0.1)
                    
                    # Check if we've collected enough data
                    if (len(self.power_history) >= self.config.storage.learning_history and 
                        self.new_maxima_count == 0):
                        # No new maxima found and we have enough data
                        self.display.print_info("No new maxima detected - learning may be complete")
                
            except KeyboardInterrupt:
                self.display.print_info("Learning interrupted by user")
                self.should_stop = True
            
            # Stop sweep
            self.hackrf.stop_sweep()
            self.is_learning = False
            
            # Calculate duration
            duration = time.time() - self.start_time
            
            # Save baselines if we have data
            if self.power_history and self.current_frequencies is not None:
                success = self._save_baselines(duration)
                
                # Display completion message
                self.display.print_completion_message(
                    'learning',
                    self.config.get_baseline_file_path(),
                    self.sweep_count,
                    duration
                )
                
                return success
            else:
                self.display.print_error("No spectrum data collected - cannot save baselines")
                return False
                
        except Exception as e:
            self.display.print_error(f"Learning mode error: {e}")
            return False
        finally:
            self.cleanup()
    
    def _save_baselines(self, duration: float) -> bool:
        """Save collected baseline data.
        
        Args:
            duration: Learning duration in seconds
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Convert power history to numpy array
            power_array = np.array(self.power_history)
            
            # Prepare metadata
            metadata = {
                'learning_duration_s': duration,
                'learning_mode': 'spectrum_monitor',
                'hackrf_config': {
                    'lna_gain': self.config.hackrf.lna_gain,
                    'vga_gain': self.config.hackrf.vga_gain,
                    'amp_enable': self.config.hackrf.amp_enable,
                    'antenna_enable': self.config.hackrf.antenna_enable,
                    'bin_width': self.config.spectrum.bin_width
                },
                'final_stats': {
                    'total_sweeps': self.sweep_count,
                    'average_sweep_rate_hz': self.sweep_rate,
                    'final_new_maxima': self.new_maxima_count
                }
            }
            
            # Save baselines
            return self.storage.save_baselines(
                self.current_frequencies,
                power_array,
                metadata
            )
            
        except Exception as e:
            self.display.print_error(f"Error saving baselines: {e}")
            return False
    
    def stop(self):
        """Stop learning mode."""
        self.should_stop = True
        self.is_learning = False
    
    def cleanup(self):
        """Clean up resources."""
        try:
            self.is_learning = False
            self.should_stop = True
            
            if self.hackrf:
                self.hackrf.stop_sweep()
            
            # Wait for keyboard thread to finish
            if self.keyboard_thread and self.keyboard_thread.is_alive():
                self.keyboard_thread.join(timeout=1.0)
                
        except Exception as e:
            self.display.print_warning(f"Cleanup error: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current learning statistics.
        
        Returns:
            Dictionary with current statistics
        """
        with self.data_lock:
            stats = {
                'sweep_count': self.sweep_count,
                'sweep_rate_hz': self.sweep_rate,
                'new_maxima_last_sweep': self.new_maxima_count,
                'power_history_length': len(self.power_history),
                'frequency_bins': len(self.current_frequencies) if self.current_frequencies is not None else 0
            }
            
            if self.max_power_levels is not None:
                stats.update({
                    'min_power_db': float(self.max_power_levels.min()),
                    'max_power_db': float(self.max_power_levels.max()),
                    'mean_power_db': float(self.max_power_levels.mean()),
                    'std_power_db': float(self.max_power_levels.std())
                })
            
            if self.start_time > 0:
                stats['elapsed_time_s'] = time.time() - self.start_time
            
            return stats 