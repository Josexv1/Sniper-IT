#!/usr/bin/env python3
"""
Sniper-IT Agent V2 - Enhanced Build System
Automated build script with pre-checks, validation, and artifact generation
"""

import os
import sys
import platform
import subprocess
import shutil
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime

# Configure UTF-8 encoding for console output on Windows
if sys.version_info >= (3, 7) and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ANSI color codes for output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def colored(text, color):
    """Return colored text for terminal"""
    if platform.system() == 'Windows':
        # Enable ANSI colors on Windows 10+
        os.system('color')
    return f"{color}{text}{Colors.RESET}"

def print_header(text):
    """Print a section header"""
    bold_cyan = Colors.BOLD + Colors.CYAN
    print(f"\n{colored('═' * 70, Colors.CYAN)}")
    print(colored(f"  {text}", bold_cyan))
    print(colored('═' * 70, Colors.CYAN))

def print_step(text):
    """Print a step message"""
    print(f"{colored('[*]', Colors.BLUE)} {text}")

def print_success(text):
    """Print a success message"""
    print(f"{colored('[OK]', Colors.GREEN)} {text}")

def print_warning(text):
    """Print a warning message"""
    print(f"{colored('[!]', Colors.YELLOW)} {text}")

def print_error(text):
    """Print an error message"""
    print(f"{colored('[ERROR]', Colors.RED)} {text}")

def run_command(cmd, description, timeout=300, show_output=False):
    """Run a command and handle output with timeout"""
    print_step(f"{description}...")
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            check=True, 
            timeout=timeout
        )
        print_success(f"{description} completed")
        if show_output and result.stdout:
            print(f"   {result.stdout.strip()}")
        return True, result.stdout
    except subprocess.TimeoutExpired:
        print_error(f"{description} timed out after {timeout} seconds")
        return False, ""
    except subprocess.CalledProcessError as e:
        print_error(f"{description} failed")
        if e.stderr:
            print(f"   {e.stderr.strip()}")
        return False, e.stderr

def get_version():
    """Get version from core/constants.py"""
    try:
        constants_path = Path('core/constants.py')
        if constants_path.exists():
            with open(constants_path, 'r') as f:
                for line in f:
                    if line.startswith('VERSION'):
                        # Extract version from VERSION = "2.0.0"
                        version = line.split('=')[1].strip().strip('"').strip("'")
                        return version
        return "2.0.0"  # Default version
    except Exception as e:
        print_warning(f"Could not read version: {e}")
        return "2.0.0"

def validate_project_structure():
    """Validate that all required files and directories exist"""
    print_header("PROJECT STRUCTURE VALIDATION")
    
    required_files = [
        'main.py',
        'requirements.txt',
        'Sniper-IT-Agent.spec'
    ]
    
    required_dirs = [
        'core',
        'collectors',
        'managers',
        'cli',
        'utils'
    ]
    
    all_valid = True
    
    # Check files
    for file in required_files:
        if Path(file).exists():
            print_success(f"Found: {file}")
        else:
            print_error(f"Missing: {file}")
            all_valid = False
    
    # Check directories
    for dir_name in required_dirs:
        if Path(dir_name).is_dir():
            print_success(f"Found: {dir_name}/")
        else:
            print_error(f"Missing: {dir_name}/")
            all_valid = False
    
    return all_valid

def check_python_syntax():
    """Check Python syntax for all .py files"""
    print_header("PYTHON SYNTAX CHECK")
    
    python_files = list(Path('.').rglob('*.py'))
    errors = []
    
    for py_file in python_files:
        if '.venv' in str(py_file) or 'build' in str(py_file):
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                compile(f.read(), py_file, 'exec')
            print_success(f"Syntax OK: {py_file}")
        except SyntaxError as e:
            print_error(f"Syntax error in {py_file}: {e}")
            errors.append(str(py_file))
    
    if errors:
        print_error(f"Found {len(errors)} files with syntax errors")
        return False
    
    print_success(f"All {len(python_files)} Python files have valid syntax")
    return True


