#!/usr/bin/env python3
"""
Sniper-IT Agent - Main Entry Point
Automated asset synchronization with Snipe-IT
"""

import sys
import argparse
import urllib3

from core.constants import APPLICATION_NAME, VERSION
from cli.formatters import console, print_header, print_error, print_info
from managers.setup_manager import run_interactive_setup


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
        '--generate-fields',
        action='store_true',
        dest='generate_fields',
        help='Validate and create missing custom fields in Snipe-IT'
    )
    
    parser.add_argument(
        '--issl',
        '--ignore-ssl',
        action='store_true',
        dest='issl',
        help='Ignore SSL certificate verification (for self-signed certificates)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'{APPLICATION_NAME} {VERSION}'
    )
    
    args = parser.parse_args()
    
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
            success = run_sync(test_mode=True, verify_ssl=not args.issl)
            return 0 if success else 1
        
        # Handle --generate-fields flag
        if args.generate_fields:
            print_info("Generate fields mode - Not yet implemented")
            print_info("This will validate and create missing custom fields")
            return 0
        
        # No arguments - run sync
        from managers.sync_manager import run_sync
        success = run_sync(test_mode=False, verify_ssl=not args.issl)
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


if __name__ == "__main__":
    sys.exit(main())
