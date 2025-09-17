#!/usr/bin/env python3
"""
Automated build script for SniperIT Agent
Creates single-file executables for Windows and Linux without prompts
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

def run_command(cmd, description, timeout=300):
    """Run a command and handle output with timeout"""
    print(f"[*] {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True, timeout=timeout)
        print(f"[+] {description} completed successfully")
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        return True
    except subprocess.TimeoutExpired:
        print(f"[-] {description} timed out after {timeout} seconds")
        return False
    except subprocess.CalledProcessError as e:
        print(f"[-] {description} failed")
        print(f"   Error: {e.stderr.strip()}")
        return False

def clean_build_directories():
    """Clean up previous build artifacts"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['*.pyc']
    
    print("[*] Cleaning previous build artifacts...")
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"   Removed: {dir_name}/")
    
    # Clean Python cache files
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.pyc'):
                os.remove(os.path.join(root, file))
        if '__pycache__' in dirs:
            shutil.rmtree(os.path.join(root, '__pycache__'))
    
    print("[+] Build directories cleaned")

def setup_environment():
    """Setup virtual environment and install dependencies"""
    print("[*] Setting up build environment...")
    
    # Check if we're in a virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    current_os = platform.system()
    
    if not in_venv:
        print("[!] Not in a virtual environment!")
        print("   Creating virtual environment automatically...")
        
        # Create venv
        venv_name = ".venv"
        if not run_command(f"{sys.executable} -m venv {venv_name}", "Creating virtual environment"):
            print("[-] Failed to create virtual environment")
            return False
        
        # Get activation script path
        if current_os == 'Windows':
            activate_script = f"{venv_name}\\Scripts\\activate.bat"
            pip_path = f"{venv_name}\\Scripts\\pip.exe"
            python_path = f"{venv_name}\\Scripts\\python.exe"
        else:
            activate_script = f"{venv_name}/bin/activate"
            pip_path = f"{venv_name}/bin/pip"
            python_path = f"{venv_name}/bin/python"
        
        print(f"[+] Virtual environment created at {venv_name}/")
        print("[*] Installing requirements in virtual environment...")
        
        # Install requirements using the venv pip
        if os.path.exists('requirements.txt'):
            if not run_command(f"{pip_path} install -r requirements.txt", "Installing requirements"):
                return False
        else:
            # Install essential packages
            if not run_command(f"{pip_path} install requests urllib3 pyinstaller", "Installing essential packages"):
                return False
                
        print("[+] Dependencies installed in virtual environment")
        
    else:
        print("[+] Virtual environment detected")
        
        # Install requirements if present
        if os.path.exists('requirements.txt'):
            print("[*] Installing/updating requirements...")
            if not run_command("pip install -r requirements.txt", "Installing requirements"):
                return False
        
        # Check PyInstaller
        try:
            import PyInstaller
            print(f"[+] PyInstaller found: {PyInstaller.__version__}")
        except ImportError:
            print("[*] Installing PyInstaller...")
            if not run_command("pip install pyinstaller", "Installing PyInstaller"):
                return False
    
    return True

def check_dependencies():
    """Check if required files are available"""
    print("[*] Checking build files...")
    
    # Check if spec file exists
    if not os.path.exists('SniperIT-Agent.spec'):
        print("[-] SniperIT-Agent.spec file not found")
        return False
    print("[+] Spec file found: SniperIT-Agent.spec")
    
    return True

def build_executable():
    """Build the executable using PyInstaller"""
    current_os = platform.system()
    print(f"[*] Building for {current_os}...")
    
    if current_os not in ['Linux', 'Windows', 'Darwin']:
        print(f"[!] Warning: Untested platform '{current_os}'")
    
    print(f"Cross-platform single-file executable")
    
    # Check if we're in a virtual environment and use the appropriate PyInstaller
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    if not in_venv and os.path.exists('.venv'):
        # Use venv's PyInstaller
        if current_os == 'Windows':
            cmd = ".venv\\Scripts\\pyinstaller.exe --clean --noconfirm --distpath dist --workpath build SniperIT-Agent.spec"
        else:
            cmd = ".venv/bin/pyinstaller --clean --noconfirm --distpath dist --workpath build SniperIT-Agent.spec"
    else:
        # Use system or current venv PyInstaller
        cmd = "pyinstaller --clean --noconfirm --distpath dist --workpath build SniperIT-Agent.spec"
    
    success = run_command(cmd, f"Building SniperIT Agent for {current_os}", timeout=600)
    
    if success:
        # Check what was created
        dist_path = Path('dist')
        if dist_path.exists():
            built_files = list(dist_path.iterdir())
            print(f"\n[*] Build Results:")
            for file in built_files:
                size = file.stat().st_size / (1024 * 1024)  # Size in MB
                print(f"   {file.name} ({size:.1f} MB)")
            
            # Show the final executable location
            if current_os == 'Windows':
                exe_path = dist_path / 'SniperIT-Agent.exe'
            else:
                exe_path = dist_path / 'SniperIT-Agent'
            
            if exe_path.exists():
                print(f"\n[+] SUCCESS! Single file executable created:")
                print(f"   Location: {exe_path.absolute()}")
                print(f"   Size: {exe_path.stat().st_size / (1024 * 1024):.1f} MB")
                return True
    
    return False

def main():
    """Main build process"""
    print("SniperIT Agent - Automated Build Process")
    print("=" * 60)
    
    # Check current directory
    if not os.path.exists('main.py'):
        print("[-] Error: main.py not found. Run this script from the project root directory.")
        return 1
    
    # Setup environment and install dependencies
    if not setup_environment():
        return 1
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Clean previous builds
    clean_build_directories()
    
    # Build executable
    if build_executable():
        print("\n[+] BUILD COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        current_os = platform.system()
        if current_os == 'Windows':
            exe_name = 'SniperIT-Agent.exe'
        else:
            exe_name = 'SniperIT-Agent'
        
        print(f"Usage:")
        print(f"   ./dist/{exe_name} --help")
        print(f"   ./dist/{exe_name} --test-only -issl")
        print(f"   ./dist/{exe_name} --generate-fields -issl")
        print(f"   ./dist/{exe_name} -issl")
        
        return 0
    else:
        print("\n[-] BUILD FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())