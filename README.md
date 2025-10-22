# Sniper-IT Agent

**Version 2.2.4**

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
  - Automatically checks out monitors to the assigned user

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
6. Check out monitors to the assigned user (with device connection tracking)
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

### Standard Build (requires config.yaml)

```bash
python build.py
```

This creates:
- `dist/Sniper-IT-Agent.exe` - Standalone executable
- Requires `config.yaml` next to the EXE at runtime
- No Python installation required on target machines

### Build with Hardcoded Credentials (for shared folder deployment)

For simplified deployment where users just run the EXE:

```bash
# Basic build with credentials
python build.py --url https://your-snipeit-server.com --api-key YOUR_API_KEY_HERE

# Build with SSL ignore (for self-signed certificates)
python build.py --url https://your-snipeit-server.com --api-key YOUR_API_KEY_HERE --ignore-ssl

# Build with automatic logging enabled
python build.py --url https://your-snipeit-server.com --api-key YOUR_API_KEY_HERE --ignore-ssl --auto-log
```

**Benefits:**
- ✅ Credentials are baked into the EXE at build time
- ✅ Optional SSL ignore flag (use `--ignore-ssl` for self-signed certificates)
- ✅ Optional automatic logging (use `--auto-log` to generate logs on every run)
- ✅ Users don't need to pass `--issl` or `--log` flags when running
- ✅ Simplified config.yaml (only needs defaults and custom fields, no server section)
- ⚠️ **Security Note**: Distribute the EXE only through secure channels as it contains credentials

**Important:** You still need a `config.yaml` file with:
- `defaults` section (company_id, status_id, category_ids, fieldset_ids, naming_convention)
- `custom_fields` section (field mappings for laptop data)
- `monitor_custom_fields` section (field mappings for monitors)

**Example deployment:**
1. Build with credentials: `python build.py --url https://snipeit.company.com --api-key eyJ0eXAiOiJKV1... --ignore-ssl --auto-log`
2. Run setup to generate `config.yaml`: `Sniper-IT-Agent.exe --setup`
   - Setup will detect hardcoded credentials and skip server config
   - Will only create defaults and custom_fields sections
3. Copy both files to shared folder: `R:\public\Inventory\`
   - `Sniper-IT-Agent.exe` (with hardcoded credentials and auto-logging)
   - `config.yaml` (with defaults and field mappings)
4. Users run the EXE - no arguments needed! Logs will be generated automatically.

## Command-Line Options

| Flag | Description |
|------|-------------|
| `--setup` | Run interactive setup wizard |
| `--test` | Test mode - collect data but don't push to Snipe-IT |
| `--issl` / `--ignore-ssl` | Ignore SSL certificate verification |
| `--log` | Save all output to a log file (hostname_timestamp.txt) |
| `-v` | Verbose mode - show all output text |
| `-vv` | Very verbose mode - show debug information |
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
   - Automatically checks out to the same user as the parent laptop/desktop
   - Adds note tracking which device it's connected to
   - Ensures monitors appear in user asset queries
   - Follows Snipe-IT best practices for accountability

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

### Option 1: Shared Folder (Recommended for Windows)

**Simplified deployment** - users just run the EXE:

1. Build with hardcoded credentials:
   ```bash
   python build.py --url https://snipeit.company.com --api-key YOUR_API_KEY --ignore-ssl --auto-log
   ```
   - Use `--ignore-ssl` for self-signed certificates
   - Use `--auto-log` to enable automatic log file generation

2. Generate config.yaml using the built executable:
   ```bash
   cd dist
   Sniper-IT-Agent.exe --setup
   ```
   - Setup will detect hardcoded credentials and skip server section
   - Will only configure defaults and custom field mappings

3. Copy both files to shared folder:
   ```
   R:\public\Inventory\
   ├── Sniper-IT-Agent.exe  (with hardcoded credentials and auto-logging)
   └── config.yaml          (with defaults and field mappings)
   ```

4. Tell users to run from the shared location:
   ```
   R:\public\Inventory\Sniper-IT-Agent.exe
   ```
   - No arguments needed
   - No user-specific configuration
   - Credentials are baked in
   - SSL settings are baked in
   - Logs automatically generated in current directory

5. Optional: Add to startup or scheduled task for automatic runs:
   ```powershell
   schtasks /create /tn "Sniper-IT Sync" /tr "R:\public\Inventory\Sniper-IT-Agent.exe" /sc daily /st 09:00
   ```

### Option 2: Local Installation with Config File

**Traditional deployment** - requires config.yaml on each machine:

#### As Scheduled Task (Windows)

1. Build the executable: `python build.py`
2. Copy `Sniper-IT-Agent.exe` and `config.yaml` to target machines
3. Create a scheduled task:
   ```powershell
   schtasks /create /tn "Sniper-IT Sync" /tr "C:\Path\To\Sniper-IT-Agent.exe --issl" /sc daily /st 09:00
   ```

#### As Cron Job (Linux)

1. Install on target machine with `config.yaml`
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

## Version History

### 2.2.4 (2025-10-22)
- **Build-time auto-logging**: New `--auto-log` flag for build.py enables automatic log generation
- **Smart setup wizard**: Detects hardcoded credentials and skips server configuration prompts
- **SSL warning suppression**: Automatically suppresses urllib3 SSL warnings when built with `--ignore-ssl`
- **Enhanced deployment**: Users run EXE with zero arguments - no need for `--issl` or `--log` flags
- **Improved UX**: Clean console output without SSL certificate warnings when using self-signed certs

### 2.2.0 (2025-10-22)
- **Multi-category support**: Automatic detection for Laptop, Desktop, and Server categories
- **Smart category detection**: Auto-detects category IDs by name matching with visual recommendations
- **Smart fieldset detection**: Keyword-based fieldset matching for computer and monitor types
- **Chassis-type detection**: Automatic laptop/desktop/server classification using Win32_SystemEnclosure
- **Invalid serial handling**: Desktops/servers with placeholder serials use hostname instead
- **Enhanced monitor collector**: Hybrid manufacturer detection with ~15 common brands via EDID codes
- **Auto-incrementing asset tags**: Configurable naming patterns (e.g., 'MIS-2026-N')
- **Improved setup wizard UX**: 
  - Renamed 'Laptop Fieldset' to 'Computer Fieldset' (shared across laptop/desktop/server)
  - Better naming convention explanations with pattern examples
  - Field association only prompts when warnings/missing fields detected
  - Simplified config generation (removed hardcoded metadata)
- **Monitor name simplification**: No #2 suffix or 'Connected to' text (tracked via serial)

### 2.1.0 (2025-10-22)
- **Build-time credential injection**: Hardcode URL and API key into executable
- **Optional SSL ignore flag**: `--ignore-ssl` flag for build.py (not hardcoded)
- **Smart setup wizard**: Detects hardcoded credentials and skips server config
- **Simplified deployment**: Copy EXE + config.yaml to shared folder, users just run it
- **Bug fix**: Removed incorrect import check in build.py
- Updated README with new deployment patterns

### 2.0.0 (2025-10-21)
- Complete rewrite with modular architecture
- Added monitor detection and tracking
- Automatic monitor checkout to parent laptop
- Interactive setup wizard
- Field-to-fieldset association
- Improved error handling
- Test mode for safe validation
- Custom field mapping system
- Auto-incrementing asset tag system
