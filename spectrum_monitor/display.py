"""
Display Module
Handles CLI output, status updates, and alert notifications.
"""

import os
import sys
import time
from typing import List, Dict, Any, Optional
from termcolor import colored
import threading


class CLIDisplay:
    """Manages command-line interface display and alerts."""
    
    def __init__(self, show_frequency_mhz: bool = True, precision_digits: int = 1, 
                 power_precision: int = 1, alert_beep: bool = False):
        """Initialize CLI display.
        
        Args:
            show_frequency_mhz: Show frequencies in MHz vs Hz
            precision_digits: Decimal places for frequency display
            power_precision: Decimal places for power display
            alert_beep: Enable audio beep on alerts
        """
        self.show_frequency_mhz = show_frequency_mhz
        self.precision_digits = precision_digits
        self.power_precision = power_precision
        self.alert_beep = alert_beep
        
        # Terminal control
        self.clear_screen = True
        self.use_colors = True
        
        # Status tracking
        self.last_status_line = ""
        self.alert_count = 0
        self.display_lock = threading.Lock()
        
        # Check terminal capabilities
        self._check_terminal_capabilities()
    
    def _check_terminal_capabilities(self):
        """Check if terminal supports colors and clearing."""
        try:
            # Check if stdout is a terminal
            if not sys.stdout.isatty():
                self.use_colors = False
                self.clear_screen = False
                return
            
            # Check TERM environment variable
            term = os.environ.get('TERM', '').lower()
            if 'color' not in term and term not in ['xterm', 'xterm-256color', 'screen']:
                self.use_colors = False
                
        except Exception:
            self.use_colors = False
            self.clear_screen = False
    
    def clear(self):
        """Clear the terminal screen."""
        if self.clear_screen:
            os.system('clear' if os.name == 'posix' else 'cls')
    
    def print_header(self, title: str, subtitle: str = "", width: int = 80):
        """Print a formatted header.
        
        Args:
            title: Main title text
            subtitle: Optional subtitle
            width: Total width of header
        """
        with self.display_lock:
            separator = "=" * width
            
            if self.use_colors:
                print(colored(separator, 'cyan'))
                print(colored(title.center(width), 'cyan', attrs=['bold']))
                if subtitle:
                    print(colored(subtitle.center(width), 'cyan'))
                print(colored(separator, 'cyan'))
            else:
                print(separator)
                print(title.center(width))
                if subtitle:
                    print(subtitle.center(width))
                print(separator)
    
    def print_config_info(self, config_info: Dict[str, Any]):
        """Print configuration information.
        
        Args:
            config_info: Dictionary with configuration details
        """
        with self.display_lock:
            print(f"Frequency Range: {config_info.get('freq_min', 0):.1f} - "
                  f"{config_info.get('freq_max', 0):.1f} MHz")
            print(f"Baseline File: {config_info.get('baseline_file', 'None')}")
            
            if 'threshold_buffer' in config_info:
                print(f"Threshold Buffer: {config_info['threshold_buffer']:.1f} dB")
            
            print()
    
    def print_learning_status(self, sweep_count: int, new_maxima: int, 
                            total_bins: int, sweep_rate: float = 0.0):
        """Print learning mode status.
        
        Args:
            sweep_count: Number of sweeps completed
            new_maxima: Number of new maxima found in last sweep
            total_bins: Total number of frequency bins
            sweep_rate: Sweeps per second
        """
        with self.display_lock:
            percentage = (new_maxima / total_bins * 100) if total_bins > 0 else 0
            
            rate_str = f" ({sweep_rate:.1f} Hz)" if sweep_rate > 0 else ""
            

            status_line = (f"Sweep {sweep_count}{rate_str}: {new_maxima} new maxima found "
                          f"({percentage:.1f}% bins updated)")
            if new_maxima > 0:
                if self.use_colors:
                    # Color code based on percentage of new maxima
                    if percentage > 50:
                        color = 'green'
                    elif percentage > 20:
                        color = 'yellow' 
                    else:
                        color = 'red'
                    print(colored(status_line, color))
                else:
                    print(status_line)
            
            self.last_status_line = status_line
    
    def print_monitoring_status(self, sweep_count: int, threshold_buffer: float, 
                              sweep_rate: float = 0.0, alerts_detected: int = 0):
        """Print monitoring mode status.
        
        Args:
            sweep_count: Number of sweeps completed
            threshold_buffer: Current threshold buffer in dB
            sweep_rate: Sweeps per second
            alerts_detected: Number of alerts in current session
        """
        with self.display_lock:
            rate_str = f" ({sweep_rate:.1f} Hz)" if sweep_rate > 0 else ""
            
            if alerts_detected == 0:
                status_msg = "No alerts detected"
                color = 'green' if self.use_colors else None
            else:
                status_msg = f"{alerts_detected} alerts detected"
                color = 'yellow' if self.use_colors else None
            
            status_line = (f"Sweep {sweep_count}{rate_str} | "
                          f"Threshold: {threshold_buffer:.1f} dB | {status_msg}")
            
            if color and self.use_colors:
                print(f"\r{colored(status_line, color)}", end="", flush=True)
            else:
                print(f"\r{status_line}", end="", flush=True)
            
            self.last_status_line = status_line
    
    def print_alert(self, frequency: float, signal_power: float, baseline_power: float,
                   threshold_buffer: float, detection_time: Optional[float] = None):
        """Print an alert for detected signal.
        
        Args:
            frequency: Alert frequency in MHz
            signal_power: Detected signal power in dB
            baseline_power: Baseline power level in dB
            threshold_buffer: Current threshold buffer in dB
            detection_time: Time of detection (for timestamping)
        """
        with self.display_lock:
            self.alert_count += 1
            
            # Calculate how much above baseline and threshold
            above_baseline = signal_power - baseline_power
            above_threshold = above_baseline - threshold_buffer
            
            # Format frequency
            if self.show_frequency_mhz:
                freq_str = f"{frequency:.{self.precision_digits}f} MHz"
            else:
                freq_str = f"{frequency * 1e6:.0f} Hz"
            
            # Format powers
            signal_str = f"{signal_power:.{self.power_precision}f} dBm"
            above_baseline_str = f"{above_baseline:.{self.power_precision}f} dB"
            above_threshold_str = f"{above_threshold:.{self.power_precision}f} dB"
            
            # Create timestamp
            timestamp = time.strftime("%H:%M:%S") if detection_time is None else \
                       time.strftime("%H:%M:%S", time.localtime(detection_time))
            
            # Print alert
            print()  # New line to separate from status
            
            if self.use_colors:
                print(colored("🚨 ALERT DETECTED 🚨", 'red', attrs=['bold']))
                print(colored(f"Time: {timestamp}", 'white'))
                print(colored(f"Frequency: {freq_str}", 'white', attrs=['bold']))
                print(colored(f"Signal: {signal_str} ({above_baseline_str} above baseline)", 'white'))
                print(colored(f"Threshold exceeded by: {above_threshold_str}", 'red', attrs=['bold']))
            else:
                print("*** ALERT DETECTED ***")
                print(f"Time: {timestamp}")
                print(f"Frequency: {freq_str}")
                print(f"Signal: {signal_str} ({above_baseline_str} above baseline)")
                print(f"Threshold exceeded by: {above_threshold_str}")
            
            print()  # Blank line after alert
            
            # Audio beep if enabled
            if self.alert_beep:
                self._beep()
    
    def print_multiple_alerts(self, alerts: List[Dict[str, Any]]):
        """Print multiple alerts in a compact format.
        
        Args:
            alerts: List of alert dictionaries with keys: frequency, signal_power, 
                   baseline_power, threshold_buffer
        """
        if not alerts:
            return
        
        with self.display_lock:
            print()  # New line to separate from status
            
            timestamp = time.strftime("%H:%M:%S")
            
            if self.use_colors:
                print(colored(f"🚨 {len(alerts)} ALERTS DETECTED 🚨", 'red', attrs=['bold']))
                print(colored(f"Time: {timestamp}", 'white'))
            else:
                print(f"*** {len(alerts)} ALERTS DETECTED ***")
                print(f"Time: {timestamp}")
            
            # Print each alert in compact format
            for alert in alerts:
                freq = alert['frequency']
                signal = alert['signal_power']
                baseline = alert['baseline_power']
                buffer = alert['threshold_buffer']
                
                above_baseline = signal - baseline
                above_threshold = above_baseline - buffer
                
                if self.show_frequency_mhz:
                    freq_str = f"{freq:.{self.precision_digits}f} MHz"
                else:
                    freq_str = f"{freq * 1e6:.0f} Hz"
                
                alert_line = (f"  {freq_str}: {signal:.{self.power_precision}f} dBm "
                             f"(+{above_threshold:.{self.power_precision}f} dB)")
                
                if self.use_colors:
                    print(colored(alert_line, 'red'))
                else:
                    print(alert_line)
            
            print()  # Blank line after alerts
            
            # Audio beep if enabled
            if self.alert_beep:
                self._beep()
    
    def print_controls(self, mode: str):
        """Print available controls for the current mode.
        
        Args:
            mode: Current operating mode ('learning' or 'monitoring')
        """
        with self.display_lock:
            if mode == 'learning':
                print("Controls: Press any key to stop learning and save baselines.")
            elif mode == 'monitoring':
                controls = [
                    "[+/-] Adjust threshold",
                    "[r] Reset threshold", 
                    "[s] Show stats",
                    "[q] Quit"
                ]
                print(f"Controls: {' | '.join(controls)}")
            print()
    
    def print_statistics(self, stats: Dict[str, Any]):
        """Print current statistics.
        
        Args:
            stats: Dictionary with statistics to display
        """
        with self.display_lock:
            print()
            if self.use_colors:
                print(colored("Current Statistics:", 'cyan', attrs=['bold']))
            else:
                print("Current Statistics:")
            
            for key, value in stats.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.2f}")
                else:
                    print(f"  {key}: {value}")
            print()
    
    def print_completion_message(self, mode: str, file_path: str = "", 
                               sweep_count: int = 0, duration: float = 0):
        """Print completion message.
        
        Args:
            mode: Mode that completed ('learning' or 'monitoring')
            file_path: Path to saved file (for learning mode)
            sweep_count: Total sweeps completed
            duration: Total duration in seconds
        """
        with self.display_lock:
            print()
            
            if mode == 'learning':
                message = f"Learning completed. Saved {sweep_count} spectra to {file_path}"
                if self.use_colors:
                    print(colored(message, 'green', attrs=['bold']))
                else:
                    print(message)
            elif mode == 'monitoring':
                message = f"Monitoring stopped after {sweep_count} sweeps"
                if self.use_colors:
                    print(colored(message, 'yellow'))
                else:
                    print(message)
            
            if duration > 0:
                duration_str = f"Duration: {duration:.1f} seconds"
                if self.use_colors:
                    print(colored(duration_str, 'white'))
                else:
                    print(duration_str)
            
            print()
    
    def print_error(self, message: str):
        """Print an error message.
        
        Args:
            message: Error message to display
        """
        with self.display_lock:
            if self.use_colors:
                print(colored(f"Error: {message}", 'red', attrs=['bold']))
            else:
                print(f"Error: {message}")
    
    def print_warning(self, message: str):
        """Print a warning message.
        
        Args:
            message: Warning message to display
        """
        with self.display_lock:
            if self.use_colors:
                print(colored(f"Warning: {message}", 'yellow'))
            else:
                print(f"Warning: {message}")
    
    def print_info(self, message: str):
        """Print an info message.
        
        Args:
            message: Info message to display
        """
        with self.display_lock:
            if self.use_colors:
                print(colored(message, 'cyan'))
            else:
                print(message)
    
    def _beep(self):
        """Produce a system beep sound."""
        try:
            # Try different methods for beeping
            if os.name == 'posix':  # Unix/Linux/macOS
                os.system('printf "\\a"')
            else:  # Windows
                import winsound
                winsound.Beep(1000, 200)  # 1000 Hz for 200ms
        except Exception:
            # Fallback: print bell character
            print('\a', end='', flush=True)
    
    def update_threshold_display(self, new_threshold: float):
        """Update the displayed threshold value.
        
        Args:
            new_threshold: New threshold buffer value
        """
        with self.display_lock:
            message = f"Threshold buffer updated to {new_threshold:.1f} dB"
            if self.use_colors:
                print(f"\r{colored(message, 'yellow')}")
            else:
                print(f"\r{message}")
    
    def get_alert_count(self) -> int:
        """Get the total number of alerts displayed."""
        return self.alert_count
    
    def reset_alert_count(self):
        """Reset the alert counter."""
        self.alert_count = 0 