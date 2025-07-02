"""
HackRF Interface Module
Provides Python interface to the hackrf_sweeper library.
"""

import ctypes
import ctypes.util
import numpy as np
import threading
import time
import os
import sys
from typing import Callable, Optional, List, Tuple
from PyQt5.QtCore import QObject, pyqtSignal

# Constants from hackrf_sweeper.h and hackrf.h
FREQ_ONE_MHZ = 1000000
FREQ_MIN_MHZ = 0
FREQ_MAX_MHZ = 7250
DEFAULT_SAMPLE_RATE_HZ = 20000000
DEFAULT_BASEBAND_FILTER_BANDWIDTH = 15000000
TUNE_STEP = DEFAULT_SAMPLE_RATE_HZ // FREQ_ONE_MHZ
MAX_SWEEP_RANGES = 10

# Additional sweep constants
BYTES_PER_BLOCK = 16384
OFFSET = 7500000  # Hz
INTERLEAVED = 1

# Output modes
HACKRF_SWEEP_OUTPUT_MODE_TEXT = 0
HACKRF_SWEEP_OUTPUT_MODE_BINARY = 1
HACKRF_SWEEP_OUTPUT_MODE_IFFT = 2

# Output types
HACKRF_SWEEP_OUTPUT_TYPE_NOP = 0
HACKRF_SWEEP_OUTPUT_TYPE_FILE = 1

# FFTW plan types
FFTW_ESTIMATE = 64
FFTW_MEASURE = 0
FFTW_PATIENT = 32
FFTW_EXHAUSTIVE = 8

# HackRF errors
HACKRF_SUCCESS = 0
HACKRF_ERROR_INVALID_PARAM = -2
HACKRF_ERROR_NOT_FOUND = -5
HACKRF_ERROR_BUSY = -6
HACKRF_ERROR_NO_MEM = -11
HACKRF_ERROR_LIBUSB = -1000
HACKRF_ERROR_THREAD = -1001
HACKRF_ERROR_STREAMING_THREAD_ERR = -1002
HACKRF_ERROR_STREAMING_STOPPED = -1003
HACKRF_ERROR_STREAMING_EXIT_CALLED = -1004
HACKRF_ERROR_OTHER = -9999

# Sweep specific errors
HACKRF_SWEEP_ERROR_INVALID_RANGE = -6000
HACKRF_SWEEP_ERROR_INCOMPATIBLE_MODE = -6001
HACKRF_SWEEP_ERROR_INVALID_RANGE_COUNT = -6002
HACKRF_SWEEP_ERROR_NOT_READY = -6003
HACKRF_SWEEP_ERROR_INVALID_FFT_SIZE = -6004


class HackRFSweepConfig:
    """Configuration parameters for HackRF sweep operations."""
    
    def __init__(self):
        self.serial_number = ""
        self.amp_enable = False
        self.antenna_enable = False
        self.freq_min_mhz = 0
        self.freq_max_mhz = 6000
        self.lna_gain = 16  # 0-40dB, 8dB steps
        self.vga_gain = 20  # 0-62dB, 2dB steps
        self.bin_width = 1000000  # Hz, 2445-5000000
        self.fftw_plan_type = "measure"  # estimate|measure|patient|exhaustive
        self.one_shot = False
        self.num_sweeps = 0  # 0 = infinite
        self.output_mode = "text"  # text|binary|ifft
        self.normalized_timestamp = False
        self.wisdom_file = ""


class HackRFTransfer(ctypes.Structure):
    """ctypes structure for hackrf_transfer."""
    _fields_ = [
        ("device", ctypes.c_void_p),
        ("buffer", ctypes.POINTER(ctypes.c_uint8)),
        ("buffer_length", ctypes.c_int),
        ("valid_length", ctypes.c_int),
        ("rx_ctx", ctypes.c_void_p),
        ("tx_ctx", ctypes.c_void_p)
    ]


