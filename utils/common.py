# common.py

import sys
import subprocess
import os
import platform

# Determine the operating system
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'

def run_command(cmd):
    """Run system commands with OS-specific handling"""
    try:
        if IS_WINDOWS:
            # Windows: Use PowerShell
            # The flag to prevent the console window from showing up
            CREATE_NO_WINDOW = 0x08000000
            completed = subprocess.Popen(["powershell.exe", "-Command", cmd],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       text=True,
                                       creationflags=CREATE_NO_WINDOW)
        elif IS_LINUX:
            # Linux: Use bash directly for the command
            if cmd.startswith("(") or cmd.startswith("["):
                # PowerShell-style command, convert to bash
                bash_cmd = convert_powershell_to_bash(cmd)
                completed = subprocess.Popen(["bash", "-c", bash_cmd],
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE,
                                           text=True)
            else:
                # Regular bash command
                completed = subprocess.Popen(["bash", "-c", cmd],
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE,
                                           text=True)
        else:
            raise Exception(f"Unsupported operating system: {platform.system()}")
        
        # Wait for the command to complete and get the output
        stdout, stderr = completed.communicate()
        
        # Return the standard output
        return stdout.strip()
    except FileNotFoundError:
        raise Exception(f"Could not find shell executable for {platform.system()}")
    except Exception as e:
        raise Exception(f"Command execution failed: {e}")

def convert_powershell_to_bash(cmd):
    """Convert basic PowerShell commands to bash equivalents"""
    # Remove PowerShell-specific syntax and convert to bash
    bash_cmd = cmd
    
    # Convert Get-WmiObject to appropriate Linux commands
    if "Get-WmiObject Win32_OperatingSystem" in cmd:
        if "CSName" in cmd:
            bash_cmd = "hostname"
        elif "Caption" in cmd:
            bash_cmd = "lsb_release -d | cut -f2"
        elif "InstallDate" in cmd:
            bash_cmd = "stat -c '%W' /etc/os-release"
    
    elif "Get-WmiObject Win32_ComputerSystem" in cmd:
        if "manufacturer" in cmd:
            bash_cmd = "cat /sys/class/dmi/id/sys_vendor 2>/dev/null || echo 'Unknown Manufacturer'"
        elif "TotalPhysicalMemory" in cmd:
            bash_cmd = "free -b | awk 'NR==2{printf \"%.0f\", $2}'"
        elif "totalphysicalmemory" in cmd:
            # Handle RAM calculation - convert to GB and round to 1 decimal
            bash_cmd = "free -g | awk 'NR==2{printf \"%.1f\", $2}'"
    
    elif "Get-WmiObject Win32_BIOS" in cmd:
        if "serialnumber" in cmd:
            bash_cmd = "cat /sys/class/dmi/id/product_serial 2>/dev/null || echo 'Unknown'"
        elif "ReleaseDate" in cmd:
            bash_cmd = "cat /sys/class/dmi/id/bios_date 2>/dev/null || echo 'Unknown'"
    
    elif "Get-WmiObject Win32_Processor" in cmd:
        bash_cmd = "cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d: -f2 | sed 's/^ *//'"
    
    elif "gwmi win32_baseboard" in cmd:
        if "product" in cmd:
            bash_cmd = "cat /sys/class/dmi/id/product_name 2>/dev/null || echo 'Unknown'"
    
    elif "Test-Connection" in cmd:
        # Extract hostname from PowerShell Test-Connection command
        import re
        match = re.search(r'Test-Connection\s+([^-\s]+)', cmd)
        if match:
            hostname = match.group(1)
            bash_cmd = f"ping -c 1 {hostname} | grep -oE '([0-9]{{1,3}}\\.){{3}}[0-9]{{1,3}}' | head -1"
    
    elif "[System.Security.Principal.WindowsIdentity]::GetCurrent()" in cmd:
        bash_cmd = "whoami"
    
    # Handle complex memory calculations
    elif "Math" in cmd and "Round" in cmd and "TotalPhysicalMemory" in cmd:
        if "1gb" in cmd or "1GB" in cmd:
            # Convert to GB and round to 1 decimal
            bash_cmd = "free -g | awk 'NR==2{printf \"%.1f\", $2}'"
        elif "FreePhysicalMemory" in cmd:
            # Calculate used memory in GB
            bash_cmd = "free -g | awk 'NR==2{printf \"%.1f\", $3}'"
    
    # Handle free memory calculations  
    elif "FreePhysicalMemory" in cmd and "1024" in cmd and "1GB" in cmd:
        # Calculate used memory in GB (Total - Free)
        bash_cmd = "free -g | awk 'NR==2{printf \"%.1f\", $3}'"
    
    # For commands that can't be easily converted, return a placeholder
    if bash_cmd == cmd and ("Get-WmiObject" in cmd or "powershell" in cmd.lower() or "[Math]" in cmd):
        bash_cmd = "echo 'Command not supported on Linux'"
    
    return bash_cmd

def format_number(val):
    """Format numbers for display, handling both integers and floats"""
    try:
        # Try converting the input to a float, replacing commas with dots if necessary
        number = float(val.replace(',', '.'))
        # Check if the number is an integer by comparing it with its integer version
        if number == int(number):
            # If it's an integer, return the integer part
            return str(int(number))
        else:
            # If it's a float, format it with one decimal place
            return "{:.1f}".format(number)
    except ValueError:
        # If conversion to a float fails, return the original input
        return val

# Resolve pyinstaller's executable path issue
def resolve_path(path):
    if getattr(sys, "frozen", False):
        # If the 'frozen' flag is set, we are in bundled-app mode!
        # For PyInstaller single-file mode, use _MEIPASS if available
        if hasattr(sys, '_MEIPASS'):
            # Single-file executable - files are in temporary directory
            meipass_path = os.path.join(sys._MEIPASS, path)
            if os.path.exists(meipass_path):
                return meipass_path
            # Also check in config subdirectory within _MEIPASS
            config_meipass_path = os.path.join(sys._MEIPASS, "config", path)
            if os.path.exists(config_meipass_path):
                return config_meipass_path
        
        # Fallback: Use the directory of the executable
        application_path = os.path.dirname(sys.executable)
        # Check if file exists in the main directory
        resolved_path = os.path.abspath(os.path.join(application_path, path))
        if os.path.exists(resolved_path):
            return resolved_path
        # Check in config directory
        config_path = os.path.join(application_path, "config", path)
        if os.path.exists(config_path):
            return config_path
        # If not found, check in _internal directory
        internal_path = os.path.join(application_path, "_internal", path)
        if os.path.exists(internal_path):
            return internal_path
        # Return the original path if neither exists
        return resolved_path
    else:
        # Normal development mode - check config directory first
        config_path = os.path.abspath(os.path.join(os.getcwd(), "config", path))
        if os.path.exists(config_path):
            return config_path
        # Fallback to original behavior
        resolved_path = os.path.abspath(os.path.join(os.getcwd(), path))

    return resolved_path