# SniperIT Agent - Cross-Platform Asset Management Agent

SniperIT Agent is a Python-based agent that automatically syncs system information with your Snipe-IT asset management system. Features robust cross-platform support for both Windows and Linux.

## 🎯 Key Features

- **🖥️ Cross-Platform**: Native support for Windows and Linux with OS-aware data collection
- **🔍 Smart Asset Detection**: Finds assets by hostname, creates new ones if not found
- **📊 Comprehensive Data Collection**: Hardware, software, network, and optional system metrics
- **✅ Verified Sync**: Confirms data was actually saved in Snipe-IT with success metrics
- **🛡️ Robust Error Handling**: Handles conflicts, SSL issues, and edge cases gracefully
- **📦 Single-File Executables**: No external dependencies or config files needed
- **⚙️ Configurable Fields**: Enable/disable data collection via simple configuration


## 📋 Data Collected

### Core System Information
- **Hardware**: Manufacturer, Model, Serial Number, Processor/CPU
- **Memory**: Total RAM, Current Usage
- **Storage**: Total capacity, Used space, Drive details
- **Network**: IP Address, MAC Address
- **Software**: Operating System, OS Install Date, BIOS info, Current user

### Optional Fields (Configurable)
- **CPU Temperature**: Real-time thermal monitoring (Linux thermal sensors)
- **System Uptime**: Days since last boot
- **Monitor Details**: Screen size and display information (WIP)
- **Agent Version**: SniperIT Agent version tracking

## 🔧 Quick Setup

### 1. Download and Extract
Download the latest `SniperIT-Agent-Source.zip` and extract to your desired location.

### 2. Configure Connection
Edit `config/config.ini` with your Snipe-IT details:
```ini
[SERVER]
site = https://your-snipeit.com/api/v1
api_key = your_api_key_here
```

### 3. Build Executable
```bash
# Works on Windows, Linux, and macOS
python build.py
```

The build script automatically:
- ✅ Creates virtual environment if needed
- ✅ Installs all required dependencies  
- ✅ Builds single-file executable with bundled config files
- ✅ Works on all platforms with zero configuration

## 💻 Usage

### Testing (No Sync)
```bash
# Test data collection without sending to Snipe-IT
./dist/SniperIT-Agent --test-only

# Test with SSL certificate bypass
./dist/SniperIT-Agent --test-only -issl
```

### Production Sync
```bash
# Full sync to Snipe-IT
./dist/SniperIT-Agent

# With SSL bypass for self-signed certificates
./dist/SniperIT-Agent -issl

# Generate missing fieldsets and models
./dist/SniperIT-Agent --generate-fields -issl
```

### Available Commands
- `--test-only` - Test data collection without syncing
- `--generate-fields` - Create missing fieldsets and models in Snipe-IT
- `-issl` - Ignore SSL certificate verification
- `--help` - Show all available options

## 📊 Success Metrics

The application provides detailed reporting:
```
🎉 SYNC COMPLETED SUCCESSFULLY!
📊 Asset Processing: Found existing asset (ID: 124)
📊 Custom Fields Success Rate: 100.0% (13/13 fields)
📊 Verification: All data confirmed in Snipe-IT
✅ Excellent sync quality!
```

## 🏗️ Building for Different Platforms

### Simple One-Command Build
```bash
python build.py  # Works on any platform
```

### Platform-Specific Outputs
- **Windows**: `dist/SniperIT-Agent.exe` (~11 MB)
- **Linux**: `dist/SniperIT-Agent` (~11 MB)
- **macOS**: `dist/SniperIT-Agent` (~11 MB)

### Cross-Platform Building
**Important**: PyInstaller can only build for the current OS:
- Build **Windows .exe** → Run on Windows machine
- Build **Linux binary** → Run on Linux machine

**Options for multi-platform builds:**
1. **Separate Machines**: Build on each target OS
2. **Virtual Machines**: Use VMs for different OS builds
3. **WSL**: Use Windows Subsystem for Linux for Linux builds
4. **CI/CD**: GitHub Actions with multiple OS runners

### Build Process
1. **Environment Setup**: Auto-creates virtual environment
2. **Dependency Installation**: Installs requirements automatically
3. **Clean Build**: Removes previous artifacts
4. **Executable Creation**: Uses PyInstaller with optimized settings
5. **Validation**: Confirms successful build

## ⚙️ Configuration

### Field Configuration
Edit `config/custom_fields.json` to enable/disable data collection:

