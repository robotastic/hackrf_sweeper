# HackRF Spectrum Monitor

A command-line spectrum monitoring tool using the HackRF sweeper library. Supports learning mode for baseline establishment and monitoring mode for anomaly detection.

## Features

### Learning Mode
- Scans designated spectrum portions and builds baseline power profiles
- Real-time feedback showing number of FFT bins with new maximum values
- Interactive termination with any key press
- Saves learned baselines to persistent storage

### Monitoring Mode
- Compares live spectrum data against learned baselines
- Configurable detection thresholds with runtime adjustment
- Real-time alerts showing:
  - Frequency bins exceeding thresholds
  - Signal strength measurements
  - Amount above baseline threshold
- Interactive threshold adjustment during operation

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Ensure libhackrf is installed
sudo apt-get install libhackrf-dev  # Ubuntu/Debian
```

## Usage

### Basic Usage
```bash
# Learning mode (default: scan and learn baselines)
python main.py --mode learning

# Monitoring mode (default mode if baselines exist)
python main.py --mode monitoring

# Use custom config file
python main.py --config my_config.yaml
```

### Learning Mode
```bash
python main.py --mode learning
# Press any key to stop learning and save baselines
```

### Monitoring Mode
```bash
python main.py --mode monitoring
# During operation:
# - Press '+' to increase threshold buffer
# - Press '-' to decrease threshold buffer
# - Press 'q' to quit
```

## Configuration

The tool uses a YAML configuration file (`config.yaml` by default):

```yaml
# Spectrum configuration
spectrum:
  freq_min_mhz: 88.0      # Start frequency in MHz
  freq_max_mhz: 108.0     # End frequency in MHz
  bin_width: 1000000      # FFT bin width in Hz
  
# HackRF settings
hackrf:
  lna_gain: 16            # LNA gain (0-40dB, 8dB steps)
  vga_gain: 20            # VGA gain (0-62dB, 2dB steps)
  amp_enable: false       # RF amplifier enable
  antenna_enable: false   # Antenna port power enable

# Monitoring settings
monitoring:
  threshold_buffer_db: 10.0  # Detection threshold above baseline (dB)
  update_rate_hz: 10.0       # Spectrum update rate
  alert_cooldown_s: 1.0      # Minimum time between alerts

# Storage settings
storage:
  baseline_file: "baselines.npz"  # Learned baseline storage
  learning_history: 1000          # Number of spectra to track in learning
```

## Interactive Controls

### Learning Mode
- **Any Key**: Stop learning and save baselines

### Monitoring Mode
- **+ (Plus)**: Increase threshold buffer by 1 dB
- **- (Minus)**: Decrease threshold buffer by 1 dB
- **r**: Reset threshold buffer to config default
- **s**: Show current statistics
- **q**: Quit monitoring mode

## File Structure

```
spectrum_monitor/
├── main.py                    # Entry point
├── config.py                  # Configuration management
├── spectrum_monitor.py        # Main monitoring coordinator
├── learning_mode.py           # Learning mode implementation
├── monitoring_mode.py         # Monitoring mode implementation  
├── hackrf_interface.py        # CLI-optimized HackRF interface
├── storage.py                 # Baseline data persistence
├── display.py                 # CLI output and alerts
├── config.yaml               # Default configuration
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Example Output

### Learning Mode
```
HackRF Spectrum Monitor - Learning Mode
========================================
Frequency Range: 88.0 - 108.0 MHz
Baseline File: baselines.npz

Scanning spectrum... Press any key to stop and save baselines.

Sweep 1: 234 new maxima found (94.2% bins updated)
Sweep 2: 156 new maxima found (62.6% bins updated)  
Sweep 3: 89 new maxima found (35.7% bins updated)
Sweep 4: 23 new maxima found (9.2% bins updated)
...

Learning stopped. Saving 1000 spectra to baselines.npz
Baseline profile saved successfully.
```

### Monitoring Mode
```
HackRF Spectrum Monitor - Monitoring Mode  
==========================================
Frequency Range: 88.0 - 108.0 MHz
Baseline File: baselines.npz (loaded successfully)
Threshold Buffer: 10.0 dB

Controls: [+/-] Adjust threshold | [r] Reset | [s] Stats | [q] Quit

Monitoring... No alerts detected.

🚨 ALERT DETECTED 🚨
Frequency: 101.1 MHz
Signal: -45.2 dBm (15.3 dB above baseline)
Threshold exceeded by: 5.3 dB

Monitoring... No alerts detected.
```

## Troubleshooting

### HackRF Not Found
```bash
# Check if HackRF is connected
hackrf_info

# Verify library installation
ldconfig -p | grep hackrf
```

### Permission Issues
```bash
# Add user to plugdev group
sudo usermod -a -G plugdev $USER
# Logout and login again
```

### Poor Performance
- Reduce frequency range in config
- Increase bin_width for faster sweeps
- Lower update_rate_hz if system is overloaded 