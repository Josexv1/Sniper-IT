"""
Sniper-IT Agent - Application Constants
Version, application name, and other constants
"""

APPLICATION_NAME = "Sniper-IT Agent"
VERSION = "2.3.4"
CONFIG_FILENAME = "config.yaml"

# Status indicators (no emojis - text-based only)
STATUS_OK = "[OK]"
STATUS_ERROR = "[ERROR]"
STATUS_WARNING = "[!]"
STATUS_INFO = "[*]"
STATUS_QUESTION = "[?]"

# Monitor custom field definitions
# Used for validation and field creation during setup
# Note: Manufacturer, Model, Serial Number are standard Snipe-IT asset fields
MONITOR_FIELD_DEFINITIONS = {
    'resolution': {
        'display_name': 'Resolution',
        'format': 'text',
        'description': 'Current display resolution (e.g., 1920x1080)'
    },
    'native_resolution': {
        'display_name': 'Native Resolution',
        'format': 'text',
        'description': 'Native/maximum resolution supported'
    },
    'refresh_rate': {
        'display_name': 'Refresh Rate',
        'format': 'text',
        'description': 'Display refresh rate (e.g., 60 Hz, 144 Hz)'
    },
    'connection_interface': {
        'display_name': 'Connection Interface',
        'format': 'text',
        'description': 'Connection type (HDMI, DisplayPort, DVI, etc.)'
    },
    'bit_depth': {
        'display_name': 'Bit Depth',
        'format': 'text',
        'description': 'Color bit depth (e.g., 8-bit, 10-bit)'
    },
    'monitor_screen_size': {
        'display_name': 'Monitor Screen Size',
        'format': 'text',
        'description': 'Physical monitor screen size (e.g., 27", 24")'
    }
}

# Expected db_column prefixes for monitor fields (for validation)
MONITOR_FIELD_PREFIXES = {
    'resolution': '_snipeit_resolution',
    'native_resolution': '_snipeit_native_resolution',
    'refresh_rate': '_snipeit_refresh_rate',
    'connection_interface': '_snipeit_connection_interface',
    'bit_depth': '_snipeit_bit_depth',
    'monitor_screen_size': '_snipeit_monitor_screen_size'
}
