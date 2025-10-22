#!/usr/bin/env python3
"""
Sniper-IT Agent - Main Entry Point
Automated asset synchronization with Snipe-IT
"""

import sys
import argparse
import urllib3
import socket
from datetime import datetime
from pathlib import Path

from core.constants import APPLICATION_NAME, VERSION
from cli.formatters import console, print_header, print_error, print_info
from managers.setup_manager import run_interactive_setup
from utils.logger import init_logger, close_logger


def main():
    """Main entry point"""
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description=f"{APPLICATION_NAME} - Automated Asset Sync Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--setup',
        action='store_true',
        help='Run interactive setup wizard to generate config.yaml'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test API connection and data collection without syncing'
    )
    
    parser.add_argument(
        '--issl',
        '--ignore-ssl',
        action='store_true',
        dest='issl',
        help='Ignore SSL certificate verification (for self-signed certificates)'
    )
    
    parser.add_argument(
        '-v',
        action='store_true',
        dest='verbose',
        help='Verbose mode - show all output text'
    )
    
    parser.add_argument(
        '-vv',
        action='store_true',
        dest='very_verbose',
        help='Very verbose mode - show debug information'
    )
    
    parser.add_argument(
        '--log',
        action='store_true',
        dest='log_to_file',
        help='Save all output to a log file (hostname_date.txt)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'{APPLICATION_NAME} {VERSION}'
    )
    
    args = parser.parse_args()
    
    # Determine verbosity level
    verbosity = 0
    if args.very_verbose:
        verbosity = 2  # Debug level
    elif args.verbose:
        verbosity = 1  # Verbose level
    
    # Setup log file if requested
    log_file = None
    if args.log_to_file:
        hostname = socket.gethostname()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = f"{hostname}_{timestamp}.txt"
        print_info(f"Logging to file: {log_file}")
    
    # Initialize logger
    init_logger(verbosity=verbosity, log_file=log_file)
    
    # Handle SSL warnings
    if args.issl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        # Handle --setup flag
        if args.setup:
            success = run_interactive_setup(verify_ssl=not args.issl)
            return 0 if success else 1
        
        # Handle --test flag
        if args.test:
            from managers.sync_manager import run_sync
            success = run_sync(test_mode=True, verify_ssl=not args.issl, verbosity=verbosity)
            return 0 if success else 1
        
        # No arguments - run sync
        from managers.sync_manager import run_sync
        success = run_sync(test_mode=False, verify_ssl=not args.issl, verbosity=verbosity)
        return 0 if success else 1
        
    except KeyboardInterrupt:
        console.print("\n")
        print_error("Cancelled by user")
        return 1
    except Exception as e:
        console.print("\n")
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Close logger
        close_logger()


if __name__ == "__main__":
    sys.exit(main())