class HackRFSweepFFTCtx(ctypes.Structure):
    """ctypes structure for hackrf_sweep_fft_ctx_t."""
    _fields_ = [
        ("size", ctypes.c_int),
        ("bin_width", ctypes.c_double),
        ("plan_type", ctypes.c_int),
        ("ifft_idx", ctypes.c_uint32),
        ("fftw_in", ctypes.c_void_p),
        ("fftw_out", ctypes.c_void_p),
        ("ifftw_in", ctypes.c_void_p),
        ("ifftw_out", ctypes.c_void_p),
        ("plan", ctypes.c_void_p),
        ("plan_inverted", ctypes.c_void_p),
        ("pwr", ctypes.POINTER(ctypes.c_float)),
        ("window", ctypes.POINTER(ctypes.c_float))
    ]


class HackRFSweepState(ctypes.Structure):
    """ctypes structure for hackrf_sweep_state_t."""
    _fields_ = [
        ("max_sweeps", ctypes.c_uint32),
        ("usb_transfer_time", ctypes.c_int64 * 2),  # timeval
        ("frequencies", ctypes.c_uint16 * (MAX_SWEEP_RANGES * 2)),
        ("num_ranges", ctypes.c_int),
        ("tune_step", ctypes.c_uint32),
        ("step_count", ctypes.c_int),
        ("device", ctypes.c_void_p),
        ("output_mode", ctypes.c_int),
        ("output_type", ctypes.c_int),
        ("output", ctypes.c_void_p),
        ("ext_cb_sample_block", ctypes.c_void_p),
        ("ext_cb_fft_ready", ctypes.c_void_p),
        ("fft", HackRFSweepFFTCtx),
        ("flags", ctypes.c_uint),
        ("sweep_count", ctypes.c_uint64),
        ("byte_count", ctypes.c_uint32),
        ("blocks_per_xfer", ctypes.c_int),
        ("sample_rate_hz", ctypes.c_uint64),
        ("write_mutex", ctypes.c_void_p),
        ("mutex_lock", ctypes.c_void_p),
        ("mutex_unlock", ctypes.c_void_p)
    ]


# Callback function types
FFTReadyCallback = ctypes.CFUNCTYPE(
    ctypes.c_int,                    # return type
    ctypes.c_void_p,                 # sweep_state
    ctypes.c_uint64,                 # frequency
    ctypes.POINTER(HackRFTransfer)   # transfer
)

SampleBlockCallback = ctypes.CFUNCTYPE(
    ctypes.c_int,                    # return type
    ctypes.c_void_p,                 # sweep_state
    ctypes.POINTER(HackRFTransfer)   # transfer
)


