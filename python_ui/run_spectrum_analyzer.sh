#!/bin/bash

# HackRF Spectrum Analyzer UI Launcher
# This script sets up the environment and launches the Qt UI

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "HackRF Spectrum Analyzer UI Launcher"
echo "====================================="

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python version: $PYTHON_VERSION"

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "Virtual environment: $VIRTUAL_ENV"
else
    echo "No virtual environment detected"
    echo "Consider creating one: python3 -m venv venv && source venv/bin/activate"
fi

# Change to the UI directory
cd "$SCRIPT_DIR"

# Check if requirements are installed
echo
echo "Checking Python dependencies..."

check_package() {
    local package=$1
    if python3 -c "import $package" 2>/dev/null; then
        echo "✓ $package is installed"
        return 0
    else
        echo "✗ $package is NOT installed"
        return 1
    fi
}

# Check all required packages
all_deps_ok=true
for pkg in PyQt5 pyqtgraph numpy scipy; do
    if ! check_package "$pkg"; then
        all_deps_ok=false
    fi
done

if [ "$all_deps_ok" = false ]; then
    echo
    echo "Missing dependencies detected. Install with:"
    echo "  pip install -r requirements.txt"
    echo
    read -p "Would you like to install dependencies now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Installing dependencies..."
        pip install -r requirements.txt
        if [ $? -ne 0 ]; then
            echo "Failed to install dependencies"
            exit 1
        fi
        echo "Dependencies installed successfully"
    else
        echo "Please install dependencies before running the UI"
        exit 1
    fi
fi

# Check for HackRF library
echo
echo "Checking HackRF library..."
if ldconfig -p | grep -q libhackrf; then
    echo "✓ libhackrf found in system"
else
    echo "⚠ libhackrf not found in system library path"
    echo "  Make sure HackRF library is installed:"
    echo "  Ubuntu/Debian: sudo apt-get install libhackrf-dev hackrf"
    echo "  Fedora/CentOS: sudo dnf install hackrf-devel hackrf"
    echo "  macOS: brew install hackrf"
fi

# Check for HackRF device (optional)
echo
echo "Checking for HackRF devices..."
if command -v hackrf_info &> /dev/null; then
    if hackrf_info 2>/dev/null | grep -q "Found HackRF"; then
        echo "✓ HackRF device detected"
        hackrf_info 2>/dev/null | grep "Serial number"
    else
        echo "⚠ No HackRF devices found"
        echo "  Make sure device is connected and accessible"
        echo "  You may need to add user to 'plugdev' group"
    fi
else
    echo "⚠ hackrf_info command not found"
    echo "  Install HackRF tools package"
fi

# Set environment variables for debugging if requested
if [[ "$1" == "--debug" ]]; then
    echo
    echo "Debug mode enabled"
    export HACKRF_DEBUG=1
    export QT_DEBUG_PLUGINS=1
fi

# Check display environment and set appropriate Qt platform
echo
echo "Checking display environment..."

if [[ -n "$WAYLAND_DISPLAY" ]] && [[ -z "$DISPLAY" ]]; then
    echo "Wayland detected, setting QT_QPA_PLATFORM=wayland"
    export QT_QPA_PLATFORM=wayland
elif [[ -n "$DISPLAY" ]]; then
    echo "X11 display detected: $DISPLAY"
    export QT_QPA_PLATFORM=xcb
elif [[ -n "$SSH_CLIENT" ]] || [[ -n "$SSH_TTY" ]]; then
    echo "SSH session detected without display"
    echo "For GUI access over SSH, use X11 forwarding:"
    echo "  ssh -X username@hostname"
    echo "Or set up a VNC/X11 server on the remote machine"
    exit 1
else
    echo "No display environment detected"
    echo "Available Qt platforms: xcb, wayland, offscreen"
    echo "Trying xcb as fallback..."
    export QT_QPA_PLATFORM=xcb
fi

# Launch the application
echo
echo "Launching HackRF Spectrum Analyzer UI..."
echo "======================================="

# Add the parent directory to Python path for imports
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Launch the UI
python3 main.py

echo
echo "UI application exited" 