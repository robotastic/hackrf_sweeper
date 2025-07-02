#!/usr/bin/env python3
"""
Real vs Simulation Mode Frequency Test
Tests the difference between real hardware mode and simulation mode frequency handling.
"""

import sys
import os
import time
import numpy as np
from PyQt5.QtWidgets import QApplication
from hackrf_interface import HackRFInterface, HackRFSweepConfig


class RealVsSimTest:
    """Compare real and simulation mode frequency handling."""
    
    def __init__(self):
        # Set up Qt application for signal processing
        if 'QT_QPA_PLATFORM' not in os.environ:
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)
    
    def test_library_function_calls(self):
        """Test what happens when we try to call real library functions."""
        print("Testing Real Library Function Accessibility")
        print("=" * 50)
        
        interface = HackRFInterface()
        
        # Check library availability
        print(f"HackRF lib loaded: {'✅' if interface.hackrf_lib else '❌'}")
        print(f"Sweeper lib loaded: {'✅' if interface.sweeper_lib else '❌'}")
        
        if interface.sweeper_lib:
            # Check individual functions
            functions_to_test = [
                'hackrf_sweep_easy_init',
                'hackrf_sweep_set_range', 
                'hackrf_sweep_setup_fft',
                'hackrf_sweep_start',
                'hackrf_sweep_stop',
                'hackrf_sweep_set_fft_rx_callback'
            ]
            
            print(f"\nSweeper library functions:")
            for func_name in functions_to_test:
                has_func = hasattr(interface.sweeper_lib, func_name)
                print(f"  {func_name}: {'✅' if has_func else '❌'}")
        
        # Test HackRF device availability
        print(f"\nTesting HackRF device access:")
        if interface.hackrf_lib:
            try:
                # Try to initialize HackRF
                result = interface.hackrf_lib.hackrf_init()
                print(f"  hackrf_init() returned: {result}")
                
                if result == 0:  # HACKRF_SUCCESS
                    print("  ✅ HackRF library initialization successful")
                    
                    # Try to open a device  
                    import ctypes
                    device_ptr = ctypes.c_void_p()
                    open_result = interface.hackrf_lib.hackrf_open(ctypes.byref(device_ptr))
                    print(f"  hackrf_open() returned: {open_result}")
                    
                    if open_result == 0:
                        print("  ✅ HackRF device found and opened successfully!")
                        print("  📡 Real hardware mode should be available")
                        
                        # Close the device
                        interface.hackrf_lib.hackrf_close(device_ptr)
                        print("  Device closed.")
                    else:
                        print("  ⚠️  No HackRF device connected or accessible")
                        print("  🔄 Will fall back to simulation mode")
                    
                    # Clean up
                    interface.hackrf_lib.hackrf_exit()
                else:
                    print(f"  ❌ HackRF initialization failed (error {result})")
                    print("  🔄 Will use simulation mode")
                    
            except Exception as e:
                print(f"  ❌ Exception during HackRF testing: {e}")
        
        return interface
    
    def test_real_sweep_configuration(self, interface):
        """Test how the real sweep worker configures frequency ranges."""
        print(f"\nTesting Real Sweep Configuration")
        print("=" * 50)
        
        # Configure a test range
        config = HackRFSweepConfig()
        config.freq_min_mhz = 100
        config.freq_max_mhz = 6000
        config.lna_gain = 16
        config.vga_gain = 20
        config.bin_width = 1000000
        
        interface.update_config(config)
        
        print(f"Configuration set:")
        print(f"  Frequency range: {config.freq_min_mhz} - {config.freq_max_mhz} MHz")
        print(f"  LNA gain: {config.lna_gain} dB")
        print(f"  VGA gain: {config.vga_gain} dB")
        print(f"  Bin width: {config.bin_width} Hz")
        
        # Check stored configuration
        stored_config = interface.config
        print(f"\nStored in interface:")
        print(f"  Frequency range: {stored_config.freq_min_mhz} - {stored_config.freq_max_mhz} MHz")
        
        # Validate
        valid, message = interface.validate_config()
        print(f"  Validation: {'✅ Valid' if valid else f'❌ Invalid: {message}'}")
        
        return valid
    
    def test_sweep_mode_behavior(self, interface):
        """Test behavior differences between real and simulation modes."""
        print(f"\nTesting Sweep Mode Behavior")
        print("=" * 50)
        
        # Test data collection for both modes
        modes = [
            ("Simulation Mode", True),
            ("Real Mode (if available)", False)
        ]
        
        results = {}
        
        for mode_name, force_sim in modes:
            print(f"\n--- {mode_name} ---")
            
            # Configure for wide range test
            config = HackRFSweepConfig()
            config.freq_min_mhz = 100
            config.freq_max_mhz = 6000
            config.bin_width = 5000000  # Larger bins for faster test
            interface.update_config(config)
            
            # Collect data
            received_data = []
            
            def on_spectrum_data(frequencies, powers):
                received_data.append({
                    'frequencies': frequencies.copy(),
                    'powers': powers.copy(),
                    'min_freq': np.min(frequencies),
                    'max_freq': np.max(frequencies),
                    'num_points': len(frequencies)
                })
                
                if len(received_data) <= 2:
                    print(f"    Spectrum #{len(received_data)}: "
                          f"{len(frequencies)} points, "
                          f"range {np.min(frequencies):.1f}-{np.max(frequencies):.1f} MHz")
            
            def on_status_change(message):
                print(f"    Status: {message}")
                
            def on_error(message):
                print(f"    Error: {message}")
            
            # Connect signals
            interface.spectrum_data_ready.connect(on_spectrum_data)
            interface.sweep_status_changed.connect(on_status_change)
            interface.error_occurred.connect(on_error)
            
            try:
                # Start sweep
                if force_sim:
                    interface.start_sweep(force_simulation=True)
                else:
                    interface.start_sweep()
                
                # Collect data for a short time
                start_time = time.time()
                while time.time() - start_time < 2.0 and len(received_data) < 5:
                    self.app.processEvents()
                    time.sleep(0.01)
                
                # Stop sweep
                interface.stop_sweep()
                self.app.processEvents()
                
                # Analyze results
                if received_data:
                    first_data = received_data[0]
                    results[mode_name] = {
                        'success': True,
                        'num_updates': len(received_data),
                        'points_per_update': first_data['num_points'],
                        'min_freq': first_data['min_freq'],
                        'max_freq': first_data['max_freq'],
                        'freq_span': first_data['max_freq'] - first_data['min_freq']
                    }
                    
                    print(f"    ✅ Received {len(received_data)} updates")
                    print(f"    Frequency span: {first_data['min_freq']:.1f} - {first_data['max_freq']:.1f} MHz")
                    print(f"    Points per update: {first_data['num_points']}")
                else:
                    results[mode_name] = {'success': False}
                    print(f"    ❌ No data received")
                    
            except Exception as e:
                print(f"    ❌ Exception: {e}")
                results[mode_name] = {'success': False, 'error': str(e)}
            
            # Disconnect signals to avoid interference
            interface.spectrum_data_ready.disconnect()
            interface.sweep_status_changed.disconnect()
            interface.error_occurred.disconnect()
        
        return results
    
    def analyze_results(self, results):
        """Analyze and compare the results from different modes."""
        print(f"\n{'='*60}")
        print("SWEEP MODE COMPARISON ANALYSIS")
        print(f"{'='*60}")
        
        for mode_name, data in results.items():
            print(f"\n{mode_name}:")
            
            if data.get('success'):
                print(f"  Status: ✅ Working")
                print(f"  Frequency range: {data['min_freq']:.1f} - {data['max_freq']:.1f} MHz")
                print(f"  Frequency span: {data['freq_span']:.1f} MHz")
                print(f"  Data points: {data['points_per_update']} per update")
                print(f"  Updates received: {data['num_updates']}")
                
                # Check if it covers the expected range
                expected_span = 6000 - 100  # 5900 MHz
                actual_span = data['freq_span']
                coverage = actual_span / expected_span * 100
                
                print(f"  Range coverage: {coverage:.1f}% of expected (5900 MHz)")
                
                if coverage > 90:
                    print(f"  ✅ Good frequency coverage")
                elif coverage > 50:
                    print(f"  ⚠️  Partial frequency coverage")
                else:
                    print(f"  ❌ Poor frequency coverage")
                    
            else:
                print(f"  Status: ❌ Failed")
                if 'error' in data:
                    print(f"  Error: {data['error']}")
        
        # Compare modes
        sim_data = results.get("Simulation Mode")
        real_data = results.get("Real Mode (if available)")
        
        if sim_data and real_data and both_successful(sim_data, real_data):
            print(f"\n📊 Mode Comparison:")
            print(f"  Simulation span: {sim_data['freq_span']:.1f} MHz")
            print(f"  Real mode span:  {real_data['freq_span']:.1f} MHz")
            
            span_diff = abs(sim_data['freq_span'] - real_data['freq_span'])
            if span_diff < 100:  # Within 100 MHz
                print(f"  ✅ Spans are similar (difference: {span_diff:.1f} MHz)")
            else:
                print(f"  ⚠️  Significant span difference: {span_diff:.1f} MHz")
                print(f"      This suggests different behavior between modes")
        
        return results