def clean_build_directories():
    """Clean up previous build artifacts"""
    print_header("CLEANING BUILD ARTIFACTS")
    
    # PyInstaller build directories
    dirs_to_clean = ['build', 'dist']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name, ignore_errors=True)
                print_success(f"Removed: {dir_name}/")
            except Exception as e:
                print_warning(f"Could not remove {dir_name}/: {e}")
        else:
            print_step(f"Directory not found: {dir_name}/")
    
    # Clean build reports
    build_reports = list(Path('.').glob('build-report-*.json'))
    for report in build_reports:
        try:
            report.unlink()
            print_success(f"Removed: {report.name}")
        except Exception as e:
            print_warning(f"Could not remove {report.name}: {e}")
    
    # Clean build metadata
    build_info = Path('core/build_info.json')
    if build_info.exists():
        try:
            build_info.unlink()
            print_success(f"Removed: {build_info}")
        except Exception as e:
            print_warning(f"Could not remove {build_info}: {e}")
    
    # Clean build secrets
    build_secrets = Path('core/build_secrets.py')
    if build_secrets.exists():
        try:
            build_secrets.unlink()
            print_success(f"Removed: {build_secrets}")
        except Exception as e:
            print_warning(f"Could not remove {build_secrets}: {e}")
    
    # Clean Python cache files recursively
    print_step("Cleaning Python cache files...")
    cache_count = 0
    for root, dirs, files in os.walk('.'):
        # Skip virtual environments and git
        if any(skip in root for skip in ['.venv', 'venv', 'env', '.git']):
            continue
            
        # Remove .pyc files
        for file in files:
            if file.endswith('.pyc') or file.endswith('.pyo'):
                try:
                    os.remove(os.path.join(root, file))
                    cache_count += 1
                except:
                    pass
                    
        # Remove __pycache__ directories
        if '__pycache__' in dirs:
            cache_path = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(cache_path, ignore_errors=True)
                cache_count += 1
            except:
                pass
    
    if cache_count > 0:
        print_success(f"Removed {cache_count} cache files/directories")
    
    # Clean PyInstaller spec leftovers
    spec_files = list(Path('.').glob('*.spec~'))
    for spec in spec_files:
        try:
            spec.unlink()
            print_success(f"Removed: {spec.name}")
        except:
            pass
    
    print_success("Build artifacts cleaned successfully")

