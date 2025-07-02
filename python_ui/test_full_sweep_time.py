#!/usr/bin/env python3
"""
Test if the sweep completes the full range when given enough time.
"""

import sys
import os
import time
import numpy as np
from PyQt5.QtWidgets import QApplication
from hackrf_interface import HackRFInterface, HackRFSweepConfig


def test_full_sweep_completion():
    """Test if sweep completes full range when given sufficient time."""
    
    # Set up Qt application for signal processing
    if 'QT_QPA_PLATFORM' not in os.environ:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    interface = HackRFInterface()
    
    # Configure for full range with 1 MHz bins
    config = HackRFSweepConfig()
    config.freq_min_mhz = 100
    config.freq_max_mhz = 6000
    config.lna_gain = 16
    config.vga_gain = 20
    config.bin_width = 1000000  # 1 MHz bins
    config.one_shot = False
    
    interface.update_config(config)
    
    print("Testing Full Sweep Completion (60 second test)")
    print("=" * 60)
    print(f"Configuration: {config.freq_min_mhz}-{config.freq_max_mhz} MHz, {config.bin_width} Hz bins")
    
    # Validate configuration
    valid, message = interface.validate_config()
    if not valid:
        print(f"❌ Configuration invalid: {message}")
        return False
    
    # Collect data
    received_data = []
    frequency_seen = set()
    last_update_time = time.time()
    max_freq_seen = 0
    frequency_milestones = [500, 1000, 2000, 3000, 4000, 5000, 6000]
    milestones_reached = []
    
    def on_spectrum_data(frequencies, powers):
        nonlocal last_update_time, max_freq_seen
        
        received_data.append({
            'min_freq': np.min(frequencies),
            'max_freq': np.max(frequencies),
            'num_points': len(frequencies)
        })
        
        # Track all frequencies and the maximum
        frequency_seen.update(frequencies)
        current_max = np.max(frequencies)
        if current_max > max_freq_seen:
            max_freq_seen = current_max
        
        # Check for milestones
        for milestone in frequency_milestones:
            if milestone not in milestones_reached and current_max >= milestone:
                milestones_reached.append(milestone)
                elapsed = time.time() - start_time
                print(f"  🎯 Reached {milestone} MHz at {elapsed:.1f}s")
        
        last_update_time = time.time()
        
        # Periodic progress updates
        if len(received_data) % 100 == 0:
            elapsed = time.time() - start_time
            span = max_freq_seen - config.freq_min_mhz
            progress = (span / (config.freq_max_mhz - config.freq_min_mhz)) * 100
            rate = span / elapsed if elapsed > 0 else 0
            print(f"  📈 Update {len(received_data)}: {max_freq_seen:.0f} MHz "
                  f"({progress:.1f}% coverage, {rate:.0f} MHz/s)")
    
    def on_status_change(message):
        if "running" in message.lower():
            print(f"  ✅ {message}")
        else:
            print(f"  📢 {message}")
    
    def on_error(message):
        print(f"  ❌ Error: {message}")
    
    # Connect signals
    interface.spectrum_data_ready.connect(on_spectrum_data)
    interface.sweep_status_changed.connect(on_status_change)
    interface.error_occurred.connect(on_error)
    
    try:
        print(f"\nStarting sweep at {time.strftime('%H:%M:%S')}...")
        start_time = time.time()
        interface.start_sweep()
        
        # Monitor for up to 60 seconds or until we reach the end
        target_coverage = 95  # Consider "complete" at 95% coverage
        
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            
            app.processEvents()
            time.sleep(0.05)
            
            # Check stopping conditions
            if elapsed >= 60.0:
                print(f"\n  ⏰ Time limit reached (60 seconds)")
                break
            
            if max_freq_seen >= config.freq_max_mhz * 0.95:
                print(f"\n  🎉 Near completion! Reached {max_freq_seen:.0f} MHz")
                break
            
            # Check if sweep has stalled (no updates for 5 seconds)
            if current_time - last_update_time > 5.0:
                print(f"\n  ⚠️  Sweep appears stalled (no updates for 5s)")
                break
        
        # Stop sweep
        interface.stop_sweep()
        app.processEvents()
        
        # Final analysis
        print(f"\n" + "=" * 60)
        print("FINAL ANALYSIS")
        print("=" * 60)
        
        elapsed_total = time.time() - start_time
        print(f"Total time: {elapsed_total:.1f} seconds")
        print(f"Total updates: {len(received_data)}")
        
        if frequency_seen:
            freq_min = min(frequency_seen)
            freq_max = max(frequency_seen)
            freq_span = freq_max - freq_min
            expected_span = config.freq_max_mhz - config.freq_min_mhz
            coverage_percent = (freq_span / expected_span) * 100
            
            print(f"Frequency range: {freq_min:.1f} - {freq_max:.1f} MHz")
            print(f"Frequency span: {freq_span:.1f} MHz")
            print(f"Coverage: {coverage_percent:.1f}% of {expected_span} MHz")
            print(f"Sweep rate: {freq_span / elapsed_total:.1f} MHz/s")
            print(f"Unique frequencies: {len(frequency_seen):,}")
            
            print(f"\nMilestones reached:")
            for milestone in frequency_milestones:
                status = "✅" if milestone in milestones_reached else "❌"
                print(f"  {status} {milestone} MHz")
            
            # Assessment
            if coverage_percent >= 95:
                print(f"\n🎉 EXCELLENT: Full range sweep completed successfully!")
                return True
            elif coverage_percent >= 80:
                print(f"\n✅ GOOD: Near-complete coverage achieved")
                return True
            elif coverage_percent >= 50:
                print(f"\n⚠️  PARTIAL: Significant coverage but incomplete")
                return False
            else:
                print(f"\n❌ POOR: Limited coverage")
                return False
        else:
            print(f"❌ No frequency data received")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False
    
    finally:
        interface.spectrum_data_ready.disconnect()
        interface.sweep_status_changed.disconnect()
        interface.error_occurred.disconnect()


if __name__ == "__main__":
    success = test_full_sweep_completion()
    if success:
        print(f"\n🎉 Full range sweep is working correctly!")
    else:
        print(f"\n⚠️  Full range sweep needs more investigation.")
    
    sys.exit(0 if success else 1) 