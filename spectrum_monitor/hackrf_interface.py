"""
HackRF Interface Module (CLI Version)
Provides CLI-compatible Python interface to the hackrf_sweeper library.
Adapted from the original Qt-based interface for command-line use.
"""

import ctypes
import ctypes.util
import numpy as np
import threading
import time
import os
import sys
from typing import Callable, Optional, List, Tuple

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
        self.dc_spike_removal = True  # Enable DC spike removal
        self.dc_spike_width = 3  # Number of bins around DC to remove (default: 3)


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


class HackRFInterface:
    """CLI-compatible interface to HackRF sweep functionality."""
    
    def __init__(self, data_callback: Optional[Callable] = None):
        """Initialize HackRF interface.
        
        Args:
            data_callback: Function called when new spectrum data arrives.
                          Signature: callback(frequencies, power_levels)
        """
        self.config = HackRFSweepConfig()
        self.is_running = False
        self.sweep_thread = None
        self.latest_spectrum = None
        self.latest_frequencies = None
        self.data_callback = data_callback
        
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
        
        # Statistics
        self.sweep_count = 0
        self.last_sweep_time = 0
        self.sweep_rate = 0.0
        
        # Load libraries
        self._load_libraries()
    
    def _remove_dc_spike(self, frequencies: np.ndarray, power_levels: np.ndarray, 
                         dc_spike_width: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """Remove DC spike from spectrum data by replacing spike values.
        
        This method preserves the array length and frequency mapping by replacing
        DC spike values with interpolated values from surrounding bins.
        
        Args:
            frequencies: Frequency array in MHz
            power_levels: Power levels in dB
            dc_spike_width: Number of bins around DC to replace (default: 3)
            
        Returns:
            Tuple of (frequencies, modified_power_levels) - arrays maintain same length
        """
        if len(frequencies) == 0 or len(power_levels) == 0:
            return frequencies, power_levels
        
        # Find the DC bin (closest to 0 frequency offset)
        freq_center = (frequencies[0] + frequencies[-1]) / 2
        freq_offsets = np.abs(frequencies - freq_center)
        dc_bin_idx = np.argmin(freq_offsets)
        
        # Calculate range of bins to replace around DC
        start_idx = max(0, dc_bin_idx - dc_spike_width)
        end_idx = min(len(frequencies), dc_bin_idx + dc_spike_width + 1)
        
        # Create a copy of power levels to modify
        modified_power_levels = power_levels.copy()
        
        # Replace DC spike region with interpolated values
        if start_idx > 0 and end_idx < len(frequencies):
            # We have valid bins on both sides, interpolate
            left_value = power_levels[start_idx - 1]
            right_value = power_levels[end_idx]
            
            # Linear interpolation across the DC spike region
            for i in range(start_idx, end_idx):
                # Weight based on distance from left edge
                weight = (i - start_idx) / (end_idx - start_idx)
                interpolated_value = left_value * (1 - weight) + right_value * weight
                modified_power_levels[i] = interpolated_value
        elif start_idx > 0:
            # Only left side available, use left value
            left_value = power_levels[start_idx - 1]
            modified_power_levels[start_idx:end_idx] = left_value
        elif end_idx < len(power_levels):
            # Only right side available, use right value
            right_value = power_levels[end_idx]
            modified_power_levels[start_idx:end_idx] = right_value
        else:
            # No valid bins on either side, use mean of all values
            mean_value = np.mean(power_levels)
            modified_power_levels[start_idx:end_idx] = mean_value
        
        return frequencies, modified_power_levels
    
    def _load_libraries(self):
        """Load the HackRF and sweeper libraries using ctypes."""
        print(f"DEBUG: Loading HackRF libraries...")
        try:
            # Load base HackRF library
            lib_path = ctypes.util.find_library('hackrf')
            print(f"DEBUG: HackRF library path: {lib_path}")
            if lib_path:
                self.hackrf_lib = ctypes.CDLL(lib_path)
                self._setup_hackrf_prototypes()
                print("DEBUG: HackRF library loaded successfully")
            else:
                raise RuntimeError("Could not find libhackrf. Please install libhackrf-dev.")
            
            # Try to load sweeper library (may not be available)
            sweeper_lib_path = ctypes.util.find_library('hackrf_sweeper')
            print(f"DEBUG: System HackRF sweeper library path: {sweeper_lib_path}")
            
            # If not found in system, try local build directory
            if not sweeper_lib_path:
                local_sweeper_paths = [
                    "../build/libhackrf_sweeper.so",
                    "../../build/libhackrf_sweeper.so",
                    "./build/libhackrf_sweeper.so",
                ]
                for path in local_sweeper_paths:
                    if os.path.exists(path):
                        sweeper_lib_path = path
                        print(f"DEBUG: Found local HackRF sweeper library: {sweeper_lib_path}")
                        break
            
            if sweeper_lib_path:
                self.sweeper_lib = ctypes.CDLL(sweeper_lib_path)
                self._setup_sweeper_prototypes()
                print("DEBUG: HackRF sweeper library loaded successfully")
            else:
                print("DEBUG: hackrf_sweeper library not found," )
                exit(1)
                
        except Exception as e:
            print(f"DEBUG: Error loading HackRF libraries: {e}")
            exit(1)
    
    def _setup_hackrf_prototypes(self):
        """Set up ctypes function prototypes for HackRF library."""
        # Basic HackRF functions
        self.hackrf_lib.hackrf_init.restype = ctypes.c_int
        self.hackrf_lib.hackrf_exit.restype = ctypes.c_int
        self.hackrf_lib.hackrf_open.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        self.hackrf_lib.hackrf_open.restype = ctypes.c_int
        self.hackrf_lib.hackrf_close.argtypes = [ctypes.c_void_p]
        self.hackrf_lib.hackrf_close.restype = ctypes.c_int
        
        # Gain control functions
        self.hackrf_lib.hackrf_set_lna_gain.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.hackrf_lib.hackrf_set_lna_gain.restype = ctypes.c_int
        self.hackrf_lib.hackrf_set_vga_gain.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.hackrf_lib.hackrf_set_vga_gain.restype = ctypes.c_int
        self.hackrf_lib.hackrf_set_amp_enable.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
        self.hackrf_lib.hackrf_set_amp_enable.restype = ctypes.c_int
        self.hackrf_lib.hackrf_set_antenna_enable.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
        self.hackrf_lib.hackrf_set_antenna_enable.restype = ctypes.c_int
    
    def _setup_sweeper_prototypes(self):
        """Set up ctypes function prototypes for sweeper library."""
        if not self.sweeper_lib:
            return
            
        # Sweep initialization and cleanup
        # int hackrf_sweep_init(hackrf_device *device, hackrf_sweep_state_t *state, uint64_t sample_rate_hz, uint32_t tune_step)
        self.sweeper_lib.hackrf_sweep_init.argtypes = [
            ctypes.c_void_p,  # hackrf_device *device
            ctypes.POINTER(HackRFSweepState),  # hackrf_sweep_state_t *state
            ctypes.c_uint64,  # uint64_t sample_rate_hz
            ctypes.c_uint32   # uint32_t tune_step
        ]
        self.sweeper_lib.hackrf_sweep_init.restype = ctypes.c_int
        
        # int hackrf_sweep_close(hackrf_sweep_state_t *state)
        self.sweeper_lib.hackrf_sweep_close.argtypes = [ctypes.POINTER(HackRFSweepState)]
        self.sweeper_lib.hackrf_sweep_close.restype = ctypes.c_int
        
        # int hackrf_sweep_set_range(hackrf_sweep_state_t *state, uint16_t frequency_list[], size_t range_count)
        self.sweeper_lib.hackrf_sweep_set_range.argtypes = [
            ctypes.POINTER(HackRFSweepState),
            ctypes.POINTER(ctypes.c_uint16),  # uint16_t frequency_list[]
            ctypes.c_size_t                   # size_t range_count
        ]
        self.sweeper_lib.hackrf_sweep_set_range.restype = ctypes.c_int
        
        # int hackrf_sweep_setup_fft(hackrf_sweep_state_t *state, int plan_type, uint32_t requested_bin_width)
        self.sweeper_lib.hackrf_sweep_setup_fft.argtypes = [
            ctypes.POINTER(HackRFSweepState),
            ctypes.c_int,     # int plan_type
            ctypes.c_uint32   # uint32_t requested_bin_width
        ]
        self.sweeper_lib.hackrf_sweep_setup_fft.restype = ctypes.c_int
        
        # int hackrf_sweep_set_output(hackrf_sweep_state_t *state, hackrf_sweep_output_mode_t output_mode, hackrf_sweep_output_type_t output_type, void *arg)
        self.sweeper_lib.hackrf_sweep_set_output.argtypes = [
            ctypes.POINTER(HackRFSweepState),
            ctypes.c_int,     # hackrf_sweep_output_mode_t output_mode
            ctypes.c_int,     # hackrf_sweep_output_type_t output_type
            ctypes.c_void_p   # void *arg
        ]
        self.sweeper_lib.hackrf_sweep_set_output.restype = ctypes.c_int
        
        # int hackrf_sweep_set_fft_rx_callback(hackrf_sweep_state_t *state, hackrf_sweep_rx_cb_fn fft_ready_cb)
        self.sweeper_lib.hackrf_sweep_set_fft_rx_callback.argtypes = [
            ctypes.POINTER(HackRFSweepState),
            ctypes.c_void_p   # function pointer
        ]
        self.sweeper_lib.hackrf_sweep_set_fft_rx_callback.restype = ctypes.c_int
        
        # Sweep execution
        # int hackrf_sweep_start(hackrf_sweep_state_t *state, int max_sweeps)
        self.sweeper_lib.hackrf_sweep_start.argtypes = [
            ctypes.POINTER(HackRFSweepState),
            ctypes.c_int      # int max_sweeps
        ]
        self.sweeper_lib.hackrf_sweep_start.restype = ctypes.c_int
        
        # int hackrf_sweep_stop(hackrf_sweep_state_t *state)
        self.sweeper_lib.hackrf_sweep_stop.argtypes = [ctypes.POINTER(HackRFSweepState)]
        self.sweeper_lib.hackrf_sweep_stop.restype = ctypes.c_int
    
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
                second_freq_start = (freq_center_hz - (sample_rate_hz * 3) // 8) / FREQ_ONE_MHZ
                second_freq_end = (freq_center_hz - sample_rate_hz // 8) / FREQ_ONE_MHZ
                
                first_freq_start = (freq_center_hz + sample_rate_hz // 8) / FREQ_ONE_MHZ
                first_freq_end = (freq_center_hz + (sample_rate_hz * 3) // 8) / FREQ_ONE_MHZ
                
                second_freqs = np.linspace(second_freq_start, second_freq_end, segment_size)
                first_freqs = np.linspace(first_freq_start, first_freq_end, segment_size)
                
                # Combine frequency arrays (low to high)
                freq_array = np.concatenate([second_freqs, first_freqs])
                
                # Apply DC spike removal if enabled
                if hasattr(self.config, 'dc_spike_removal') and self.config.dc_spike_removal:
                    freq_array, power_array = self._remove_dc_spike(
                        freq_array, power_array, self.config.dc_spike_width
                    )
                
                # Filter to only include frequencies within user's requested range
                if hasattr(self, 'user_freq_min') and hasattr(self, 'user_freq_max'):
                    # Create mask for frequencies within user's range
                    freq_mask = (freq_array >= self.user_freq_min) & (freq_array <= self.user_freq_max)
                    
                    # Apply mask to both frequency and power arrays
                    filtered_freq_array = freq_array[freq_mask]
                    filtered_power_array = power_array[freq_mask]
                    
                    # Only emit if we have data within the requested range
                    if len(filtered_freq_array) > 0:
                        self._emit_spectrum_data(filtered_freq_array, filtered_power_array.copy())
                else:
                    # Fallback: emit all data if range filtering not set up
                    self._emit_spectrum_data(freq_array, power_array.copy())
                
                # Update statistics
                self.sweep_count += 1
                current_time = time.time()
                if self.last_sweep_time > 0:
                    self.sweep_rate = 1.0 / (current_time - self.last_sweep_time)
                self.last_sweep_time = current_time
            
            return 0  # Continue receiving callbacks
            
        except Exception as e:
            print(f"Error in FFT callback: {e}")
            return 1  # Stop callbacks on error
    
    def _emit_spectrum_data(self, frequencies, power_levels):
        """Emit spectrum data to callback or store locally."""
        self.latest_frequencies = frequencies
        self.latest_spectrum = power_levels
        
        if self.data_callback:
            self.data_callback(frequencies, power_levels)
    
    def set_data_callback(self, callback: Callable):
        """Set the callback function for spectrum data.
        
        Args:
            callback: Function called when new spectrum data arrives.
                     Signature: callback(frequencies, power_levels)
        """
        self.data_callback = callback
    
    def start_sweep(self):
        """Start spectrum sweep operation.
        

        """
        print(f"DEBUG: hackrf_lib available: {self.hackrf_lib is not None}")
        print(f"DEBUG: sweeper_lib available: {self.sweeper_lib is not None}")
        
        if self.is_running:
            return
        
        self.is_running = True
        self.sweep_count = 0
        self.last_sweep_time = 0
        
        # Set user frequency range for filtering
        self.user_freq_min = self.config.freq_min_mhz
        self.user_freq_max = self.config.freq_max_mhz
           

        print("DEBUG: Starting real HackRF sweep worker")
        self.sweep_thread = threading.Thread(target=self._real_sweep_worker)
        
        self.sweep_thread.daemon = True
        self.sweep_thread.start()
    
    def stop_sweep(self):
        """Stop spectrum sweep operation."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.sweep_thread and self.sweep_thread.is_alive():
            self.sweep_thread.join(timeout=2.0)
        
        self._cleanup_real_sweep()
    
    def _real_sweep_worker(self):
        """Real HackRF sweep worker thread."""
        try:
            print("DEBUG: Starting real sweep worker...")
            
            print("DEBUG: Configuring HackRF device...")
            if not self._configure_device():
                print("Failed to configure HackRF device")
                return
            
            print("DEBUG: Configuring sweep parameters...")
            if not self._configure_sweep():
                print("Failed to configure sweep parameters")
                return
            
            print("DEBUG: Starting HackRF sweep...")
            
            # Start the sweep
            print("DEBUG: Calling hackrf_sweep_start...")
            sweep_state_ptr = ctypes.pointer(self.sweep_state)
            max_sweeps = 0 if not self.config.one_shot else 1  # 0 = infinite
            result = self.sweeper_lib.hackrf_sweep_start(sweep_state_ptr, max_sweeps)
            print(f"DEBUG: hackrf_sweep_start returned: {result}")
            if result != HACKRF_SUCCESS:
                print(f"Failed to start sweep: {result}")
                return
            
            print("DEBUG: Sweep started successfully, entering main loop...")
            # Keep running until stopped
            while self.is_running:
                time.sleep(0.1)  # Main thread sleep
                
                if self.config.one_shot:
                    break
            
            print("DEBUG: Exiting sweep loop...")
            
        except Exception as e:
            print(f"Error in real sweep: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("DEBUG: Cleaning up real sweep...")
            self._cleanup_real_sweep()
    
    
    def _configure_device(self):
        """Configure HackRF device parameters."""
        try:
            print("DEBUG: Initializing HackRF...")
            # Initialize HackRF
            result = self.hackrf_lib.hackrf_init()
            print(f"DEBUG: hackrf_init returned: {result}")
            if result != HACKRF_SUCCESS:
                print(f"Failed to initialize HackRF: {result}")
                return False
            
            print("DEBUG: Opening HackRF device...")
            # Open device
            device_ptr = ctypes.c_void_p()
            result = self.hackrf_lib.hackrf_open(ctypes.byref(device_ptr))
            print(f"DEBUG: hackrf_open returned: {result}")
            if result != HACKRF_SUCCESS:
                print(f"Failed to open HackRF: {result}")
                return False
            
            self.device = device_ptr
            print(f"DEBUG: Device opened, pointer: {self.device}")
            
            print("DEBUG: Setting LNA gain...")
            # Configure gains
            result = self.hackrf_lib.hackrf_set_lna_gain(self.device, self.config.lna_gain)
            print(f"DEBUG: hackrf_set_lna_gain returned: {result}")
            if result != HACKRF_SUCCESS:
                print(f"Failed to set LNA gain: {result}")
                return False
            
            print("DEBUG: Setting VGA gain...")
            result = self.hackrf_lib.hackrf_set_vga_gain(self.device, self.config.vga_gain)
            print(f"DEBUG: hackrf_set_vga_gain returned: {result}")
            if result != HACKRF_SUCCESS:
                print(f"Failed to set VGA gain: {result}")
                return False
            
            print("DEBUG: Setting amp enable...")
            # Configure amplifiers
            result = self.hackrf_lib.hackrf_set_amp_enable(self.device, 1 if self.config.amp_enable else 0)
            print(f"DEBUG: hackrf_set_amp_enable returned: {result}")
            if result != HACKRF_SUCCESS:
                print(f"Failed to set amp enable: {result}")
                return False
            
            print("DEBUG: Setting antenna enable...")
            result = self.hackrf_lib.hackrf_set_antenna_enable(self.device, 1 if self.config.antenna_enable else 0)
            print(f"DEBUG: hackrf_set_antenna_enable returned: {result}")
            if result != HACKRF_SUCCESS:
                print(f"Failed to set antenna enable: {result}")
                return False
            
            print("DEBUG: Device configuration completed successfully")
            return True
            
        except Exception as e:
            print(f"Error configuring device: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _configure_sweep(self):
        """Configure sweep parameters."""
        try:
            print("DEBUG: Creating sweep state structure...")
            # Create sweep state structure directly
            self.sweep_state = HackRFSweepState()
            sweep_state_ptr = ctypes.pointer(self.sweep_state)
            
            print("DEBUG: Calling hackrf_sweep_init...")
            print(f"DEBUG: Device pointer: {self.device}")
            print(f"DEBUG: State pointer: {sweep_state_ptr}")
            print(f"DEBUG: Sample rate: {DEFAULT_SAMPLE_RATE_HZ}")
            print(f"DEBUG: Tune step: {TUNE_STEP}")
            
            # Initialize sweep state with device
            result = self.sweeper_lib.hackrf_sweep_init(
                self.device,                    # hackrf_device *device
                sweep_state_ptr,                # hackrf_sweep_state_t *state
                DEFAULT_SAMPLE_RATE_HZ,         # uint64_t sample_rate_hz
                TUNE_STEP                       # uint32_t tune_step
            )
            print(f"DEBUG: hackrf_sweep_init returned: {result}")
            if result != HACKRF_SUCCESS:
                print(f"Failed to initialize sweep: {result}")
                return False
            
            print("DEBUG: Setting output mode...")
            # Set output mode (required before setting range)
            result = self.sweeper_lib.hackrf_sweep_set_output(
                sweep_state_ptr,
                HACKRF_SWEEP_OUTPUT_MODE_BINARY,  # We want binary FFT data
                HACKRF_SWEEP_OUTPUT_TYPE_NOP,     # No file output, just callbacks
                None                              # No file pointer
            )
            print(f"DEBUG: hackrf_sweep_set_output returned: {result}")
            if result != HACKRF_SUCCESS:
                print(f"Failed to set output mode: {result}")
                return False
            
            print("DEBUG: Setting frequency range...")
            # Configure frequency range
            freq_min_uint16 = int(self.config.freq_min_mhz)
            freq_max_uint16 = int(self.config.freq_max_mhz)
            
            # Create frequency list: [freq_min, freq_max]
            frequency_list = (ctypes.c_uint16 * 2)(freq_min_uint16, freq_max_uint16)
            
            print(f"DEBUG: Setting range {freq_min_uint16} - {freq_max_uint16} MHz")
            result = self.sweeper_lib.hackrf_sweep_set_range(
                sweep_state_ptr,
                frequency_list,
                1  # range count (one range: min to max)
            )
            print(f"DEBUG: hackrf_sweep_set_range returned: {result}")
            if result != HACKRF_SUCCESS:
                print(f"Failed to set frequency range: {result}")
                return False
            
            print("DEBUG: Setting up FFT...")
            print(f"DEBUG: Bin width: {self.config.bin_width}")
            # Setup FFT with bin width and plan type
            result = self.sweeper_lib.hackrf_sweep_setup_fft(
                sweep_state_ptr,
                FFTW_MEASURE,                   # plan type
                self.config.bin_width           # bin width
            )
            print(f"DEBUG: hackrf_sweep_setup_fft returned: {result}")
            if result != HACKRF_SUCCESS:
                print(f"Failed to setup FFT: {result}")
                return False
            
            print("DEBUG: Setting up FFT callback...")
            # Set up callback
            self.fft_callback_ref = FFTReadyCallback(self._fft_ready_callback)
            result = self.sweeper_lib.hackrf_sweep_set_fft_rx_callback(
                sweep_state_ptr,
                ctypes.cast(self.fft_callback_ref, ctypes.c_void_p)
            )
            print(f"DEBUG: hackrf_sweep_set_fft_rx_callback returned: {result}")
            if result != HACKRF_SUCCESS:
                print(f"Failed to set FFT callback: {result}")
                return False
            
            print("DEBUG: Sweep configuration completed successfully")
            return True
            
        except Exception as e:
            print(f"Error configuring sweep: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _cleanup_real_sweep(self):
        """Clean up real sweep resources."""
        try:
            if self.sweep_state:
                sweep_state_ptr = ctypes.pointer(self.sweep_state)
                print("DEBUG: Stopping sweep...")
                self.sweeper_lib.hackrf_sweep_stop(sweep_state_ptr)
                print("DEBUG: Closing sweep...")
                self.sweeper_lib.hackrf_sweep_close(sweep_state_ptr)
                self.sweep_state = None
            
            if self.device:
                print("DEBUG: Closing HackRF device...")
                self.hackrf_lib.hackrf_close(self.device)
                self.device = None
            
            if self.hackrf_lib:
                print("DEBUG: Exiting HackRF...")
                self.hackrf_lib.hackrf_exit()
                
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    def update_config(self, config: HackRFSweepConfig):
        """Update sweep configuration."""
        self.config = config
    
    def get_sweep_stats(self) -> Tuple[int, float]:
        """Get current sweep statistics.
        
        Returns:
            Tuple of (sweep_count, sweep_rate)
        """
        return self.sweep_count, self.sweep_rate
