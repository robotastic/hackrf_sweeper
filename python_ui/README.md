# HackRF Spectrum Analyzer UI

A Python Qt-based graphical user interface for the HackRF spectrum sweeper library.

## Features

- **Real-time Spectrum Display**: Large central plot showing spectrum data with real-time updates
- **Peak Hold**: Optional peak hold functionality to track maximum signal levels
- **Performance Optimized**: Designed for real-time operation with CPU hang prevention
- **Bluetooth Analysis**: Waterfall display and smooth spectrum rendering for wireless analysis
- **Comprehensive Controls**: Full access to all HackRF sweeper parameters
- **Status Monitoring**: Real-time sweep statistics and status messages
- **File Output**: Optional data logging to files

## Requirements

- Python 3.7+
- PyQt5
- pyqtgraph
- numpy
- scipy
- HackRF hardware and libhackrf installed

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure HackRF library is installed:**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install libhackrf-dev hackrf
   
   # Fedora/CentOS
   sudo dnf install hackrf-devel hackrf
   
   # macOS (with Homebrew)
   brew install hackrf
   ```

3. **Build the hackrf_sweeper library** (if not already built):
   ```bash
   cd ..  # Go to project root
   mkdir -p build
   cd build
   cmake ..
   make
   ```

## Usage

### Display Environment Setup

The application requires a graphical display. Choose the appropriate method:

**Local Desktop Session:**
```bash
cd python_ui
./run_spectrum_analyzer.sh
```

**SSH with X11 Forwarding:**
```bash
# Connect with X11 forwarding
ssh -X username@hostname
cd ~/Projects/RF-Scanning/hackrf_sweeper/python_ui
./run_spectrum_analyzer.sh
```

**Headless/Testing Mode:**
```bash
# For testing without a display
export QT_QPA_PLATFORM=offscreen
python main.py
```

### Running the Application

1. **Start the application:**
   ```bash
   cd python_ui
   ./run_spectrum_analyzer.sh
   ```

2. **Configure sweep parameters** in the left sidebar:

   - **Device Configuration**:
     - Serial Number: Specify HackRF device (leave blank for auto-detect)
     - RF Amplifier: Enable/disable RF amplifier
     - Antenna Power: Enable/disable antenna port power

   - **Frequency Configuration**:
     - Min/Max Frequency: Set sweep frequency range (0-6000 MHz)

   - **Gain Configuration**:
     - LNA (IF) Gain: 0-40 dB in 8 dB steps
     - VGA (Baseband) Gain: 0-62 dB in 2 dB steps

   - **FFT Configuration**:
     - Bin Width: FFT bin width (2445-5000000 Hz)
     - FFTW Plan: FFTW optimization level
     - Wisdom File: Optional FFTW wisdom file for faster startup

   - **Sweep Configuration**:
     - One Shot Mode: Perform single sweep
     - Number of Sweeps: Limit sweep count (0 = infinite)
     - Normalize Timestamps: Keep same timestamp within sweep

   - **Output Configuration**:
     - Output Mode: Text, binary, or inverse FFT
     - Output File: Optional file for data logging

3. **Start sweeping:**
   - Click "Start Sweep" to begin spectrum analysis
   - Use "Stop Sweep" to halt the operation
   - "Apply Configuration" updates settings without starting

4. **View results:**
   - Main spectrum plot shows real-time frequency vs. power
   - Green line: Current sweep data
   - Red dashed line: Peak hold data
   - Use "Clear Peak Hold" to reset peak data

## Interface Components

### Spectrum Display
- **X-axis**: Frequency (MHz)
- **Y-axis**: Power level (dB)
- **Auto-scaling**: Frequency range adjusts to sweep settings
- **Grid**: Configurable grid overlay
- **Legend**: Shows current and peak hold traces

### Control Panel
Organized into logical groups matching hackrf_sweeper command-line options:

| UI Control | Command Line | Description |
|------------|--------------|-------------|
| Serial Number | `-d` | HackRF device serial number |
| RF Amplifier | `-a` | RX RF amplifier enable |
| Min/Max Frequency | `-f` | Frequency range in MHz |
| Antenna Power | `-p` | Antenna port power enable |
| LNA Gain | `-l` | RX LNA gain (0-40dB, 8dB steps) |
| VGA Gain | `-g` | RX VGA gain (0-62dB, 2dB steps) |
| Bin Width | `-w` | FFT bin width (2445-5000000 Hz) |
| FFTW Plan | `-P` | FFTW plan type |
| Wisdom File | `-W` | FFTW wisdom file path |
| One Shot | `-1` | Single sweep mode |
| Number of Sweeps | `-N` | Maximum sweep count |
| Output Mode | `-B/-I` | Binary/IFFT output modes |
| Normalize Timestamps | `-n` | Timestamp normalization |
| Output File | `-r` | Output file path |

### Status Panel
- **Sweep Statistics**: Real-time counters and rates
- **Status Messages**: Log of operations and errors
- **Clear Functions**: Reset peak hold and message log

## Configuration Validation

The application validates all parameters before starting a sweep:
- Frequency range limits (0-6000 MHz)
- Gain step requirements (LNA: 8dB, VGA: 2dB)
- FFT bin width limits (2445-5000000 Hz)
- Logical consistency checks

## Error Handling

- Library loading failures
- Device connection issues
- Parameter validation errors
- Runtime sweep errors

All errors are displayed in both popup dialogs and the status message log.

## Development Notes

### Architecture
- **main.py**: Application entry point
- **spectrum_analyzer_ui.py**: Main UI components
- **hackrf_interface.py**: HackRF library wrapper with ctypes integration
- **requirements.txt**: Python dependencies
- **test_hackrf_integration.py**: Integration test suite

### Library Integration Details

The Python UI integrates with the hackrf_sweeper library through:

1. **Shared Library Creation**: CMakeLists.txt builds `libhackrf_sweeper.so` from the static library
2. **ctypes Interface**: Complete Python wrapper for all hackrf_sweeper functions
3. **Callback System**: Real-time FFT data via Python callbacks from C library
4. **Automatic Fallback**: Uses simulation mode if hardware/library unavailable
5. **Memory Management**: Proper cleanup of C structures and resources

**Integration Test**: Run `python3 test_hackrf_integration.py` to verify library loading and function availability.

**Command-Line Demo**: 
- Real hardware mode: `python3 demo_integration.py`
- Simulation mode: `python3 demo_integration.py --sim`

### Performance Optimization

The UI is optimized for real-time operation with automatic CPU hang prevention:
- See `PERFORMANCE_OPTIMIZATION.md` for detailed technical information
- Memory usage optimized to <1 MB for normal operation
- Built-in throttling prevents UI hanging during high data rates
- Graceful error handling ensures stable operation

### Current Implementation Status
- ✅ Complete UI framework
- ✅ Parameter validation
- ✅ Real HackRF library integration
- ✅ Shared library generation for Python access
- ✅ Full ctypes interface to hackrf_sweeper functions
- ✅ Real-time FFT callback system
- ✅ Automatic fallback to simulation mode
- 📋 File output functionality
- 📋 Device enumeration

### Future Enhancements
- Waterfall display
- Signal measurement tools
- Configuration presets
- Data export options
- Advanced triggering
- Multi-device support

## Troubleshooting

### Common Issues

1. **Display/GUI Issues**
   - **"qt.qpa.xcb: could not connect to display"**: No display server available
     - **SSH users**: Reconnect with `ssh -X username@hostname`
     - **Headless**: Use `export QT_QPA_PLATFORM=offscreen`
     - **Local**: Ensure you're in a desktop environment
   - **Wayland warning**: Use `export QT_QPA_PLATFORM=wayland` if preferred
   - Test display with: `python3 test_display.py`

2. **"Could not load HackRF library"**
   - Ensure libhackrf is installed and in system path
   - Check library permissions

3. **Permission denied accessing HackRF**
   - Add user to `plugdev` group (Linux)
   - Use `sudo` if necessary
   - Check udev rules for HackRF

4. **PyQt5 import errors**
   - Install PyQt5: `pip install PyQt5`
   - On some systems: `sudo apt-get install python3-pyqt5`

5. **Poor performance**
   - Reduce FFT bin count
   - Use FFTW wisdom file
   - Close other applications

### Debug Mode
Enable debug output by setting environment variable:
```bash
export HACKRF_DEBUG=1
python main.py
```

## License

This UI application follows the same license as the parent HackRF sweeper project (GNU GPL v2+).

## Contributing

Contributions welcome! Please ensure:
- Code follows existing style
- UI changes maintain usability
- New features include documentation
- Test with real HackRF hardware when possible 