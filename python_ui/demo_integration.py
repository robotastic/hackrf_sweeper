#!/usr/bin/env python3
"""
HackRF Spectrum Analyzer Integration Demo
Demonstrates the real library integration without GUI.
"""

import sys
import time
import signal
import numpy as np
from hackrf_interface import HackRFInterface, HackRFSweepConfig


class SpectrumDemo:
    """Demo class to show HackRF integration without GUI."""
    
    def __init__(self):
        self.interface = HackRFInterface()
        self.running = False
        self.spectrum_count = 0
        
        # Setup signal handler for clean exit
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        print("\nReceived interrupt signal. Stopping...")
        self.stop()
        
    def on_spectrum_data(self, frequencies, powers):
        """Handle received spectrum data."""
        self.spectrum_count += 1
        
        # Calculate some basic statistics
        min_freq = frequencies[0]
        max_freq = frequencies[-1]
        min_power = np.min(powers)
        max_power = np.max(powers)
        avg_power = np.mean(powers)
        
        # Find peak signal
        peak_idx = np.argmax(powers)
        peak_freq = frequencies[peak_idx]
        peak_power = powers[peak_idx]
        
        print(f"\rSpectrum #{self.spectrum_count:4d} | "
              f"Range: {min_freq:6.1f}-{max_freq:6.1f} MHz | "
              f"Power: {min_power:5.1f} to {max_power:5.1f} dB | "
              f"Peak: {peak_freq:6.1f} MHz @ {peak_power:5.1f} dB", 
              end="", flush=True)
    
    def on_status_change(self, message):
        """Handle status messages."""
        print(f"\n[STATUS] {message}")
        
    def on_error(self, message):
        """Handle error messages."""
        print(f"\n[ERROR] {message}")
        
    def on_stats_update(self, sweep_count, sweep_rate, data_rate):
        """Handle statistics updates."""
        print(f"\n[STATS] Sweeps: {sweep_count}, Rate: {sweep_rate:.1f}/s, Data: {data_rate:.1f} KB/s")
    
    def configure_sweep(self):
        """Configure sweep parameters."""
        config = HackRFSweepConfig()
        
        # Configure for a reasonable demo
        config.freq_min_mhz = 88      # FM radio band start
        config.freq_max_mhz = 108     # FM radio band end
        config.lna_gain = 16          # Moderate LNA gain
        config.vga_gain = 20          # Moderate VGA gain
        config.bin_width = 100000     # 100 kHz bins for good resolution
        config.fftw_plan_type = "measure"  # Good balance of speed vs accuracy
        config.amp_enable = False     # Start with amp disabled
        config.antenna_enable = False # No antenna power
        
        self.interface.update_config(config)
        
        print("Sweep Configuration:")
        print(f"  Frequency Range: {config.freq_min_mhz} - {config.freq_max_mhz} MHz")
        print(f"  LNA Gain: {config.lna_gain} dB")
        print(f"  VGA Gain: {config.vga_gain} dB")
        print(f"  FFT Bin Width: {config.bin_width} Hz")
        print(f"  FFTW Plan: {config.fftw_plan_type}")
        
    def start(self):
        """Start the spectrum sweep demo."""
        print("HackRF Spectrum Analyzer Integration Demo")
        print("=" * 50)
        
        # Set up Qt application for signal processing
        from PyQt5.QtWidgets import QApplication
        import os
        
        # Set offscreen platform for headless operation
        if 'QT_QPA_PLATFORM' not in os.environ:
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Check library status
        print(f"HackRF Library: {'✅ Loaded' if self.interface.hackrf_lib else '❌ Failed'}")
        print(f"Sweeper Library: {'✅ Loaded' if self.interface.sweeper_lib else '❌ Failed'}")
        
        if self.interface.sweeper_lib and hasattr(self.interface.sweeper_lib, 'hackrf_sweep_easy_init'):
            print("🎯 Real HackRF integration available")
        else:
            print("🔄 Using simulation mode")
        
        print()
        
        # Configure sweep
        self.configure_sweep()
        
        # Validate configuration
        valid, message = self.interface.validate_config()
        if not valid:
            print(f"❌ Configuration error: {message}")
            return False
        
        print("✅ Configuration valid")
        print()
        
        # Connect signals
        self.interface.spectrum_data_ready.connect(self.on_spectrum_data)
        self.interface.sweep_status_changed.connect(self.on_status_change)
        self.interface.error_occurred.connect(self.on_error)
        self.interface.sweep_stats_updated.connect(self.on_stats_update)
        
        # Start sweep
        print("Starting spectrum sweep...")
        print("Press Ctrl+C to stop")
        print("-" * 50)
        
        self.running = True
        self.interface.start_sweep()
        
        # Run until stopped, processing Qt events
        try:
            while self.running and self.interface.is_running:
                app.processEvents()
                time.sleep(0.01)
        except KeyboardInterrupt:
            self.signal_handler(signal.SIGINT, None)
        
        return True
    
    def stop(self):
        """Stop the demo."""
        self.running = False
        if self.interface.is_running:
            self.interface.stop_sweep()
        
        print(f"\n\nDemo completed. Processed {self.spectrum_count} spectrum updates.")


def main():
    """Main demo function."""
    demo = SpectrumDemo()
    
    # Check if we should force simulation mode
    force_sim = '--sim' in sys.argv or '--simulation' in sys.argv
    if force_sim:
        print("Forcing simulation mode...")
        # Monkey patch to force simulation
        original_start = demo.interface.start_sweep
        demo.interface.start_sweep = lambda: original_start(force_simulation=True)
    
    try:
        success = demo.start()
        return 0 if success else 1
    except Exception as e:
        print(f"\nDemo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        demo.stop()


if __name__ == "__main__":
    sys.exit(main()) 