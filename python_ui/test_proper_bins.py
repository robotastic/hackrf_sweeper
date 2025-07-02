#!/usr/bin/env python3
"""
Test with proper 1 MHz bins to see if frequency range works correctly.
"""

import sys
import os
import time
import numpy as np
from PyQt5.QtWidgets import QApplication
from hackrf_interface import HackRFInterface, HackRFSweepConfig


def test_full_range_with_proper_bins():
    """Test full range sweep with 1 MHz bins like the UI default."""
    
    # Set up Qt application for signal processing
    if 'QT_QPA_PLATFORM' not in os.environ:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    interface = HackRFInterface()
    
    # Configure for full range with 1 MHz bins (like UI default)
    config = HackRFSweepConfig()
    config.freq_min_mhz = 100
    config.freq_max_mhz = 6000
    config.lna_gain = 16
    config.vga_gain = 20
    config.bin_width = 1000000  # 1 MHz bins - same as UI default
    config.one_shot = False
    
    interface.update_config(config)
    
    print("Testing Full Range with 1 MHz Bins")
    print("=" * 50)
    print(f"Configuration:")
    print(f"  Frequency range: {config.freq_min_mhz} - {config.freq_max_mhz} MHz")
    print(f"  Bin width: {config.bin_width} Hz")
    print(f"  Expected FFT size: {20000000 // config.bin_width}")
    print(f"  Expected frequency span: {config.freq_max_mhz - config.freq_min_mhz} MHz")
    
    # Validate configuration
    valid, message = interface.validate_config()
    if not valid:
        print(f"❌ Configuration invalid: {message}")
        return False
    
    print(f"✅ Configuration valid")
    
    # Collect data
    received_data = []
    frequency_seen = set()
    
    def on_spectrum_data(frequencies, powers):
        received_data.append({
            'frequencies': frequencies.copy(),
            'powers': powers.copy(),
            'min_freq': np.min(frequencies),
            'max_freq': np.max(frequencies),
            'num_points': len(frequencies)
        })
        
        # Track all frequencies we've seen
        frequency_seen.update(frequencies)
        
        if len(received_data) <= 5:
            print(f"  Update #{len(received_data)}: "
                  f"{len(frequencies)} points, "
                  f"range {np.min(frequencies):.1f}-{np.max(frequencies):.1f} MHz")
    
    def on_status_change(message):
        print(f"  Status: {message}")
    
    def on_error(message):
        print(f"  Error: {message}")
    
    # Connect signals
    interface.spectrum_data_ready.connect(on_spectrum_data)
    interface.sweep_status_changed.connect(on_status_change)
    interface.error_occurred.connect(on_error)
    
    try:
        print(f"\nStarting real hardware sweep...")
        interface.start_sweep()
        
        # Collect data for longer to see if it sweeps through the range
        start_time = time.time()
        while time.time() - start_time < 10.0 and len(received_data) < 20:
            app.processEvents()
            time.sleep(0.1)
        
        # Stop sweep
        interface.stop_sweep()
        app.processEvents()
        
        # Analyze results
        print(f"\nAnalysis after {time.time() - start_time:.1f} seconds:")
        print(f"  Total updates received: {len(received_data)}")
        
        if received_data:
            all_frequencies = list(frequency_seen)
            if all_frequencies:
                freq_min = min(all_frequencies)
                freq_max = max(all_frequencies)
                freq_span = freq_max - freq_min
                
                print(f"  Frequency range covered: {freq_min:.1f} - {freq_max:.1f} MHz")
                print(f"  Total frequency span: {freq_span:.1f} MHz")
                print(f"  Unique frequencies seen: {len(all_frequencies)}")
                
                expected_span = config.freq_max_mhz - config.freq_min_mhz
                coverage_percent = (freq_span / expected_span) * 100
                
                print(f"  Range coverage: {coverage_percent:.1f}% of expected {expected_span} MHz")
                
                if coverage_percent > 90:
                    print(f"  ✅ Excellent coverage - full range sweep working!")
                    return True
                elif coverage_percent > 50:
                    print(f"  ⚠️  Partial coverage - sweep working but limited")
                elif coverage_percent > 10:
                    print(f"  ❌ Poor coverage - sweep mostly limited to small range")
                else:
                    print(f"  ❌ Very poor coverage - sweep stuck in tiny range")
                
                # Check if it's progressing through the range
                if len(received_data) >= 2:
                    first_center = np.mean([received_data[0]['min_freq'], received_data[0]['max_freq']])
                    last_center = np.mean([received_data[-1]['min_freq'], received_data[-1]['max_freq']])
                    progression = last_center - first_center
                    
                    print(f"  Frequency progression: {progression:.1f} MHz over {len(received_data)} updates")
                    
                    if progression > 100:
                        print(f"  ✅ Good progression - sweep is advancing through range")
                    elif progression > 10:
                        print(f"  ⚠️  Slow progression - sweep advancing but slowly")
                    else:
                        print(f"  ❌ No progression - sweep stuck in same area")
            else:
                print(f"  ❌ No frequency data received")
                return False
        else:
            print(f"  ❌ No spectrum data received")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False
    
    finally:
        # Disconnect signals
        interface.spectrum_data_ready.disconnect()
        interface.sweep_status_changed.disconnect()
        interface.error_occurred.disconnect()
    
    return False


if __name__ == "__main__":
    success = test_full_range_with_proper_bins()
    if success:
        print(f"\n🎉 Full range sweep is working correctly!")
    else:
        print(f"\n⚠️  Full range sweep has issues that need to be addressed.")
    
    sys.exit(0 if success else 1) 