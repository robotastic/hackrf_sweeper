#!/bin/bash

# HackRF Spectrum Monitor Setup Script

echo "HackRF Spectrum Monitor Setup"
echo "============================"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✓ Python dependencies installed"
else
    echo "✗ Failed to install Python dependencies"
    exit 1
fi

# Check for HackRF library
echo "Checking for HackRF library..."
if ldconfig -p | grep -q hackrf; then
    echo "✓ HackRF library found"
    HACKRF_AVAILABLE=true
fi

# Make main script executable
chmod +x main.py
echo "✓ Made main.py executable"

# Create symlink for easier access (optional)
if [ ! -L "../spectrum-monitor" ]; then
    ln -s spectrum_monitor/main.py ../spectrum-monitor 2>/dev/null || true
fi

echo ""
echo "Setup complete!"
echo ""
echo "Usage:"
echo "  ./main.py --help                    # Show help"
echo "  ./main.py --mode learning           # Learn baseline spectrum"
echo "  ./main.py --mode monitoring         # Monitor for anomalies"
echo ""


echo "For detailed documentation, see README.md" 