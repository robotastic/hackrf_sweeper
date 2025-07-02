#!/usr/bin/env python3
"""
HackRF Spectrum Analyzer UI
Main entry point for the application.
"""

import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

# Add the parent directory to the path to access the hackrf library
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spectrum_analyzer_ui import SpectrumAnalyzerMainWindow


def main():
    """Main function to start the HackRF Spectrum Analyzer UI."""
    
    app = QApplication(sys.argv)
    app.setApplicationName("HackRF Spectrum Analyzer")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("HackRF Tools")
    
    # Create main window
    main_window = SpectrumAnalyzerMainWindow()
    main_window.show()
    
    # Start the application event loop
    sys.exit(app.exec_())


if __name__ == "__main__":
    main() 