```json
{
  "field_configuration": {
    "basic_system_fields": {
      "operating_system": {"enabled": true, "field_name": "_snipeit_os_3"},
      "memory_ram": {"enabled": true, "field_name": "_snipeit_memory_10"}
    },
    "optional_fields": {
      "cpu_temperature": {"enabled": false, "field_name": "_snipeit_temp_20"},
      "system_uptime": {"enabled": false, "field_name": "_snipeit_uptime_21"}
    }
  }
}
```

### Advanced Configuration
- **Basic Fields**: Core system information (always recommended)
- **Optional Fields**: Additional metrics (enable as needed)
- **Monitor Fields**: Display/screen information
- **Field Names**: Match your Snipe-IT custom field database names

## 🏛️ Project Architecture

### 📁 Clean Structure (Production Ready)

```
SniperIT-Agent/
├── main.py                     # 🚀 Main entry point & CLI handling
├── build.py                    # 🏗️ Cross-platform build script  
├── requirements.txt            # 📋 Python dependencies
├── SniperIT-Agent.spec         # ⚙️ PyInstaller build configuration
├── collectors/
│   └── system_collector.py     # 🖥️ ALL OS commands & data collection
├── managers/
│   ├── asset_manager.py        # 📊 Asset processing & API handling
│   └── fieldset_manager.py     # 📝 Fieldset validation & creation
├── config/
│   ├── config.ini              # 🔧 Snipe-IT API configuration
│   ├── custom_fields.json      # 📝 Field mapping (NO PowerShell commands)
│   ├── constants.py            # 📋 Version & app constants
│   └── settings.py             # ⚙️ Configuration management
└── utils/
    ├── common.py               # 🛠️ OS utilities & command conversion
    └── exception.py            # 🚨 Error handling
```

### ✅ Key Architectural Improvements

1. **🎯 Centralized Commands**: ALL OS commands in `system_collector.py` (no scattered PowerShell)
2. **📦 Clean Configuration**: JSON files contain only mappings, no executable code
3. **🔄 Unified Build**: Single build script works on all platforms
4. **🧪 Modular Design**: Each component testable independently
5. **📖 Self-Documenting**: Clear file names and structure
6. **🗂️ Organized**: Logical grouping by functionality
7. **🚀 Production Ready**: Single-file executables with bundled configs

## 🔄 Workflow

1. **OS Detection** → Automatically detect Windows/Linux and use appropriate commands
2. **Data Collection** → Gather comprehensive system information via `system_collector.py`
3. **Manufacturer Processing** → Find existing or create new manufacturer
4. **Model Processing** → Find/create model with proper fieldset assignment
5. **Asset Detection** → Search by hostname in Snipe-IT database
6. **Asset Sync** → Create new asset or update existing with collected data
7. **Verification** → Confirm all data was saved correctly via API verification

## 🛠️ Development

### Requirements
- **Python 3.8+**
- **Virtual Environment** (auto-created by build script)
- **Dependencies**: `requests`, `urllib3`, `pyinstaller`

### Development Setup
```bash
# Clone/download the project
python build.py                 # Sets up everything automatically

# Manual setup (optional)
python -m venv .venv
source .venv/bin/activate       # Linux/Mac
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### Testing
```bash
# Test system collector directly
python -c "from collectors.system_collector import SystemDataCollector; SystemDataCollector().collect_all_data()"

# Test main application
python main.py --test-only
```

### Development Notes
- **All OS commands** are centralized in `collectors/system_collector.py`
- **Configuration-driven** field collection
- **Cross-platform** command handling with automatic OS detection
- **Error handling** for unsupported hardware/systems

## 📋 Enterprise Deployment

### Group Policy Integration (Windows)
1. Place executable in network-accessible location
2. Create GPO with scheduled task
3. Set "on idle" trigger based on your requirements
4. Run as SYSTEM user for optimal execution
5. Use `-issl` flag for internal certificate authorities

### Linux Deployment
1. Deploy via configuration management (Ansible, Puppet, etc.)
2. Create systemd service or cron job
3. Use system package managers for distribution
4. Consider running with sudo for hardware access

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Credits

This project is inspired by [https://github.com/aadrsh/snipe-it-python-agent](https://github.com/aadrsh/snipe-it-python-agent). Special thanks to the original contributors for their groundwork in Snipe-IT integration.

Enhanced with clean architecture for reliability, maintainability, and true cross-platform support.
