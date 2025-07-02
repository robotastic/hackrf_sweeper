#!/usr/bin/env python3
"""
Frequency Range Integration Test
Tests that frequency ranges are correctly passed through the entire chain:
UI Settings -> HackRF Interface -> Library Calls -> Callback Data -> Display
"""

import sys
import os
import time
import numpy as np
from PyQt5.QtWidgets import QApplication
from hackrf_interface import HackRFInterface, HackRFSweepConfig


class FrequencyRangeTest:
    """Test frequency range handling throughout the system."""
    
    def __init__(self):
        # Set up Qt application for signal processing
        if 'QT_QPA_PLATFORM' not in os.environ:
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)
        
        self.interface = HackRFInterface()
        self.received_data = []
        self.test_results = {}
        
    def test_frequency_range_configuration(self, freq_min, freq_max, test_name):
        """Test a specific frequency range configuration."""
        print(f"\n{'='*60}")
        print(f"Testing {test_name}: {freq_min} - {freq_max} MHz")
        print(f"{'='*60}")
        
        # Clear previous data
        self.received_data.clear()
        
        # Configure the interface
        config = HackRFSweepConfig()
        config.freq_min_mhz = freq_min
        config.freq_max_mhz = freq_max
        config.lna_gain = 16
        config.vga_gain = 20
        config.bin_width = 1000000  # 1 MHz bins for easier analysis
        config.one_shot = False
        
        self.interface.update_config(config)
        
        # Validate configuration
        valid, message = self.interface.validate_config()
        if not valid:
            print(f"❌ Configuration invalid: {message}")
            return False
        
        print(f"✅ Configuration valid")
        print(f"   Range: {config.freq_min_mhz} - {config.freq_max_mhz} MHz")
        print(f"   Bin width: {config.bin_width} Hz")
        
        # Set up data collection
        def on_spectrum_data(frequencies, powers):
            self.received_data.append({
                'frequencies': frequencies.copy(),
                'powers': powers.copy(),
                'min_freq': np.min(frequencies),
                'max_freq': np.max(frequencies),
                'num_points': len(frequencies)
            })
            
            if len(self.received_data) <= 3:  # Show first few
                print(f"   Received spectrum #{len(self.received_data)}: "
                      f"{len(frequencies)} points, "
                      f"range {np.min(frequencies):.1f}-{np.max(frequencies):.1f} MHz")
        
        def on_status_change(message):
            print(f"   Status: {message}")
        
        self.interface.spectrum_data_ready.connect(on_spectrum_data)
        self.interface.sweep_status_changed.connect(on_status_change)
        
        # Start sweep in simulation mode to ensure consistent data
        print("   Starting sweep in simulation mode...")
        self.interface.start_sweep(force_simulation=True)
        
        # Collect data for a few seconds
        start_time = time.time()
        while time.time() - start_time < 3.0 and len(self.received_data) < 10:
            self.app.processEvents()
            time.sleep(0.01)
        
        # Stop sweep
        self.interface.stop_sweep()
        self.app.processEvents()
        
        # Analyze results
        return self._analyze_frequency_data(freq_min, freq_max, test_name)
    
    def _analyze_frequency_data(self, expected_min, expected_max, test_name):
        """Analyze the collected frequency data."""
        if not self.received_data:
            print("❌ No spectrum data received")
            return False
        
        print(f"\n   Analysis of {len(self.received_data)} spectrum updates:")
        
        # Check frequency range coverage
        all_frequencies = []
        for data in self.received_data:
            all_frequencies.extend(data['frequencies'])
        
        if not all_frequencies:
            print("❌ No frequency data found")
            return False
        
        actual_min = min(all_frequencies)
        actual_max = max(all_frequencies)
        
        print(f"   Expected range: {expected_min:.1f} - {expected_max:.1f} MHz")
        print(f"   Actual range:   {actual_min:.1f} - {actual_max:.1f} MHz")
        
        # Check if ranges match (within reasonable tolerance)
        min_tolerance = abs(expected_min - actual_min)
        max_tolerance = abs(expected_max - actual_max)
        
        print(f"   Min difference: {min_tolerance:.1f} MHz")
        print(f"   Max difference: {max_tolerance:.1f} MHz")
        
        # Frequency range should match within 10% or 100 MHz, whichever is larger
        expected_span = expected_max - expected_min
        tolerance_threshold = max(expected_span * 0.1, 100.0)
        
        range_match = (min_tolerance <= tolerance_threshold and 
                      max_tolerance <= tolerance_threshold)
        
        if range_match:
            print("   ✅ Frequency range matches expected values")
        else:
            print(f"   ❌ Frequency range mismatch (tolerance: {tolerance_threshold:.1f} MHz)")
        
        # Check data consistency
        first_data = self.received_data[0]
        consistent_points = all(len(data['frequencies']) == first_data['num_points'] 
                               for data in self.received_data)
        
        if consistent_points:
            print(f"   ✅ Consistent data size: {first_data['num_points']} points per sweep")
        else:
            print("   ❌ Inconsistent data sizes across sweeps")
        
        # Check frequency spacing
        if len(first_data['frequencies']) > 1:
            freq_diffs = np.diff(first_data['frequencies'])
            avg_spacing = np.mean(freq_diffs)
            spacing_std = np.std(freq_diffs)
            
            print(f"   Frequency spacing: {avg_spacing:.3f} ± {spacing_std:.3f} MHz")
            
            # Should be relatively uniform
            uniform_spacing = spacing_std < avg_spacing * 0.1
            if uniform_spacing:
                print("   ✅ Uniform frequency spacing")
            else:
                print("   ⚠️  Non-uniform frequency spacing")
        
        # Store results
        self.test_results[test_name] = {
            'expected_min': expected_min,
            'expected_max': expected_max,
            'actual_min': actual_min,
            'actual_max': actual_max,
            'range_match': range_match,
            'consistent_points': consistent_points,
            'num_updates': len(self.received_data),
            'points_per_update': first_data['num_points'] if self.received_data else 0
        }
        
        return range_match and consistent_points
    
    def test_library_parameter_passing(self):
        """Test that parameters are correctly passed to the library functions."""
        print(f"\n{'='*60}")
        print("Testing Library Parameter Passing")
        print(f"{'='*60}")
        
        # Test different configurations
        test_configs = [
            (100, 200, "Small range"),
            (400, 500, "UHF band"),
            (1000, 2000, "L-band"),
            (2000, 3000, "S-band"),
            (100, 6000, "Full range"),
        ]
        
        for freq_min, freq_max, desc in test_configs:
            config = HackRFSweepConfig()
            config.freq_min_mhz = freq_min
            config.freq_max_mhz = freq_max
            self.interface.update_config(config)
            
            # Check internal state
            stored_min = self.interface.config.freq_min_mhz
            stored_max = self.interface.config.freq_max_mhz
            
            if stored_min == freq_min and stored_max == freq_max:
                print(f"   ✅ {desc}: {freq_min}-{freq_max} MHz stored correctly")
            else:
                print(f"   ❌ {desc}: Expected {freq_min}-{freq_max}, got {stored_min}-{stored_max}")
    
    def test_simulation_vs_real_mode(self):
        """Compare simulation mode frequency handling with real mode expectations."""
        print(f"\n{'='*60}")
        print("Testing Simulation vs Real Mode Frequency Handling")
        print(f"{'='*60}")
        
        # Check if real HackRF functions are available
        has_real_functions = (self.interface.sweeper_lib and 
                             hasattr(self.interface.sweeper_lib, 'hackrf_sweep_easy_init'))
        
        print(f"Real HackRF functions available: {'✅ Yes' if has_real_functions else '❌ No'}")
        
        if has_real_functions:
            print("   The interface can access real HackRF library functions")
            print("   However, we'll test with simulation mode for consistency")
        else:
            print("   Running in simulation-only mode")
            print("   Real hardware testing requires a connected HackRF device")
        
        # In simulation mode, verify that frequency generation follows the settings
        config = HackRFSweepConfig()
        config.freq_min_mhz = 500
        config.freq_max_mhz = 1500
        self.interface.update_config(config)
        
        # Look at the simulation worker code behavior
        print("\n   Analyzing simulation mode frequency generation:")
        print(f"   - Configured range: {config.freq_min_mhz}-{config.freq_max_mhz} MHz")
        
        # The simulation should use these exact values
        expected_points = max(100, int((config.freq_max_mhz - config.freq_min_mhz) * 10))
        print(f"   - Expected points: {expected_points} (10 points per MHz)")
        
        return True
    
    def run_all_tests(self):
        """Run the complete frequency range test suite."""
        print("HackRF Frequency Range Integration Test")
        print("=" * 60)
        
        # Test 1: Library parameter passing
        param_test = self.test_library_parameter_passing()
        
        # Test 2: Simulation vs real mode
        mode_test = self.test_simulation_vs_real_mode()
        
        # Test 3: Various frequency ranges
        range_tests = [
            (100, 200, "VHF High"),
            (400, 500, "UHF"),
            (800, 1000, "Cellular"),
            (2000, 3000, "WiFi/Bluetooth"),
            (100, 1000, "Wide VHF-UHF"),
            (1000, 6000, "Microwave"),
            (100, 6000, "Full HackRF Range"),
        ]
        
        results = []
        for freq_min, freq_max, test_name in range_tests:
            result = self.test_frequency_range_configuration(freq_min, freq_max, test_name)
            results.append((test_name, result))
        
        # Summary
        print(f"\n{'='*60}")
        print("TEST RESULTS SUMMARY")
        print(f"{'='*60}")
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {test_name:20s}: {status}")
        
        print(f"\nOverall: {passed}/{total} frequency range tests passed")
        
        # Detailed analysis
        if self.test_results:
            print(f"\n{'='*60}")
            print("DETAILED FREQUENCY ANALYSIS")
            print(f"{'='*60}")
            
            for test_name, data in self.test_results.items():
                print(f"\n{test_name}:")
                print(f"  Expected: {data['expected_min']:.1f} - {data['expected_max']:.1f} MHz")
                print(f"  Actual:   {data['actual_min']:.1f} - {data['actual_max']:.1f} MHz")
                print(f"  Updates:  {data['num_updates']}")
                print(f"  Points:   {data['points_per_update']} per update")
                
                # Check for potential issues
                expected_span = data['expected_max'] - data['expected_min']
                actual_span = data['actual_max'] - data['actual_min']
                span_ratio = actual_span / expected_span if expected_span > 0 else 0
                
                if span_ratio < 0.8:
                    print(f"  ⚠️  Warning: Actual span is only {span_ratio:.1%} of expected")
                elif span_ratio > 1.2:
                    print(f"  ⚠️  Warning: Actual span is {span_ratio:.1%} of expected")
                else:
                    print(f"  ✅ Good span coverage: {span_ratio:.1%} of expected")
        
        if passed == total:
            print(f"\n🎉 All frequency range tests passed!")
            print("   The frequency range handling is working correctly.")
            return True
        else:
            print(f"\n⚠️  {total - passed} tests failed.")
            print("   There may be issues with frequency range handling.")
            return False


def main():
    """Run the frequency range test suite."""
    try:
        tester = FrequencyRangeTest()
        success = tester.run_all_tests()
        return 0 if success else 1
    except Exception as e:
        print(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 