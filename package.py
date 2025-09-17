#!/usr/bin/env python3
"""
Package SniperIT Agent for distribution
Creates distribution packages ready for Windows building
"""

import os
import shutil
import platform
from pathlib import Path
import zipfile
import tarfile

def create_distribution_package():
    """Create a distribution package for building on other platforms"""
    print("📦 Creating SniperIT Agent Distribution Package")
    print("=" * 60)
    
    # Create dist package directory
    package_name = "SniperIT-Agent-Source"
    package_dir = Path(package_name)
    
    if package_dir.exists():
        shutil.rmtree(package_dir)
    
    package_dir.mkdir()
    print(f"📁 Created package directory: {package_name}/")
    
    # Files and directories to include
    include_items = [
        'main.py',
        'SniperIT-Agent.spec',
        'build.py',
        'requirements.txt',
        'README.md',
        '.github/',
        'config/',
        'collectors/',
        'managers/',
        'utils/'
    ]
    
    # Copy items to package
    print("📋 Copying files...")
    for item in include_items:
        src = Path(item)
        if src.exists():
            dst = package_dir / item
            if src.is_dir():
                shutil.copytree(src, dst)
                print(f"   📁 {item}/ → {package_name}/{item}/")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"   📄 {item} → {package_name}/{item}")
        else:
            print(f"   ⚠️  {item} not found, skipping")
    
    # Create README for distribution
    readme_content = """# SniperIT Agent - Distribution Package

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
"""
    
    readme_path = package_dir / "README.txt"
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    print(f"   📄 Created README.txt")
    
    # Create archives
    current_os = platform.system()
    print(f"\n📦 Creating distribution archives...")
    
    # Create ZIP (Windows-friendly)
    zip_name = f"{package_name}.zip"
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file
                arc_path = file_path.relative_to(package_dir.parent)
                zipf.write(file_path, arc_path)
    
    zip_size = Path(zip_name).stat().st_size / 1024
    print(f"   ✅ {zip_name} ({zip_size:.1f} KB)")
    
    # Create TAR.GZ (Linux-friendly)
    if current_os != 'Windows':
        tar_name = f"{package_name}.tar.gz"
        with tarfile.open(tar_name, 'w:gz') as tarf:
            tarf.add(package_dir, arcname=package_name)
        
        tar_size = Path(tar_name).stat().st_size / 1024
        print(f"   ✅ {tar_name} ({tar_size:.1f} KB)")
    
    # Cleanup temp directory
    shutil.rmtree(package_dir)
    
    print(f"\n🎉 DISTRIBUTION PACKAGE CREATED!")
    print("=" * 60)
    print("📋 Files created:")
    if Path(zip_name).exists():
        print(f"   📦 {zip_name} - Ready for Windows building")
    if current_os != 'Windows' and Path(f"{package_name}.tar.gz").exists():
        print(f"   📦 {package_name}.tar.gz - Ready for Linux building")
    
    print(f"\n🔧 Instructions:")
    print(f"1. Send package to target platform (Windows/Linux/macOS)")
    print(f"2. Extract archive")
    print(f"3. Run: python build.py")
    print(f"   (Works on all platforms - automatically handles venv and dependencies)")

if __name__ == "__main__":
    create_distribution_package()