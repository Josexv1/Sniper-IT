# Sniper-IT Agent

**Version 2.0.0**

Automated asset management agent for Snipe-IT. Automatically collects laptop/desktop and monitor information, then synchronizes it to your Snipe-IT server.

## Features

- **Automatic System Data Collection**
  - Hardware info (manufacturer, model, serial number)
  - OS details and installation date
  - CPU, RAM, storage information
  - Network details (IP, MAC address)
  - BIOS information
  - Agent version tracking

- **Monitor Detection**
  - Automatically detects external monitors
  - Filters out internal laptop displays
  - Captures resolution, refresh rate, connection type
  - Automatically checks out monitors to parent laptop

- **Smart Synchronization**
  - Finds or creates manufacturers and models
  - Updates existing assets or creates new ones
  - Preserves asset tags
  - Maps custom fields to Snipe-IT
  - Validates data before pushing

- **Easy Setup**
  - Interactive setup wizard
  - Validates API connection
  - Creates missing custom fields
  - Generates configuration file

## Requirements

- Python 3.11+
- Windows or Linux
- Snipe-IT server with API access
- Network access to Snipe-IT server

## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start

### 1. Run Setup Wizard

Configure the agent and validate your Snipe-IT connection:

```bash
python main.py --setup
```

The wizard will guide you through:
- Testing API connection
- Selecting company, categories, and fieldsets
- Validating custom fields
- Creating missing fields
- Generating `config.yaml`

**For self-signed SSL certificates:**
```bash
python main.py --setup --issl
```

### 2. Test Data Collection

Test the agent without pushing data to Snipe-IT:

```bash
python main.py --test --issl
```

This will:
- Collect system data
- Detect monitors
- Display all collected information
- **NOT** push to Snipe-IT

### 3. Run Sync

Synchronize your assets to Snipe-IT:

```bash
python main.py --issl
```

The agent will:
1. Collect system information
2. Detect external monitors
3. Find or create manufacturers/models
4. Update or create laptop asset
5. Update or create monitor assets
6. Check out monitors to laptop
7. Display summary

## Configuration

After running setup, edit `config.yaml` if needed:

```yaml
server:
  url: https://your-snipeit-server.com
  api_key: your_api_key_here
  verify_ssl: false

defaults:
  status_id: 2
  company_id: 1
  laptop_category_id: 2
  laptop_fieldset_id: 1
  monitor_category_id: 38
  monitor_fieldset_id: 3

custom_fields:
  # Field mappings...
```

## Building Executable

Build a standalone executable for distribution:

```bash
python build.py
```

This creates:
- `dist/Sniper-IT-Agent.exe` - Standalone executable
- No Python installation required on target machines

## Command-Line Options

| Flag | Description |
|------|-------------|
| `--setup` | Run interactive setup wizard |
| `--test` | Test mode - collect data but don't push to Snipe-IT |
| `--issl` | Ignore SSL certificate verification |
| `--version` | Display version information |

## How It Works

### Data Collection

1. **System Information**
   - Uses PowerShell (Windows) or bash commands (Linux)
   - Non-admin privileges required
   - Collects hardware, OS, network details

2. **Monitor Detection**
   - Windows: Uses WMI and D3DKMDT APIs
   - Linux: Uses xrandr
   - Filters out internal laptop displays
   - Captures manufacturer, model, serial, resolution

### Synchronization Process

1. **Manufacturer Management**
   - Searches for existing manufacturer
   - Creates if not found

2. **Model Management**
   - Searches for existing model
   - Creates with correct category and fieldset
   - Links to manufacturer

3. **Asset Management**
   - Searches by hostname
   - Updates existing asset or creates new
   - Preserves asset tags
   - Maps custom fields

4. **Monitor Checkout**
   - After creating/updating monitor
   - Automatically checks out to parent laptop
   - Creates asset hierarchy

## Project Structure

```
Sniper-IT/
├── main.py                 # Entry point
├── build.py                # Build script for executable
├── config.yaml            # Configuration file
├── config.example.yaml    # Example configuration
│
├── cli/                   # CLI formatting and prompts
│   ├── formatters.py
│   └── __init__.py
│
├── collectors/            # Data collection modules
│   ├── system_collector.py    # System data
│   ├── monitor_collector.py   # Monitor data
│   └── __init__.py
│
├── core/                  # Core functionality
│   ├── api_client.py          # Snipe-IT API wrapper
│   ├── config_manager.py      # Configuration handling
│   ├── constants.py           # Application constants
│   └── __init__.py
│
├── managers/              # Business logic
│   ├── setup_manager.py       # Setup wizard
│   ├── asset_manager.py       # Laptop/desktop assets
│   ├── monitor_manager.py     # Monitor assets
│   ├── sync_manager.py        # Synchronization orchestration
│   └── __init__.py
│
└── utils/                 # Utilities
    ├── exceptions.py          # Custom exceptions
    └── __init__.py
```

## Deployment

### As Scheduled Task (Windows)

1. Build the executable: `python build.py`
2. Copy `Sniper-IT-Agent.exe` and `config.yaml` to target machines
3. Create a scheduled task:
   ```powershell
   schtasks /create /tn "Sniper-IT Sync" /tr "C:\Path\To\Sniper-IT-Agent.exe --issl" /sc daily /st 09:00
   ```

### As Cron Job (Linux)

1. Install on target machine
2. Add to crontab:
   ```bash
   crontab -e
   # Run daily at 9 AM
   0 9 * * * /path/to/main.py --issl
   ```

## Troubleshooting

### "Authentication failed - check your API key"
- Verify API key is valid in Snipe-IT
- Check key has not expired
- Ensure proper permissions

### "This field seems to exist, but is not available on this Asset Model's fieldset"
- Run setup again: `python main.py --setup --issl`
- The wizard will associate fields with fieldsets

### "No external monitors detected"
- Expected if only using laptop screen
- Internal displays are automatically filtered
- Check monitor is connected and powered on

### SSL Certificate Errors
- Use `--issl` flag to ignore SSL verification
- Or add valid SSL certificate to Snipe-IT server

## License

This project is internal software for Feilo Sylvania Europe Ltd.

## Version History

### 2.0.0 (2025-10-21)
- Complete rewrite with modular architecture
- Added monitor detection and tracking
- Automatic monitor checkout to parent laptop
- Interactive setup wizard
- Field-to-fieldset association
- Improved error handling
- Test mode for safe validation
- Custom field mapping system
