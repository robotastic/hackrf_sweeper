"""
Storage Module
Handles persistence of baseline spectrum data and metadata.
"""

import numpy as np
import os
import time
from typing import Optional, Dict, Any, Tuple
import json


class BaselineStorage:
    """Manages storage and retrieval of spectrum baseline data."""
    
    def __init__(self, file_path: str):
        """Initialize baseline storage.
        
        Args:
            file_path: Path to baseline data file
        """
        self.file_path = file_path
        self.baselines_loaded = False
        
        # Baseline data
        self.frequencies = None
        self.max_power_levels = None
        self.metadata = {}
    
    def save_baselines(self, frequencies: np.ndarray, power_history: np.ndarray, 
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Save learned baseline data to file.
        
        Args:
            frequencies: Frequency array in MHz
            power_history: 2D array of power history (sweeps x frequency_bins)
            metadata: Optional metadata dictionary
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Calculate maximum power levels across all sweeps
            max_power_levels = np.max(power_history, axis=0)
            
            # Prepare metadata
            save_metadata = {
                'timestamp': time.time(),
                'creation_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'frequency_range_mhz': [float(frequencies.min()), float(frequencies.max())],
                'num_frequency_bins': len(frequencies),
                'num_sweeps_learned': power_history.shape[0],
                'baseline_stats': {
                    'min_power_db': float(max_power_levels.min()),
                    'max_power_db': float(max_power_levels.max()),
                    'mean_power_db': float(max_power_levels.mean()),
                    'std_power_db': float(max_power_levels.std())
                }
            }
            
            # Add user metadata
            if metadata:
                save_metadata.update(metadata)
            
            # Save data using numpy compressed format
            np.savez_compressed(
                self.file_path,
                frequencies=frequencies,
                max_power_levels=max_power_levels,
                power_history=power_history,
                metadata=np.array([save_metadata], dtype=object)
            )
            
            # Update internal state
            self.frequencies = frequencies
            self.max_power_levels = max_power_levels
            self.metadata = save_metadata
            self.baselines_loaded = True
            
            return True
            
        except Exception as e:
            print(f"Error saving baselines: {e}")
            return False
    
    def load_baselines(self) -> bool:
        """Load baseline data from file.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            if not os.path.exists(self.file_path):
                print(f"Baseline file not found: {self.file_path}")
                return False
            
            # Load data
            data = np.load(self.file_path, allow_pickle=True)
            
            # Extract baseline data
            self.frequencies = data['frequencies']
            self.max_power_levels = data['max_power_levels']
            
            # Extract metadata
            if 'metadata' in data:
                self.metadata = data['metadata'].item()
            else:
                self.metadata = {}
            
            self.baselines_loaded = True
            return True
            
        except Exception as e:
            print(f"Error loading baselines: {e}")
            return False
    
    def is_loaded(self) -> bool:
        """Check if baseline data is loaded."""
        return self.baselines_loaded
    
    def get_baselines(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Get loaded baseline data.
        
        Returns:
            Tuple of (frequencies, max_power_levels) or (None, None) if not loaded
        """
        if self.baselines_loaded:
            return self.frequencies, self.max_power_levels
        return None, None
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get baseline metadata."""
        return self.metadata.copy() if self.metadata else {}
    
    def get_baseline_at_frequency(self, target_freq: float) -> Optional[float]:
        """Get baseline power level at specific frequency.
        
        Args:
            target_freq: Target frequency in MHz
            
        Returns:
            Baseline power level in dB, or None if not available
        """
        if not self.baselines_loaded:
            return None
        
        # Find closest frequency bin
        freq_idx = np.argmin(np.abs(self.frequencies - target_freq))
        
        # Check if we're reasonably close
        freq_diff = abs(self.frequencies[freq_idx] - target_freq)
        max_allowed_diff = (self.frequencies[1] - self.frequencies[0]) * 2  # Allow 2x bin width
        
        if freq_diff <= max_allowed_diff:
            return float(self.max_power_levels[freq_idx])
        
        return None
    
    def interpolate_baselines(self, target_frequencies: np.ndarray) -> Optional[np.ndarray]:
        """Interpolate baselines to match target frequency grid.
        
        Args:
            target_frequencies: Target frequency array in MHz
            
        Returns:
            Interpolated baseline power levels, or None if not loaded
        """
        if not self.baselines_loaded:
            return None
        
        try:
            # Use linear interpolation
            interpolated = np.interp(target_frequencies, self.frequencies, self.max_power_levels)
            return interpolated
            
        except Exception as e:
            print(f"Error interpolating baselines: {e}")
            return None
    
    def check_frequency_coverage(self, freq_min: float, freq_max: float) -> Tuple[bool, str]:
        """Check if baselines cover the requested frequency range.
        
        Args:
            freq_min: Minimum frequency in MHz
            freq_max: Maximum frequency in MHz
            
        Returns:
            Tuple of (is_covered, message)
        """
        if not self.baselines_loaded:
            return False, "No baselines loaded"
        
        baseline_min = self.frequencies.min()
        baseline_max = self.frequencies.max()
        
        # Calculate frequency bin width for tolerance
        if len(self.frequencies) > 1:
            freq_bin_width = (baseline_max - baseline_min) / (len(self.frequencies) - 1)
            # Allow tolerance of 1 frequency bin width
            tolerance = freq_bin_width
        else:
            tolerance = 0.1  # Default 0.1 MHz tolerance
        
        # Check if requested range is within baseline coverage (with tolerance)
        min_deficit = baseline_min - freq_min
        max_deficit = freq_max - baseline_max
        
        if min_deficit > tolerance or max_deficit > tolerance:
            return False, (
                f"Requested range {freq_min:.1f}-{freq_max:.1f} MHz "
                f"exceeds baseline coverage {baseline_min:.3f}-{baseline_max:.3f} MHz "
                f"(tolerance: {tolerance:.3f} MHz)"
            )
        
        return True, "Frequency range fully covered by baselines"
    
    def get_file_info(self) -> Dict[str, Any]:
        """Get information about the baseline file.
        
        Returns:
            Dictionary with file information
        """
        info = {
            'file_path': self.file_path,
            'exists': os.path.exists(self.file_path),
            'loaded': self.baselines_loaded
        }
        
        if os.path.exists(self.file_path):
            stat = os.stat(self.file_path)
            info.update({
                'size_bytes': stat.st_size,
                'modified_time': time.ctime(stat.st_mtime),
                'created_time': time.ctime(stat.st_ctime)
            })
        
        if self.baselines_loaded and self.metadata:
            info.update({
                'frequency_range_mhz': self.metadata.get('frequency_range_mhz', []),
                'num_frequency_bins': self.metadata.get('num_frequency_bins', 0),
                'num_sweeps_learned': self.metadata.get('num_sweeps_learned', 0),
                'creation_date': self.metadata.get('creation_date', 'Unknown'),
                'baseline_stats': self.metadata.get('baseline_stats', {})
            })
        
        return info
    
    def export_json(self, json_path: str) -> bool:
        """Export baseline data to JSON format.
        
        Args:
            json_path: Path for JSON export
            
        Returns:
            True if exported successfully, False otherwise
        """
        if not self.baselines_loaded:
            print("No baselines loaded to export")
            return False
        
        try:
            export_data = {
                'metadata': self.metadata,
                'frequency_mhz': self.frequencies.tolist(),
                'max_power_db': self.max_power_levels.tolist()
            }
            
            with open(json_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error exporting to JSON: {e}")
            return False
    
    def create_backup(self, backup_suffix: str = None) -> Optional[str]:
        """Create a backup copy of the baseline file.
        
        Args:
            backup_suffix: Optional suffix for backup filename
            
        Returns:
            Path to backup file if successful, None otherwise
        """
        if not os.path.exists(self.file_path):
            return None
        
        try:
            if backup_suffix is None:
                timestamp = time.strftime('%Y%m%d_%H%M%S')
                backup_suffix = f"backup_{timestamp}"
            
            # Create backup filename
            base, ext = os.path.splitext(self.file_path)
            backup_path = f"{base}_{backup_suffix}{ext}"
            
            # Copy file
            import shutil
            shutil.copy2(self.file_path, backup_path)
            
            return backup_path
            
        except Exception as e:
            print(f"Error creating backup: {e}")
            return None
    
    def __str__(self) -> str:
        """String representation of baseline storage."""
        if not self.baselines_loaded:
            return f"BaselineStorage(file={self.file_path}, loaded=False)"
        
        stats = self.metadata.get('baseline_stats', {})
        return (
            f"BaselineStorage(\n"
            f"  file={self.file_path}\n"
            f"  frequency_range={self.metadata.get('frequency_range_mhz', [])}\n"
            f"  bins={self.metadata.get('num_frequency_bins', 0)}\n"
            f"  sweeps={self.metadata.get('num_sweeps_learned', 0)}\n"
            f"  power_range=[{stats.get('min_power_db', 0):.1f}, {stats.get('max_power_db', 0):.1f}] dB\n"
            f")"
        ) 