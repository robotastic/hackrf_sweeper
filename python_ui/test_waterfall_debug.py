#!/usr/bin/env python3

import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from spectrum_analyzer_ui import SpectrumDisplay

def test_waterfall_dimensions():
    """Test waterfall dimension calculation with debug output."""
    
    app = QApplication(sys.argv)
    
    # Create the spectrum display widget
    display = SpectrumDisplay()
    
    # Create a simple window to hold it
    window = QMainWindow()
    window.setCentralWidget(display)
    window.resize(1200, 800)  # Set a specific size
    window.show()
    
    # Force the application to process events so widgets get their sizes
    app.processEvents()
    
    print("=== FORCING WATERFALL INITIALIZATION ===")
    
    # Force waterfall initialization
    display.initialize_waterfall_array()
    
    print("\n=== TESTING RESIZE ===")
    
    # Test resizing
    window.resize(1600, 600)
    app.processEvents()
    display.initialize_waterfall_array()
    
    print("\n=== CREATING TEST PATTERN ===")
    
    # Create test pattern to verify it works
    display.create_test_waterfall_pattern()
    
    # Keep window open briefly to see results
    app.processEvents()
    
    print("\n=== TEST COMPLETED ===")
    app.quit()

if __name__ == "__main__":
    test_waterfall_dimensions() 