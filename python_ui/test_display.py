#!/usr/bin/env python3
"""
Simple test script to verify Qt/display environment
"""

import sys
import os

def test_qt_environment():
    """Test if Qt can initialize properly."""
    print("Qt Display Environment Test")
    print("=" * 30)
    
    # Check environment variables
    print(f"DISPLAY: {os.environ.get('DISPLAY', 'Not set')}")
    print(f"WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY', 'Not set')}")
    print(f"XDG_SESSION_TYPE: {os.environ.get('XDG_SESSION_TYPE', 'Not set')}")
    print(f"QT_QPA_PLATFORM: {os.environ.get('QT_QPA_PLATFORM', 'Not set')}")
    print(f"SSH_CLIENT: {os.environ.get('SSH_CLIENT', 'Not set')}")
    print()
    
    # Test PyQt5 import
    try:
        print("Testing PyQt5 import...")
        from PyQt5.QtWidgets import QApplication, QLabel, QWidget
        from PyQt5.QtCore import Qt
        print("✓ PyQt5 import successful")
    except ImportError as e:
        print(f"✗ PyQt5 import failed: {e}")
        return False
    
    # Test QApplication creation
    try:
        print("Testing QApplication creation...")
        app = QApplication(sys.argv)
        print("✓ QApplication created successfully")
        
        # Test simple widget creation
        print("Testing widget creation...")
        widget = QWidget()
        widget.setWindowTitle("Qt Test Window")
        widget.resize(200, 100)
        
        label = QLabel("Qt is working!", widget)
        label.setAlignment(Qt.AlignCenter)
        
        print("✓ Widget created successfully")
        print()
        print("Attempting to show window for 3 seconds...")
        
        widget.show()
        
        # Process events briefly
        app.processEvents()
        
        # Use a timer to close after 3 seconds
        from PyQt5.QtCore import QTimer
        timer = QTimer()
        timer.timeout.connect(app.quit)
        timer.start(3000)  # 3 seconds
        
        result = app.exec_()
        print(f"Application exited with code: {result}")
        print("✓ Qt environment test completed successfully!")
        return True
        
    except Exception as e:
        print(f"✗ Qt environment test failed: {e}")
        print("This typically indicates a display/platform issue")
        return False

def print_platform_info():
    """Print available Qt platform information."""
    try:
        from PyQt5.QtGui import QGuiApplication
        app = QGuiApplication([])
        
        print("\nAvailable Qt Platforms:")
        print("-" * 25)
        
        # This will print available platforms
        platforms = app.platformName()
        print(f"Current platform: {platforms}")
        
        app.quit()
        
    except Exception as e:
        print(f"Could not get platform info: {e}")

def main():
    """Main test function."""
    if "--platforms" in sys.argv:
        print_platform_info()
        return
    
    success = test_qt_environment()
    
    if not success:
        print("\nTroubleshooting suggestions:")
        print("1. If using SSH, enable X11 forwarding: ssh -X user@host")
        print("2. If using Wayland, set: export QT_QPA_PLATFORM=wayland")
        print("3. If using X11, ensure DISPLAY is set correctly")
        print("4. For headless testing, use: export QT_QPA_PLATFORM=offscreen")
        print("5. Check if you have permission to access the display")
        sys.exit(1)
    else:
        print("\n✓ Qt environment is working correctly!")
        print("You should be able to run the HackRF Spectrum Analyzer UI")

if __name__ == "__main__":
    main() 