def both_successful(data1, data2):
    """Check if both data sets indicate success."""
    return data1.get('success', False) and data2.get('success', False)


def main():
    """Run the real vs simulation test."""
    try:
        tester = RealVsSimTest()
        
        print("HackRF Real vs Simulation Mode Test")
        print("=" * 60)
        
        # Test 1: Library function accessibility
        interface = tester.test_library_function_calls()
        
        # Test 2: Configuration handling
        config_valid = tester.test_real_sweep_configuration(interface)
        
        if not config_valid:
            print("❌ Configuration test failed, aborting")
            return 1
        
        # Test 3: Compare sweep mode behaviors
        results = tester.test_sweep_mode_behavior(interface)
        
        # Test 4: Analyze results
        tester.analyze_results(results)
        
        # Final assessment
        print(f"\n{'='*60}")
        print("FINAL ASSESSMENT")
        print(f"{'='*60}")
        
        sim_success = results.get("Simulation Mode", {}).get('success', False)
        real_success = results.get("Real Mode (if available)", {}).get('success', False)
        
        if sim_success and real_success:
            print("✅ Both simulation and real modes are working")
            print("   If you're still seeing issues, the problem may be in:")
            print("   - UI parameter updates not triggering new sweeps")
            print("   - Display/plotting issues")
            print("   - Real device configuration differences")
        elif sim_success and not real_success:
            print("✅ Simulation mode works, but real mode has issues")
            print("   This could be due to:")
            print("   - No HackRF device connected")
            print("   - Device permission issues")
            print("   - Library compilation problems")
        elif not sim_success:
            print("❌ Basic simulation mode is not working")
            print("   This indicates a fundamental issue with the interface")
        
        return 0 if sim_success else 1
        
    except Exception as e:
        print(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 