class HackRFInterface(QObject):
    """Interface to HackRF sweep functionality."""
    
    # Qt signals for UI updates
    spectrum_data_ready = pyqtSignal(np.ndarray, np.ndarray)  # frequencies, power_levels
    sweep_status_changed = pyqtSignal(str)  # status message
    error_occurred = pyqtSignal(str)  # error message
    sweep_stats_updated = pyqtSignal(int, float, float)  # sweep_count, sweep_rate, data_rate
    
    def __init__(self):
        super().__init__()
        self.config = HackRFSweepConfig()
        self.is_running = False
        self.sweep_thread = None
        self.latest_spectrum = None
        self.latest_frequencies = None
        
        # User's requested frequency range (for filtering extended sweep data)
        self.user_freq_min = 0
        self.user_freq_max = 6000
        
        # Library references
        self.hackrf_lib = None
        self.sweeper_lib = None
        self.device = None
        self.sweep_state = None
        
        # Callback references (must be kept alive)
        self.fft_callback_ref = None
        
        # Load libraries
        self._load_libraries()
    
    def _load_libraries(self):
        """Load the HackRF and sweeper libraries using ctypes."""
        try:
            # Load base HackRF library
            lib_path = ctypes.util.find_library('hackrf')
            if lib_path:
                self.hackrf_lib = ctypes.CDLL(lib_path)
                self._setup_hackrf_prototypes()
            else:
                self.error_occurred.emit("Could not find libhackrf. Please install libhackrf-dev.")
                return False
            
            # Load sweeper library
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sweeper_lib_path = os.path.join(project_root, "build", "libhackrf_sweeper.a")
            
            if os.path.exists(sweeper_lib_path):
                # For static library, we need to link it differently
                # Try to load it as a shared library first, if available
                sweeper_so_path = os.path.join(project_root, "build", "libhackrf_sweeper.so")
                if os.path.exists(sweeper_so_path):
                    self.sweeper_lib = ctypes.CDLL(sweeper_so_path)
                else:
                    # Use system libhackrf with sweep functions if available
                    self.sweeper_lib = self.hackrf_lib
                
                self._setup_sweeper_prototypes()
            else:
                self.error_occurred.emit(
                    f"Could not find hackrf_sweeper library at {sweeper_lib_path}. "
                    "Please build the project first with 'make' in the build directory."
                )
                return False
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Error loading libraries: {str(e)}")
            return False
    
    def _setup_hackrf_prototypes(self):
        """Setup ctypes function prototypes for the HackRF library."""
        if not self.hackrf_lib:
            return
        
        try:
            # Basic HackRF functions
            self.hackrf_lib.hackrf_init.restype = ctypes.c_int
            self.hackrf_lib.hackrf_exit.restype = ctypes.c_int
            
            # Device functions
            self.hackrf_lib.hackrf_open.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
            self.hackrf_lib.hackrf_open.restype = ctypes.c_int
            
            self.hackrf_lib.hackrf_open_by_serial.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
            self.hackrf_lib.hackrf_open_by_serial.restype = ctypes.c_int
            
            self.hackrf_lib.hackrf_close.argtypes = [ctypes.c_void_p]
            self.hackrf_lib.hackrf_close.restype = ctypes.c_int
            
            # Settings functions
            self.hackrf_lib.hackrf_set_sample_rate_manual.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
            self.hackrf_lib.hackrf_set_sample_rate_manual.restype = ctypes.c_int
            
            self.hackrf_lib.hackrf_set_baseband_filter_bandwidth.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self.hackrf_lib.hackrf_set_baseband_filter_bandwidth.restype = ctypes.c_int
            
            self.hackrf_lib.hackrf_set_vga_gain.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self.hackrf_lib.hackrf_set_vga_gain.restype = ctypes.c_int
            
            self.hackrf_lib.hackrf_set_lna_gain.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self.hackrf_lib.hackrf_set_lna_gain.restype = ctypes.c_int
            
            self.hackrf_lib.hackrf_set_amp_enable.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
            self.hackrf_lib.hackrf_set_amp_enable.restype = ctypes.c_int
            
            self.hackrf_lib.hackrf_set_antenna_enable.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
            self.hackrf_lib.hackrf_set_antenna_enable.restype = ctypes.c_int
            
            self.hackrf_lib.hackrf_is_streaming.argtypes = [ctypes.c_void_p]
            self.hackrf_lib.hackrf_is_streaming.restype = ctypes.c_int
            
            # Sweep functions
            self.hackrf_lib.hackrf_init_sweep.argtypes = [
                ctypes.c_void_p,  # device
                ctypes.POINTER(ctypes.c_uint16),  # frequency_list
                ctypes.c_int,     # num_ranges
                ctypes.c_uint32,  # num_bytes
                ctypes.c_uint32,  # step_width
                ctypes.c_uint32,  # offset
                ctypes.c_int      # style
            ]
            self.hackrf_lib.hackrf_init_sweep.restype = ctypes.c_int
            
            self.hackrf_lib.hackrf_start_rx_sweep.argtypes = [
                ctypes.c_void_p,  # device
                ctypes.c_void_p,  # callback
                ctypes.c_void_p   # rx_ctx
            ]
            self.hackrf_lib.hackrf_start_rx_sweep.restype = ctypes.c_int
            
        except Exception as e:
            self.error_occurred.emit(f"Error setting up HackRF function prototypes: {str(e)}")
    
    def _setup_sweeper_prototypes(self):
        """Setup ctypes function prototypes for the sweeper library."""
        if not self.sweeper_lib:
            return
        
        try:
            # Check if sweep functions are available
            if hasattr(self.sweeper_lib, 'hackrf_sweep_easy_init'):
                # Sweep initialization
                self.sweeper_lib.hackrf_sweep_easy_init.argtypes = [ctypes.c_void_p, ctypes.POINTER(HackRFSweepState)]
                self.sweeper_lib.hackrf_sweep_easy_init.restype = ctypes.c_int
                
                # Sweep configuration
                self.sweeper_lib.hackrf_sweep_set_output.argtypes = [
                    ctypes.POINTER(HackRFSweepState), ctypes.c_int, ctypes.c_int, ctypes.c_void_p
                ]
                self.sweeper_lib.hackrf_sweep_set_output.restype = ctypes.c_int
                
                self.sweeper_lib.hackrf_sweep_set_range.argtypes = [
                    ctypes.POINTER(HackRFSweepState), 
                    ctypes.POINTER(ctypes.c_uint16),
                    ctypes.c_size_t
                ]
                self.sweeper_lib.hackrf_sweep_set_range.restype = ctypes.c_int
                
                self.sweeper_lib.hackrf_sweep_setup_fft.argtypes = [
                    ctypes.POINTER(HackRFSweepState), ctypes.c_int, ctypes.c_uint32
                ]
                self.sweeper_lib.hackrf_sweep_setup_fft.restype = ctypes.c_int
                
                # Sweep control
                self.sweeper_lib.hackrf_sweep_start.argtypes = [ctypes.POINTER(HackRFSweepState), ctypes.c_int]
                self.sweeper_lib.hackrf_sweep_start.restype = ctypes.c_int
                
                self.sweeper_lib.hackrf_sweep_stop.argtypes = [ctypes.POINTER(HackRFSweepState)]
                self.sweeper_lib.hackrf_sweep_stop.restype = ctypes.c_int
                
                self.sweeper_lib.hackrf_sweep_close.argtypes = [ctypes.POINTER(HackRFSweepState)]
                self.sweeper_lib.hackrf_sweep_close.restype = ctypes.c_int
                
                # Callbacks
                self.sweeper_lib.hackrf_sweep_set_fft_rx_callback.argtypes = [
                    ctypes.POINTER(HackRFSweepState), FFTReadyCallback
                ]
                self.sweeper_lib.hackrf_sweep_set_fft_rx_callback.restype = ctypes.c_int
                
                # Wisdom
                self.sweeper_lib.hackrf_sweep_import_wisdom.argtypes = [
                    ctypes.POINTER(HackRFSweepState), ctypes.c_char_p
                ]
                self.sweeper_lib.hackrf_sweep_import_wisdom.restype = ctypes.c_int
                
                self.sweeper_lib.hackrf_sweep_export_wisdom.argtypes = [
                    ctypes.POINTER(HackRFSweepState), ctypes.c_char_p
                ]
                self.sweeper_lib.hackrf_sweep_export_wisdom.restype = ctypes.c_int
                
            else:
                # Fallback to simulation mode
                self.sweeper_lib = None
                self.error_occurred.emit("Sweep functions not available. Using simulation mode.")
                
        except Exception as e:
            self.error_occurred.emit(f"Error setting up sweeper function prototypes: {str(e)}")
    
    def _fft_ready_callback(self, sweep_state_ptr, frequency, transfer_ptr):
        """Callback function for FFT data ready."""
        try:
            # Dereference the sweep state
            if not sweep_state_ptr:
                return 0
            
            sweep_state = ctypes.cast(sweep_state_ptr, ctypes.POINTER(HackRFSweepState)).contents
            
            # Get FFT data
            fft_ctx = sweep_state.fft
            if fft_ctx.pwr and fft_ctx.size > 0:
                # Convert full power array from C
                full_power_array = np.ctypeslib.as_array(fft_ctx.pwr, shape=(fft_ctx.size,))
                
                # Extract frequency bins using same logic as C library (skips DC bin)
                # This follows the same bin selection as hackrf_sweeper.c to avoid DC spike
                
                # First segment indices: i + 1 + (fft_size * 5) / 8
                # Second segment indices: i + 1 + (fft_size / 8)
                segment_size = fft_ctx.size // 4
                
                # First segment (upper part of spectrum)
                first_start_idx = 1 + (fft_ctx.size * 5) // 8
                first_power = full_power_array[first_start_idx:first_start_idx + segment_size]
                
                # Second segment (lower part of spectrum) 
                second_start_idx = 1 + fft_ctx.size // 8
                second_power = full_power_array[second_start_idx:second_start_idx + segment_size]
                
                # Combine segments in correct frequency order (low to high)
                power_array = np.concatenate([second_power, first_power])
                
                # Calculate corresponding frequency arrays
                sample_rate_hz = DEFAULT_SAMPLE_RATE_HZ
                freq_center_hz = frequency
                
                # Frequency ranges for each segment
                # Second segment: center - 3/8 * sample_rate to center - 1/8 * sample_rate
                # First segment: center + 1/8 * sample_rate to center + 3/8 * sample_rate
                
                second_freq_start = (freq_center_hz - (sample_rate_hz * 3) // 8) / FREQ_ONE_MHZ
                second_freq_end = (freq_center_hz - sample_rate_hz // 8) / FREQ_ONE_MHZ
                
                first_freq_start = (freq_center_hz + sample_rate_hz // 8) / FREQ_ONE_MHZ
                first_freq_end = (freq_center_hz + (sample_rate_hz * 3) // 8) / FREQ_ONE_MHZ
                
                second_freqs = np.linspace(second_freq_start, second_freq_end, segment_size)
                first_freqs = np.linspace(first_freq_start, first_freq_end, segment_size)
                
                # Combine frequency arrays (low to high)
                freq_array = np.concatenate([second_freqs, first_freqs])
                
                # Filter to only include frequencies within user's requested range
                # This ensures complete coverage while discarding data beyond stop frequency
                if hasattr(self, 'user_freq_min') and hasattr(self, 'user_freq_max'):
                    # Create mask for frequencies within user's range
                    freq_mask = (freq_array >= self.user_freq_min) & (freq_array <= self.user_freq_max)
                    
                    # Apply mask to both frequency and power arrays
                    filtered_freq_array = freq_array[freq_mask]
                    filtered_power_array = power_array[freq_mask]
                    
                    # Only emit if we have data within the requested range
                    if len(filtered_freq_array) > 0:
                        self.spectrum_data_ready.emit(filtered_freq_array, filtered_power_array.copy())
                else:
                    # Fallback: emit all data if range filtering not set up
                    self.spectrum_data_ready.emit(freq_array, power_array.copy())
            
            return 0  # Continue receiving callbacks
            
        except Exception as e:
            print(f"Error in FFT callback: {e}")
            return 1  # Stop callbacks on error
    
    def start_sweep(self, force_simulation=False):
        """Start the spectrum sweep operation."""
        if self.is_running:
            return
        
        if not self.hackrf_lib:
            self.error_occurred.emit("HackRF library not loaded")
            return
        
        self.is_running = True
        
        if (not force_simulation and 
            self.sweeper_lib and 
            hasattr(self.sweeper_lib, 'hackrf_sweep_easy_init')):
            # Use real sweep library
            self.sweep_thread = threading.Thread(target=self._real_sweep_worker, daemon=True)
        else:
            # Use simulation
            self.sweep_thread = threading.Thread(target=self._simulation_sweep_worker, daemon=True)
        
        self.sweep_thread.start()
        self.sweep_status_changed.emit("Starting sweep...")
    
    def stop_sweep(self):
        """Stop the spectrum sweep operation."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Stop real sweep if running
        if self.sweep_state and self.sweeper_lib:
            try:
                self.sweeper_lib.hackrf_sweep_stop(ctypes.byref(self.sweep_state))
            except Exception as e:
                print(f"Error stopping sweep: {e}")
        
        if self.sweep_thread:
            self.sweep_thread.join(timeout=5.0)
        
        self.sweep_status_changed.emit("Sweep stopped")
    
    def _real_sweep_worker(self):
        """Worker thread for real sweep operations."""
        try:
            # Initialize HackRF
            result = self.hackrf_lib.hackrf_init()
            if result != HACKRF_SUCCESS:
                self.sweep_status_changed.emit("No HackRF device found, using simulation...")
                self._simulation_sweep_worker()
                return
            
            # Open device
            device_ptr = ctypes.c_void_p()
            if self.config.serial_number:
                result = self.hackrf_lib.hackrf_open_by_serial(
                    self.config.serial_number.encode('utf-8'),
                    ctypes.byref(device_ptr)
                )
            else:
                result = self.hackrf_lib.hackrf_open(ctypes.byref(device_ptr))
            
            if result != HACKRF_SUCCESS:
                self.sweep_status_changed.emit("Cannot open HackRF device, using simulation...")
                self._simulation_sweep_worker()
                return
            
            self.device = device_ptr
            
            # Configure device
            self._configure_device()
            
            # Initialize sweep state
            self.sweep_state = HackRFSweepState()
            result = self.sweeper_lib.hackrf_sweep_easy_init(self.device, ctypes.byref(self.sweep_state))
            if result != HACKRF_SUCCESS:
                self.error_occurred.emit(f"Failed to initialize sweep (error {result})")
                return
            
            # Configure sweep parameters (this should handle hardware initialization internally)
            self._configure_sweep()
            
            # Set up callback
            self.fft_callback_ref = FFTReadyCallback(self._fft_ready_callback)
            result = self.sweeper_lib.hackrf_sweep_set_fft_rx_callback(
                ctypes.byref(self.sweep_state),
                self.fft_callback_ref
            )
            if result != HACKRF_SUCCESS:
                self.error_occurred.emit(f"Failed to set FFT callback (error {result})")
                return
            
            # Start sweep using sweeper library
            max_sweeps = self.config.num_sweeps if self.config.num_sweeps > 0 else 0
            result = self.sweeper_lib.hackrf_sweep_start(ctypes.byref(self.sweep_state), max_sweeps)
            if result != HACKRF_SUCCESS:
                self.error_occurred.emit(f"Failed to start sweep (error {result})")
                return
            
            self.sweep_status_changed.emit("Sweep running...")
            
            # Monitor sweep
            sweep_count = 0
            while self.is_running and self.hackrf_lib.hackrf_is_streaming(self.device):
                time.sleep(0.1)
                
                # Update statistics periodically
                sweep_count += 1
                if sweep_count % 50 == 0:  # Every 5 seconds
                    self.sweep_stats_updated.emit(sweep_count, 10.0, 1024.0)
                
                if self.config.one_shot:
                    break
            
        except Exception as e:
            self.error_occurred.emit(f"Sweep error: {str(e)}")
        finally:
            self._cleanup_real_sweep()
    
    def _simulation_sweep_worker(self):
        """Worker thread for simulated sweep operations (fallback)."""
        try:
            self.sweep_status_changed.emit("Running in simulation mode...")
            
            # Store user's requested range for filtering (same as real sweep)
            self.user_freq_min = self.config.freq_min_mhz
            self.user_freq_max = self.config.freq_max_mhz
            
            # Use extended range for simulation to match real behavior
            segment_bandwidth_mhz = DEFAULT_SAMPLE_RATE_HZ * 0.75 / FREQ_ONE_MHZ  # ~15 MHz
            sim_freq_start = self.config.freq_min_mhz
            sim_freq_end = self.config.freq_max_mhz + segment_bandwidth_mhz
            
            print(f"Simulation - User requested: {self.user_freq_min:.1f} - {self.user_freq_max:.1f} MHz")
            print(f"Simulation - Extended range: {sim_freq_start:.1f} - {sim_freq_end:.1f} MHz")
            
            sweep_count = 0
            while self.is_running:
                # Generate simulated spectrum data over extended range
                num_points = max(100, int((sim_freq_end - sim_freq_start) * 10))  # 10 points per MHz
                
                frequencies = np.linspace(sim_freq_start, sim_freq_end, num_points)
                
                # Simulate noise floor and signals
                power_levels = -90 + 15 * np.random.randn(num_points)
                
                # Add some simulated signals
                signal_freqs = [88.5, 101.1, 433.92, 915.0, 1090.0, 2400.0, 2442.0, 2484.0]  # Added more Bluetooth signals
                for sig_freq in signal_freqs:
                    if sim_freq_start <= sig_freq <= sim_freq_end:
                        # Find closest frequency bin
                        idx = np.argmin(np.abs(frequencies - sig_freq))
                        power_levels[idx] += 40 + 10 * np.random.randn()
                
                # Filter to user's requested range (same logic as real sweep)
                freq_mask = (frequencies >= self.user_freq_min) & (frequencies <= self.user_freq_max)
                filtered_frequencies = frequencies[freq_mask]
                filtered_power_levels = power_levels[freq_mask]
                
                # Only emit if we have data within the requested range
                if len(filtered_frequencies) > 0:
                    self.spectrum_data_ready.emit(filtered_frequencies, filtered_power_levels)
                
                sweep_count += 1
                if sweep_count % 10 == 0:
                    self.sweep_stats_updated.emit(sweep_count, 10.0, 1024.0)
                
                time.sleep(0.1)  # 10 Hz update rate
                
                if self.config.one_shot:
                    break
            
        except Exception as e:
            self.error_occurred.emit(f"Simulation error: {str(e)}")
        finally:
            self.is_running = False
            self.sweep_status_changed.emit("Simulation completed")
    
    def _configure_device(self):
        """Configure HackRF device settings."""
        if not self.device or not self.hackrf_lib:
            return
        
        try:
            # Set sample rate
            result = self.hackrf_lib.hackrf_set_sample_rate_manual(
                self.device, DEFAULT_SAMPLE_RATE_HZ, 1
            )
            if result != HACKRF_SUCCESS:
                self.error_occurred.emit(f"Failed to set sample rate (error {result})")
                return
            
            # Set baseband filter
            result = self.hackrf_lib.hackrf_set_baseband_filter_bandwidth(
                self.device, DEFAULT_BASEBAND_FILTER_BANDWIDTH
            )
            if result != HACKRF_SUCCESS:
                self.error_occurred.emit(f"Failed to set baseband filter (error {result})")
                return
            
            # Set gains
            result = self.hackrf_lib.hackrf_set_vga_gain(self.device, self.config.vga_gain)
            if result != HACKRF_SUCCESS:
                self.error_occurred.emit(f"Failed to set VGA gain (error {result})")
                return
            
            result = self.hackrf_lib.hackrf_set_lna_gain(self.device, self.config.lna_gain)
            if result != HACKRF_SUCCESS:
                self.error_occurred.emit(f"Failed to set LNA gain (error {result})")
                return
            
            # Set amp if enabled
            if self.config.amp_enable:
                result = self.hackrf_lib.hackrf_set_amp_enable(self.device, 1)
                if result != HACKRF_SUCCESS:
                    self.error_occurred.emit(f"Failed to enable amp (error {result})")
                    return
            
            # Set antenna power if enabled
            if self.config.antenna_enable:
                result = self.hackrf_lib.hackrf_set_antenna_enable(self.device, 1)
                if result != HACKRF_SUCCESS:
                    self.error_occurred.emit(f"Failed to enable antenna power (error {result})")
                    return
            
        except Exception as e:
            self.error_occurred.emit(f"Error configuring device: {str(e)}")
    
    def _configure_sweep(self):
        """Configure sweep parameters."""
        if not self.sweep_state or not self.sweeper_lib:
            return
        
        try:
            # Set output mode (using NOP for callback mode)
            result = self.sweeper_lib.hackrf_sweep_set_output(
                ctypes.byref(self.sweep_state),
                HACKRF_SWEEP_OUTPUT_MODE_TEXT,
                HACKRF_SWEEP_OUTPUT_TYPE_NOP,
                None
            )
            if result != HACKRF_SUCCESS:
                self.error_occurred.emit(f"Failed to set output mode (error {result})")
                return
            
            # Extend frequency range to ensure complete coverage of requested range
            # Each sweep segment has bandwidth ~= sample_rate * 0.75 = 15 MHz
            # We need to extend beyond max frequency to capture the final portion
            segment_bandwidth_mhz = DEFAULT_SAMPLE_RATE_HZ * 0.75 / FREQ_ONE_MHZ  # ~15 MHz
            
            # Store user's requested range for filtering
            self.user_freq_min = self.config.freq_min_mhz
            self.user_freq_max = self.config.freq_max_mhz
            
            # Extend hardware sweep range to ensure complete coverage
            hw_freq_min = int(self.config.freq_min_mhz)
            hw_freq_max = int(self.config.freq_max_mhz + segment_bandwidth_mhz)
            
            print(f"User requested range: {self.user_freq_min:.1f} - {self.user_freq_max:.1f} MHz")
            print(f"Hardware sweep range: {hw_freq_min} - {hw_freq_max} MHz (extended for complete coverage)")
            
            freq_list = (ctypes.c_uint16 * 2)()
            freq_list[0] = hw_freq_min
            freq_list[1] = hw_freq_max
            
            result = self.sweeper_lib.hackrf_sweep_set_range(
                ctypes.byref(self.sweep_state),
                freq_list,
                1  # One range
            )
            if result != HACKRF_SUCCESS:
                self.error_occurred.emit(f"Failed to set frequency range (error {result})")
                return
            
            # Load wisdom if specified
            if self.config.wisdom_file:
                wisdom_path = self.config.wisdom_file.encode('utf-8')
                self.sweeper_lib.hackrf_sweep_import_wisdom(
                    ctypes.byref(self.sweep_state),
                    wisdom_path
                )
            else:
                self.sweeper_lib.hackrf_sweep_import_wisdom(
                    ctypes.byref(self.sweep_state),
                    None
                )
            
            # Set up FFT
            fftw_plan_map = {
                "estimate": FFTW_ESTIMATE,
                "measure": FFTW_MEASURE,
                "patient": FFTW_PATIENT,
                "exhaustive": FFTW_EXHAUSTIVE
            }
            plan_type = fftw_plan_map.get(self.config.fftw_plan_type, FFTW_MEASURE)
            
            result = self.sweeper_lib.hackrf_sweep_setup_fft(
                ctypes.byref(self.sweep_state),
                plan_type,
                self.config.bin_width
            )
            if result != HACKRF_SUCCESS:
                self.error_occurred.emit(f"Failed to setup FFT (error {result})")
                return
            
        except Exception as e:
            self.error_occurred.emit(f"Error configuring sweep: {str(e)}")
    
    def _cleanup_real_sweep(self):
        """Clean up real sweep resources."""
        try:
            if self.sweep_state and self.sweeper_lib:
                self.sweeper_lib.hackrf_sweep_close(ctypes.byref(self.sweep_state))
                self.sweep_state = None
            
            if self.device and self.hackrf_lib:
                self.hackrf_lib.hackrf_close(self.device)
                self.device = None
                self.hackrf_lib.hackrf_exit()
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
        finally:
            self.is_running = False
    
    def update_config(self, config: HackRFSweepConfig):
        """Update the sweep configuration."""
        self.config = config
    
    def get_device_list(self) -> List[str]:
        """Get list of available HackRF devices."""
        # TODO: Implement device enumeration
        return ["HackRF One (auto-detect)"]
    
    def validate_config(self) -> Tuple[bool, str]:
        """Validate the current configuration."""
        if self.config.freq_min_mhz >= self.config.freq_max_mhz:
            return False, "Minimum frequency must be less than maximum frequency"
        
        if self.config.freq_min_mhz < FREQ_MIN_MHZ or self.config.freq_max_mhz > FREQ_MAX_MHZ:
            return False, f"Frequency range must be between {FREQ_MIN_MHZ} and {FREQ_MAX_MHZ} MHz"
        
        if self.config.lna_gain % 8 != 0:
            return False, "LNA gain must be a multiple of 8"
        
        if self.config.vga_gain % 2 != 0:
            return False, "VGA gain must be a multiple of 2"
        
        if self.config.bin_width < 2445 or self.config.bin_width > 5000000:
            return False, "FFT bin width must be between 2445 and 5000000 Hz"
        
        return True, "Configuration is valid" 