def setup_environment():
    """Setup virtual environment and install dependencies"""
    print_header("ENVIRONMENT SETUP")
    
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    current_os = platform.system()
    venv_name = ".venv"
    
    # Check if .venv already exists
    venv_exists = os.path.exists(venv_name)
    
    if not in_venv:
        if venv_exists:
            print_warning("Not in virtual environment, but .venv exists")
            print_step("Using existing .venv...")
        else:
            print_warning("Not in a virtual environment")
            print_step("Creating virtual environment...")
            
            success, _ = run_command(
                f"{sys.executable} -m venv {venv_name}", 
                "Creating virtual environment"
            )
            
            if not success:
                return False
            
            print_success(f"Virtual environment created: {venv_name}/")
        
        # Get paths for the venv
        if current_os == 'Windows':
            pip_path = f"{venv_name}\\Scripts\\pip.exe"
            python_path = f"{venv_name}\\Scripts\\python.exe"
        else:
            pip_path = f"{venv_name}/bin/pip"
            python_path = f"{venv_name}/bin/python"
        
        # Upgrade pip in venv
        if not venv_exists:
            print_step("Upgrading pip in venv...")
            run_command(f'"{pip_path}" install --upgrade pip', "Upgrading pip")
        
        # Install requirements
        if os.path.exists('requirements.txt'):
            success, _ = run_command(
                f'"{pip_path}" install -r requirements.txt', 
                "Installing requirements",
                timeout=600
            )
            if not success:
                return False
        
        print_success("Dependencies installed in virtual environment")
    else:
        print_success("Virtual environment detected")
        
        # Update pip
        print_step("Ensuring pip is up to date...")
        run_command("pip install --upgrade pip", "Upgrading pip")
        
        # Install/update requirements
        if os.path.exists('requirements.txt'):
            success, _ = run_command(
                "pip install -r requirements.txt", 
                "Installing/updating requirements",
                timeout=600
            )
            if not success:
                return False
    
    # Verify PyInstaller
    try:
        import PyInstaller
        print_success(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print_step("Installing PyInstaller...")
        success, _ = run_command("pip install pyinstaller", "Installing PyInstaller")
        if not success:
            return False
    
    return True

def inject_build_metadata():
    """Inject build metadata into the application"""
    print_header("INJECTING BUILD METADATA")
    
    version = get_version()
    build_time = datetime.now().isoformat()
    build_os = platform.system()
    build_arch = platform.machine()
    
    metadata = {
        'version': version,
        'build_time': build_time,
        'build_os': build_os,
        'build_arch': build_arch,
        'python_version': platform.python_version()
    }
    
    # Create build_info.json
    build_info_path = Path('core/build_info.json')
    build_info_path.parent.mkdir(exist_ok=True)
    
    with open(build_info_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print_success(f"Build metadata created: {build_info_path}")
    print(f"   Version: {version}")
    print(f"   Build Time: {build_time}")
    print(f"   Build OS: {build_os}")
    
    return metadata

def inject_build_secrets(url=None, api_key=None, ignore_ssl=False):
    """
    Inject build-time secrets into the application
    
    Args:
        url: Snipe-IT server URL to hardcode
        api_key: API key to hardcode
        ignore_ssl: Whether to ignore SSL certificate verification
    """
    print_header("INJECTING BUILD SECRETS")
    
    # Create build_secrets.py
    build_secrets_path = Path('core/build_secrets.py')
    build_secrets_path.parent.mkdir(exist_ok=True)
    
    # Template for build_secrets.py
    template = '''"""
Build-time secrets - Auto-generated by build.py
DO NOT COMMIT THIS FILE TO VERSION CONTROL
"""

# Hardcoded credentials (set during build time)
BUILD_SERVER_URL = {url}
BUILD_API_KEY = {api_key}
BUILD_IGNORE_SSL = {ignore_ssl}  # Set via --ignore-ssl flag
'''.format(
        url=repr(url) if url else 'None',
        api_key=repr(api_key) if api_key else 'None',
        ignore_ssl=ignore_ssl
    )
    
    with open(build_secrets_path, 'w', encoding='utf-8') as f:
        f.write(template)
    
    if url and api_key:
        print_success(f"Build secrets injected: {build_secrets_path}")
        print(f"   URL: {url}")
        print(f"   API Key: {'*' * 20}...{api_key[-4:] if len(api_key) > 4 else '****'}")
        print(f"   Ignore SSL: {ignore_ssl}")
        if ignore_ssl:
            print_warning("SSL verification will be disabled - use only with self-signed certificates")
        print_warning("This executable has credentials baked in - distribute securely!")
    else:
        print_step(f"No secrets provided - creating empty template: {build_secrets_path}")
        print(f"   Build will use config.yaml at runtime")
    
    return bool(url and api_key)

def build_executable():
    """Build the executable using PyInstaller"""
    print_header("BUILDING EXECUTABLE")
    
    current_os = platform.system()
    print_step(f"Building for {current_os}...")
    
    # Determine PyInstaller path
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if not in_venv and os.path.exists('.venv'):
        if current_os == 'Windows':
            pyinstaller_cmd = ".venv\\Scripts\\pyinstaller.exe"
        else:
            pyinstaller_cmd = ".venv/bin/pyinstaller"
    else:
        pyinstaller_cmd = "pyinstaller"
    
    # Build command (no --clean flag, we cleaned manually before)
    cmd = f"{pyinstaller_cmd} --noconfirm --distpath dist --workpath build Sniper-IT-Agent.spec"
    
    success, _ = run_command(cmd, f"Building Sniper-IT Agent for {current_os}", timeout=900)
    
    if not success:
        return False, None
    
    # Verify build results
    dist_path = Path('dist')
    if not dist_path.exists():
        print_error("dist/ directory not created")
        return False, None
    
    # Find executable
    if current_os == 'Windows':
        exe_path = dist_path / 'Sniper-IT-Agent.exe'
    else:
        exe_path = dist_path / 'Sniper-IT-Agent'
    
    if not exe_path.exists():
        print_error(f"Executable not found: {exe_path}")
        return False, None
    
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print_success(f"Executable created: {exe_path.name}")
    print(f"   Location: {exe_path.absolute()}")
    print(f"   Size: {size_mb:.2f} MB")
    
    return True, exe_path

def generate_checksums(exe_path):
    """Generate checksums for the executable"""
    print_header("GENERATING CHECKSUMS")
    
    if not exe_path or not exe_path.exists():
        print_error("Executable not found, skipping checksum generation")
        return None
    
    checksums = {}
    
    # Generate SHA256
    print_step("Calculating SHA256...")
    sha256_hash = hashlib.sha256()
    with open(exe_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256_hash.update(chunk)
    checksums['sha256'] = sha256_hash.hexdigest()
    print_success(f"SHA256: {checksums['sha256']}")
    
    # Generate MD5
    print_step("Calculating MD5...")
    md5_hash = hashlib.md5()
    with open(exe_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            md5_hash.update(chunk)
    checksums['md5'] = md5_hash.hexdigest()
    print_success(f"MD5: {checksums['md5']}")
    
    # Save checksums to file
    checksum_file = exe_path.parent / f"{exe_path.name}.checksums.txt"
    with open(checksum_file, 'w', encoding='utf-8') as f:
        f.write(f"PyIT Agent - Checksums\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"File: {exe_path.name}\n")
        f.write(f"Size: {exe_path.stat().st_size:,} bytes\n")
        f.write(f"\nSHA256: {checksums['sha256']}\n")
        f.write(f"MD5: {checksums['md5']}\n")
    
    print_success(f"Checksums saved: {checksum_file}")
    
    return checksums

def create_build_report(metadata, exe_path, checksums):
    """Create a comprehensive build report"""
    print_header("GENERATING BUILD REPORT")
    
    version = metadata['version']
    build_time = metadata['build_time']
    
    report = {
        'build_info': metadata,
        'executable': {
            'name': exe_path.name if exe_path else None,
            'path': str(exe_path.absolute()) if exe_path else None,
            'size_bytes': exe_path.stat().st_size if exe_path else None,
            'size_mb': round(exe_path.stat().st_size / (1024 * 1024), 2) if exe_path else None
        },
        'checksums': checksums,
        'build_status': 'success' if exe_path else 'failed'
    }
    
    # Save JSON report
    report_file = Path(f'build-report-{version}.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    print_success(f"Build report created: {report_file}")
    
    # Create human-readable report
    readme_file = Path('dist/README.txt')
    if exe_path:
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(f"Sniper-IT Agent v{version}\n")
            f.write(f"{'=' * 60}\n\n")
            f.write(f"Build Information:\n")
            f.write(f"  Build Time: {build_time}\n")
            f.write(f"  Build OS: {metadata['build_os']}\n")
            f.write(f"  Build Arch: {metadata['build_arch']}\n")
            f.write(f"  Python Version: {metadata['python_version']}\n\n")
            f.write(f"Executable:\n")
            f.write(f"  Name: {exe_path.name}\n")
            f.write(f"  Size: {report['executable']['size_mb']} MB\n\n")
            if checksums:
                f.write(f"Checksums:\n")
                f.write(f"  SHA256: {checksums['sha256']}\n")
                f.write(f"  MD5: {checksums['md5']}\n\n")
            f.write(f"Usage:\n")
            f.write(f"  ./{exe_path.name} --help\n")
            f.write(f"  ./{exe_path.name} --setup\n")
            f.write(f"  ./{exe_path.name} --test\n")
            f.write(f"  ./{exe_path.name} --issl\n\n")
        
        print_success(f"README created: {readme_file}")
    
    return report

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Sniper-IT Agent V2 - Build System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python build.py                                                     # Normal build
  python build.py --clean                                             # Clean all build artifacts only
  python build.py --url https://snipeit.com --api-key YOUR_KEY       # Build with hardcoded credentials
  python build.py --url https://snipeit.com --api-key YOUR_KEY --ignore-ssl  # With SSL ignore
        '''
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clean all PyInstaller build artifacts and exit (no build)'
    )
    parser.add_argument(
        '--url',
        type=str,
        help='Hardcode Snipe-IT server URL into the executable'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        help='Hardcode API key into the executable (for distribution)'
    )
    parser.add_argument(
        '--ignore-ssl',
        action='store_true',
        help='Hardcode SSL ignore flag (for self-signed certificates)'
    )
    return parser.parse_args()

def main():
    """Main build process"""
    # Parse command line arguments
    args = parse_arguments()
    
    print_header("Sniper-IT Agent V2 - Build System")
    
    version = get_version()
    bold_cyan = Colors.BOLD + Colors.CYAN
    print(f"\n{colored(f'Version: {version}', bold_cyan)}\n")
    
    # Check we're in the right directory
    if not os.path.exists('main.py'):
        print_error("main.py not found. Run this script from the project root directory.")
        return 1
    
    # If --clean flag is provided, only clean and exit
    if args.clean:
        clean_build_directories()
        print()
        print(colored("✓ Clean completed successfully!", Colors.GREEN))
        print(f"\n{colored('Tip:', Colors.BOLD)} Run {colored('python build.py', Colors.CYAN)} to build the project.\n")
        return 0
    
    # Step 1: Validate project structure
    if not validate_project_structure():
        print_error("Project structure validation failed")
        return 1
    
    # Step 2: Check Python syntax
    if not check_python_syntax():
        print_error("Python syntax check failed")
        return 1
    
    # Step 3: Setup environment (installs dependencies)
    if not setup_environment():
        print_error("Environment setup failed")
        return 1
    
    # Step 4: Clean build directories
    clean_build_directories()
    
    # Step 5: Inject build secrets (if provided)
    has_secrets = inject_build_secrets(args.url, args.api_key, args.ignore_ssl)
    
    # Step 6: Inject build metadata
    metadata = inject_build_metadata()
    
    # Step 7: Build executable
    success, exe_path = build_executable()
    if not success:
        print_error("Build failed")
        return 1
    
    # Step 8: Generate checksums
    checksums = generate_checksums(exe_path)
    
    # Step 9: Create build report
    report = create_build_report(metadata, exe_path, checksums)
    
    # Final success message
    print_header("BUILD COMPLETED SUCCESSFULLY")
    exe_size = report["executable"]["size_mb"]
    sha_short = checksums.get('sha256', '')[:16] + '...' if checksums else ''
    
    print(f"\n{colored('✓', Colors.GREEN)} Executable: {colored(str(exe_path.absolute()), Colors.BOLD)}")
    print(f"{colored('✓', Colors.GREEN)} Size: {colored(f'{exe_size} MB', Colors.BOLD)}")
    if checksums:
        print(f"{colored('✓', Colors.GREEN)} SHA256: {colored(sha_short, Colors.BOLD)}")
    print(f"\n{colored('Next steps:', Colors.BOLD)}")
    print(f"  1. Test: {colored(f'./{exe_path.name} --test', Colors.CYAN)}")
    print(f"  2. Setup: {colored(f'./{exe_path.name} --setup', Colors.CYAN)}")
    print(f"  3. Check: {colored('dist/README.txt', Colors.CYAN)} for usage instructions")
    print()
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{colored('[!]', Colors.YELLOW)} Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n{colored('[ERROR]', Colors.RED)} Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
