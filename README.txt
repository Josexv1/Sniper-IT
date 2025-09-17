# SniperIT Agent - Distribution Package

This package contains the complete SniperIT Agent source code and cross-platform build script.

## 🏗️ Building Executables (Any Platform)

### Simple One-Command Build:
1. Open terminal/command prompt in this folder
2. Run: `python build.py`
3. Find executable in `dist/` folder:
   - Windows: `dist/SniperIT-Agent.exe`
   - Linux: `dist/SniperIT-Agent`

The build script automatically:
- ✅ Creates virtual environment if needed
- ✅ Installs all required dependencies
- ✅ Builds single-file executable with bundled config files
- ✅ Works on Windows, Linux, and macOS

## ✅ What's Included

- Complete source code (main.py + modules)
- Cross-platform build script (build.py)
- PyInstaller spec file (SniperIT-Agent.spec)
- Requirements file (requirements.txt)
- Configuration files and documentation
- Zero-configuration automated building

## 🎯 Features

- Comprehensive fieldset validation and creation
- Bulk model updates (--generate-fields)
- SSL certificate handling (-issl flag)
- Test-only mode (--test-only)
- True single-file executables (no external config files needed)
- Cross-platform Windows/Linux/macOS support

## 📋 Requirements
- Python 3.8+ (that's it! Everything else is installed automatically)

For detailed information, see README.md
