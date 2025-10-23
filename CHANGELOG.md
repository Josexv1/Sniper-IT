# Changelog

## Version 2.2.8
- **Monitor name change detection**: Monitor names now properly update when they contain old "Connected to" text
- **Monitor asset tag auto-increment**: Monitors now support custom naming conventions (e.g., 'MIS-MON-N')
- **Separate naming conventions**: Computer and monitor assets can have different naming patterns
- **Enhanced setup wizard**: New step for configuring monitor asset tag pattern
- **Config template update**: Added `monitor_naming_convention` field to defaults
- **Clean monitor names**: Monitor names are now just the model (e.g., "HP M24fe FHD" not "PHL PHL 275V8 - Connected to...")
- **Consistent asset tags**: Monitors now use proper naming convention instead of serial numbers (unless configured otherwise)

## Version 2.2.7
- **Smart change detection**: Assets only updated when meaningful changes are detected
- **Ignore volatile data**: Disk space and RAM usage changes no longer trigger unnecessary updates
- **Clean status display**: Shows "NO CHANGES (already up to date)" when asset is current
- **Reduced API calls**: Skips update requests when no changes detected
- **Monitor change detection**: Monitors also skip updates when already up to date
- **Better efficiency**: Minimizes unnecessary writes to Snipe-IT database

## Version 2.2.6
- **Smart log file location**: Auto-log now falls back to temp directory if current directory is not writable
- **Improved model detection**: Better handling of duplicate model errors - searches more thoroughly before failing
- **Permission handling**: Graceful degradation when running from shared folders without write access
- **Error recovery**: When model creation fails due to duplicates, searches all models ignoring manufacturer mismatch
- **Better UX**: Clear messaging about log file location changes

## Version 2.2.5
- **Monitor checkout optimization**: Fixed unnecessary checkin/checkout cycles in activity log
- **Smart assignment check**: Monitor only checked in/out if assignment needs to change
- **Reduced API calls**: Skips checkout when monitor already assigned to correct user
- **Cleaner audit trail**: Eliminates repeated "Auto-checkin before reassignment" entries
- **Performance improvement**: Faster sync with fewer redundant operations

## Version 2.2.4
- **Build-time auto-logging**: New `--auto-log` flag for build.py enables automatic log generation
- **Smart setup wizard**: Detects hardcoded credentials and skips server configuration prompts
- **SSL warning suppression**: Automatically suppresses urllib3 SSL warnings when built with `--ignore-ssl`
- **Enhanced deployment**: Users run EXE with zero arguments - no need for `--issl` or `--log` flags
- **Improved UX**: Clean console output without SSL certificate warnings when using self-signed certs

## Version 2.2.0
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

## Version 2.1.0
- **Build-time credential injection**: Hardcode URL and API key into executable
- **Optional SSL ignore flag**: `--ignore-ssl` flag for build.py (not hardcoded)
- **Smart setup wizard**: Detects hardcoded credentials and skips server config
- **Simplified deployment**: Copy EXE + config.yaml to shared folder, users just run it
- **Bug fix**: Removed incorrect import check in build.py
- Updated README with new deployment patterns

## Version 2.0.0
- Complete rewrite with modular architecture
- Added monitor detection and tracking
- Automatic monitor checkout to parent laptop
- Interactive setup wizard
- Field-to-fieldset association
- Improved error handling
- Test mode for safe validation
- Custom field mapping system
- Auto-incrementing asset tag system
