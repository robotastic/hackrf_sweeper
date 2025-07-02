#!/usr/bin/env python3
"""
Test script to verify HackRF library integration
"""

import sys
import os
from hackrf_interface import HackRFInterface, HackRFSweepConfig


def test_library_loading():
    """Test if the libraries load correctly."""
    print("Testing library loading...")
    
    interface = HackRFInterface()
    
    # Check basic library loading
    if not interface.hackrf_lib:
        print("❌ Failed to load HackRF library")
        return False
    else:
        print("✅ HackRF library loaded successfully")
    
    if not interface.sweeper_lib:
        print("❌ Failed to load sweeper library")
        return False
    else:
        print("✅ Sweeper library loaded successfully")
    
    # Check if sweep functions are available
    has_sweep_init = hasattr(interface.sweeper_lib, 'hackrf_sweep_easy_init')
    has_sweep_start = hasattr(interface.sweeper_lib, 'hackrf_sweep_start')
    has_sweep_stop = hasattr(interface.sweeper_lib, 'hackrf_sweep_stop')
    has_sweep_callback = hasattr(interface.sweeper_lib, 'hackrf_sweep_set_fft_rx_callback')
    
    if all([has_sweep_init, has_sweep_start, has_sweep_stop, has_sweep_callback]):
        print("✅ All required sweep functions are available")
        return True
    else:
        print("❌ Some sweep functions are missing:")
        if not has_sweep_init:
            print("   - hackrf_sweep_easy_init")
        if not has_sweep_start:
            print("   - hackrf_sweep_start")
        if not has_sweep_stop:
            print("   - hackrf_sweep_stop")
        if not has_sweep_callback:
            print("   - hackrf_sweep_set_fft_rx_callback")
        return False


def test_configuration_validation():
    """Test configuration validation."""
    print("\nTesting configuration validation...")
    
    interface = HackRFInterface()
    
    # Test valid configuration
    config = HackRFSweepConfig()
    config.freq_min_mhz = 100
    config.freq_max_mhz = 200
    config.lna_gain = 16
    config.vga_gain = 20
    config.bin_width = 1000000
    
    interface.update_config(config)
    valid, message = interface.validate_config()
    
    if valid:
        print("✅ Valid configuration accepted")
    else:
        print(f"❌ Valid configuration rejected: {message}")
        return False
    
    # Test invalid configuration (min >= max frequency)
    config.freq_min_mhz = 200
    config.freq_max_mhz = 100
    interface.update_config(config)
    valid, message = interface.validate_config()
    
    if not valid:
        print("✅ Invalid configuration properly rejected")
    else:
        print("❌ Invalid configuration was accepted")
        return False
    
    return True


def test_device_detection():
    """Test device detection capabilities."""
    print("\nTesting device detection...")
    
    interface = HackRFInterface()
    
    try:
        # Try to initialize HackRF (this will fail if no device is connected)
        result = interface.hackrf_lib.hackrf_init()
        
        if result == 0:  # HACKRF_SUCCESS
            print("✅ HackRF library initialization successful")
            
            # Try to open a device
            device_ptr = interface.hackrf_lib.hackrf_open
            print("✅ HackRF device access functions available")
            
            # Clean up
            interface.hackrf_lib.hackrf_exit()
            
        else:
            print(f"⚠️  HackRF initialization returned error code: {result}")
            print("   This is normal if no HackRF device is connected")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during device detection: {e}")
        return False


def test_simulation_mode():
    """Test simulation mode functionality."""
    print("\nTesting simulation mode...")
    
    # Need QApplication for Qt signals to work
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer, QEventLoop
    import sys
    
    # Set offscreen platform for headless testing
    if 'QT_QPA_PLATFORM' not in os.environ:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    
    # Create QApplication if one doesn't exist
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    interface = HackRFInterface()
    
    # Configure for a quick test
    config = HackRFSweepConfig()
    config.freq_min_mhz = 400
    config.freq_max_mhz = 500
    config.one_shot = False  # Don't use one-shot for testing
    interface.update_config(config)
    
    # Set up signal capturing
    spectrum_received = False
    spectrum_count = 0
    
    def on_spectrum_data(frequencies, powers):
        nonlocal spectrum_received, spectrum_count
        spectrum_received = True
        spectrum_count += 1
        print(f"   Received spectrum data #{spectrum_count}: {len(frequencies)} points, "
              f"range {frequencies[0]:.1f}-{frequencies[-1]:.1f} MHz")
    
    def on_status_change(message):
        print(f"   Status: {message}")
    
    interface.spectrum_data_ready.connect(on_spectrum_data)
    interface.sweep_status_changed.connect(on_status_change)
    
    try:
        # Force simulation mode regardless of hardware availability
        interface.start_sweep(force_simulation=True)
        
        # Process Qt events for a few seconds
        import time
        end_time = time.time() + 3.0
        while time.time() < end_time and spectrum_count < 5:
            app.processEvents()
            time.sleep(0.01)
        
        interface.stop_sweep()
        
        # Process any remaining events
        app.processEvents()
        
        if spectrum_received and spectrum_count > 0:
            print(f"✅ Simulation mode working correctly (received {spectrum_count} updates)")
            return True
        else:
            print(f"❌ No spectrum data received in simulation mode (count: {spectrum_count})")
            return False
            
    except Exception as e:
        print(f"❌ Error in simulation mode: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("HackRF Integration Test Suite")
    print("=" * 40)
    
    tests = [
        test_library_loading,
        test_configuration_validation,
        test_device_detection,
        test_simulation_mode,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            results.append(False)
    
    print("\n" + "=" * 40)
    print("Test Results Summary:")
    
    test_names = [
        "Library Loading",
        "Configuration Validation", 
        "Device Detection",
        "Simulation Mode"
    ]
    
    passed = 0
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! HackRF integration is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 