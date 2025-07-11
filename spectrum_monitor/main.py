#!/usr/bin/env python3
"""
HackRF Spectrum Monitor
Main entry point for the spectrum monitoring tool.
"""

import argparse
import sys
import os
from pathlib import Path

# Add the spectrum monitor directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from config import Configuration
from display import CLIDisplay
from learning_mode import LearningMode
from monitoring_mode import MonitoringMode


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='HackRF Spectrum Monitor - Learn and monitor spectrum baselines',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --mode learning                    # Learn baseline spectrum
  %(prog)s --mode monitoring                  # Monitor for anomalies
  %(prog)s --config custom.yaml --mode learning  # Use custom config
        """
    )
    
    parser.add_argument(
        '--mode', '-m',
        choices=['learning', 'monitoring', 'auto'],
        default='auto',
        help='Operating mode (default: auto - monitoring if baselines exist, learning otherwise)'
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path (default: config.yaml)'
    )
    
    parser.add_argument(
        '--baseline-file', '-b',
        help='Override baseline file path from config'
    )
    
    parser.add_argument(
        '--threshold', '-t',
        type=float,
        help='Override threshold buffer from config (dB)'
    )
    
    parser.add_argument(
        '--freq-min',
        type=float,
        help='Override minimum frequency (MHz)'
    )
    
    parser.add_argument(
        '--freq-max',
        type=float,
        help='Override maximum frequency (MHz)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    
    return parser.parse_args()


def determine_mode(args, config):
    """Determine the operating mode based on arguments and baseline availability.
    
    Args:
        args: Parsed command line arguments
        config: Configuration object
        
    Returns:
        Operating mode string ('learning' or 'monitoring')
    """
    if args.mode in ['learning', 'monitoring']:
        return args.mode
    
    # Auto mode - check if baselines exist
    baseline_path = config.get_baseline_file_path()
    if args.baseline_file:
        baseline_path = args.baseline_file
    
    if os.path.exists(baseline_path):
        return 'monitoring'
    else:
        return 'learning'


def apply_command_line_overrides(config, args):
    """Apply command line argument overrides to configuration.
    
    Args:
        config: Configuration object to modify
        args: Parsed command line arguments
    """
    if args.baseline_file:
        config.storage.baseline_file = os.path.basename(args.baseline_file)
        config.storage.data_directory = os.path.dirname(args.baseline_file) or '.'
    
    if args.threshold is not None:
        config.monitoring.threshold_buffer_db = args.threshold
    
    if args.freq_min is not None:
        config.spectrum.freq_min_mhz = args.freq_min
    
    if args.freq_max is not None:
        config.spectrum.freq_max_mhz = args.freq_max


def create_display(config, args):
    """Create and configure display object.
    
    Args:
        config: Configuration object
        args: Parsed command line arguments
        
    Returns:
        CLIDisplay object
    """
    display = CLIDisplay(
        show_frequency_mhz=config.display.show_frequency_mhz,
        precision_digits=config.display.precision_digits,
        power_precision=config.display.power_precision,
        alert_beep=config.display.alert_beep
    )
    
    # Apply command line overrides
    if args.no_color:
        display.use_colors = False
    
    return display


def run_learning_mode(config, display, args):
    """Run learning mode.
    
    Args:
        config: Configuration object
        display: Display object
        args: Command line arguments
        
    Returns:
        True if successful, False otherwise
    """
    try:
        learning = LearningMode(config, display)
        success = learning.run()
        
        if success:
            display.print_info("Learning mode completed successfully.")
            display.print_info(f"Baselines saved to: {config.get_baseline_file_path()}")
            display.print_info("You can now run monitoring mode to detect anomalies.")
        else:
            display.print_error("Learning mode failed.")
        
        return success
        
    except Exception as e:
        display.print_error(f"Learning mode error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return False


def run_monitoring_mode(config, display, args):
    """Run monitoring mode.
    
    Args:
        config: Configuration object
        display: Display object
        args: Command line arguments
        
    Returns:
        True if successful, False otherwise
    """
    try:
        monitoring = MonitoringMode(config, display)
        success = monitoring.run()
        
        if success:
            display.print_info("Monitoring mode completed.")
        else:
            display.print_error("Monitoring mode failed.")
        
        return success
        
    except Exception as e:
        display.print_error(f"Monitoring mode error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return False


def main():
    """Main function."""
    args = parse_arguments()
    
    try:
        # Load configuration
        try:
            config = Configuration(args.config)
        except FileNotFoundError:
            print(f"Error: Configuration file not found: {args.config}")
            print("Create a config.yaml file or specify a different config with --config")
            return 1
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return 1
        
        # Apply command line overrides
        apply_command_line_overrides(config, args)
        
        # Create display
        display = create_display(config, args)
        
        # Determine operating mode
        mode = determine_mode(args, config)
        
        if args.verbose:
            display.print_info(f"Operating mode: {mode}")
            display.print_info(f"Configuration: {args.config}")
            display.print_info(f"Baseline file: {config.get_baseline_file_path()}")
        
        # Run the appropriate mode
        if mode == 'learning':
            success = run_learning_mode(config, display, args)
        elif mode == 'monitoring':
            success = run_monitoring_mode(config, display, args)
        else:
            display.print_error(f"Unknown mode: {mode}")
            return 1
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 