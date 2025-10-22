"""
Sniper-IT Agent - System Data Collector
Collects system information using regular user privileges (no admin required)
Supports Windows and Linux platforms
"""

import platform
import subprocess
import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from utils.exceptions import DataCollectionError
from core.constants import VERSION


class SystemDataCollector:
    """
    Collects system data using commands that work with regular domain user privileges.
    All commands are tested to work without administrative/elevated permissions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the system data collector
        
        Args:
            config: Optional configuration dictionary with custom fields definitions
        """
        self.os_type = platform.system()
        self.config = config or {}
        self.collected_data: Dict[str, Any] = {}
        self.custom_fields: Dict[str, str] = {}
        
    def collect_all(self) -> Dict[str, Any]:
        """
        Collect all system data based on the operating system
        
        Returns:
            Dictionary containing:
                - system_data: Core system information
                - custom_fields: Data formatted for Snipe-IT custom fields
                - os_type: Operating system type
                - asset_type: Asset type ("laptop", "desktop", or "server")
                
        Raises:
            DataCollectionError: If critical data collection fails
        """
        try:
            if self.os_type == "Windows":
                self._collect_windows_data()
            elif self.os_type == "Linux":
                self._collect_linux_data()
            else:
                self._collect_generic_data()
            
            # Always add agent version
            self.collected_data['agent_version'] = VERSION
            
            # Map collected data to custom fields format
            self._map_to_custom_fields()
            
            return {
                'system_data': self.collected_data,
                'custom_fields': self.custom_fields,
                'os_type': self.os_type,
                'asset_type': self.get_asset_type()  # "laptop", "desktop", or "server"
            }
            
        except Exception as e:
            raise DataCollectionError(f"Failed to collect system data: {e}")
    
    def _collect_windows_data(self) -> None:
        """
        Collect Windows system data using CIM/WMI queries.
        All commands work with regular domain user privileges.
        """
        # Basic system information
        self.collected_data['hostname'] = self._run_powershell("$env:COMPUTERNAME")
        self.collected_data['manufacturer'] = self._run_powershell(
            "(Get-CimInstance -ClassName Win32_ComputerSystem).Manufacturer"
        )
        self.collected_data['model'] = self._run_powershell(
            "(Get-CimInstance -ClassName Win32_ComputerSystem).Model"
        )
        self.collected_data['serial_number'] = self._run_powershell(
            "(Get-CimInstance -ClassName Win32_BIOS).SerialNumber"
        )
        
        # Detect chassis type to determine if laptop or desktop
        # ChassisTypes: 3=Desktop, 4=Low Profile Desktop, 5=Pizza Box, 6=Mini Tower, 7=Tower
        #               8=Portable, 9=Laptop, 10=Notebook, 11=Hand Held, 12=Docking Station
        #               13=All in One, 14=Sub Notebook, 30=Tablet, 31=Convertible, 32=Detachable
        chassis_type = self._run_powershell(
            "(Get-CimInstance -ClassName Win32_SystemEnclosure).ChassisTypes[0]"
        )
        self.collected_data['chassis_type'] = chassis_type if chassis_type else "Unknown"
        
        # Hardware information - Processor
        self.collected_data['processor'] = self._run_powershell(
            "(Get-CimInstance -ClassName Win32_Processor).Name"
        )
        
        # Memory information (RAM)
        total_memory_gb = self._run_powershell(
            "[Math]::Round((Get-CimInstance -ClassName Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)"
        )
        self.collected_data['memory_total_gb'] = f"{total_memory_gb} GB" if total_memory_gb else "Unknown"
        
        # RAM Usage calculation - Combined command for reliability
        ram_usage = self._run_powershell(
            "$os = Get-CimInstance -ClassName Win32_OperatingSystem; $cs = Get-CimInstance -ClassName Win32_ComputerSystem; $totalGB = [Math]::Round($cs.TotalPhysicalMemory / 1GB, 2); $freeGB = [Math]::Round($os.FreePhysicalMemory / 1MB, 2); $usedGB = $totalGB - $freeGB; $percent = [Math]::Round(($usedGB / $totalGB) * 100, 1); \"$usedGB GB / $totalGB GB ($percent%)\""
        )
        self.collected_data['ram_usage'] = ram_usage if ram_usage else "Unknown"
        
        # Storage information - Total storage from physical disks
        total_storage = self._run_powershell(
            "$total = 0; Get-CimInstance -ClassName Win32_DiskDrive | Where-Object { $_.MediaType -match 'Fixed' } | ForEach-Object { $total += $_.Size }; [Math]::Round($total / 1GB, 2)"
        )
        self.collected_data['total_storage_gb'] = f"{total_storage} GB" if total_storage else "Unknown"
        
        # Disk space used on C: drive - Combined command for reliability
        disk_usage = self._run_powershell(
            "$disk = Get-CimInstance -ClassName Win32_LogicalDisk -Filter \"DeviceID='C:'\"; $totalGB = [Math]::Round($disk.Size / 1GB, 2); $usedGB = [Math]::Round(($disk.Size - $disk.FreeSpace) / 1GB, 2); $percent = [Math]::Round(($usedGB / $totalGB) * 100, 1); \"$usedGB GB / $totalGB GB ($percent%)\""
        )
        self.collected_data['disk_space_used'] = disk_usage if disk_usage else "Unknown"
        
        # Storage details (disk models and info)
        storage_info = self._run_powershell(
            "Get-CimInstance -ClassName Win32_DiskDrive | Where-Object { $_.MediaType -match 'Fixed' } | ForEach-Object { \"$($_.Model) - $([Math]::Round($_.Size/1GB,2)) GB\" } | Select-Object -First 3"
        )
        self.collected_data['storage_information'] = storage_info if storage_info else "Unknown"
        
        # Network information - IP Address (active adapter)
        ip_address = self._run_powershell(
            "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback' -and $_.PrefixOrigin -eq 'Dhcp' -or $_.PrefixOrigin -eq 'Manual' } | Select-Object -First 1).IPAddress"
        )
        # Fallback if Get-NetIPAddress fails
        if not ip_address:
            ip_address = self._run_powershell(
                "(Test-Connection -ComputerName $env:COMPUTERNAME -Count 1).IPv4Address.IPAddressToString"
            )
        self.collected_data['ip_address'] = ip_address if ip_address else "Unknown"
        
        # MAC Address (active adapter)
        mac_address = self._run_powershell(
            "(Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.Physical -eq $true } | Select-Object -First 1).MacAddress"
        )
        # Fallback to WMI if Get-NetAdapter fails
        if not mac_address:
            mac_address = self._run_powershell(
                "(Get-CimInstance -ClassName Win32_NetworkAdapterConfiguration | Where-Object { $_.IPEnabled -eq $true } | Select-Object -First 1).MACAddress"
            )
        self.collected_data['mac_address'] = mac_address if mac_address else "Unknown"
        
        # Operating System information
        os_caption = self._run_powershell(
            "(Get-CimInstance -ClassName Win32_OperatingSystem).Caption"
        )
        os_version = self._run_powershell(
            "(Get-CimInstance -ClassName Win32_OperatingSystem).Version"
        )
        if os_caption and os_version:
            self.collected_data['operating_system'] = f"{os_caption} ({os_version})"
        elif os_caption:
            self.collected_data['operating_system'] = os_caption
        else:
            self.collected_data['operating_system'] = "Windows (Unknown Version)"
        
        # OS Install Date
        install_date = self._run_powershell(
            "(Get-CimInstance -ClassName Win32_OperatingSystem).InstallDate.ToString('yyyy-MM-dd HH:mm:ss')"
        )
        self.collected_data['os_install_date'] = install_date if install_date else "Unknown"
        
        # BIOS Release Date
        bios_date = self._run_powershell(
            "$bios = Get-CimInstance -ClassName Win32_BIOS; if ($bios.ReleaseDate) { $bios.ReleaseDate.ToString('yyyy-MM-dd') } else { 'Unknown' }"
        )
        self.collected_data['bios_release_date'] = bios_date if bios_date else "Unknown"
        
        # Current User
        current_user = self._run_powershell(
            "$user = [System.Security.Principal.WindowsIdentity]::GetCurrent(); $user.Name"
        )
        self.collected_data['username'] = current_user if current_user else "Unknown"
        
        # Optional fields
        self._collect_optional_windows_fields()
    
    def _collect_optional_windows_fields(self) -> None:
        """Collect optional Windows fields if enabled in config"""
        optional_fields = self.config.get('custom_fields', {}).get('optional_fields', {})
        
        # CPU Temperature (usually not available on Windows without 3rd party tools)
        if optional_fields.get('cpu_temperature', {}).get('enabled', False):
            self.collected_data['cpu_temperature'] = "Not Available (Windows)"
        
        # System Uptime
        if optional_fields.get('system_uptime', {}).get('enabled', False):
            uptime = self._run_powershell(
                "$bootTime = (Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime; $uptime = (Get-Date) - $bootTime; [Math]::Round($uptime.TotalDays, 2)"
            )
            self.collected_data['system_uptime'] = f"{uptime} days" if uptime else "Unknown"
        
        # Screen Size (monitor information)
        if optional_fields.get('screen_size', {}).get('enabled', False):
            screen_size = self._run_powershell(
                "$monitors = Get-CimInstance -Namespace root\\wmi -ClassName WmiMonitorBasicDisplayParams; if ($monitors) { $monitor = $monitors | Select-Object -First 1; \"$($monitor.MaxHorizontalImageSize) x $($monitor.MaxVerticalImageSize) cm\" } else { 'Unknown' }"
            )
            self.collected_data['screen_size'] = screen_size if screen_size else "Unknown"
    
    def _collect_linux_data(self) -> None:
        """
        Collect Linux system data using standard commands.
        All commands work with regular user privileges.
        """
        # Basic system information
        self.collected_data['hostname'] = self._run_bash("hostname")
        self.collected_data['manufacturer'] = self._run_bash(
            "cat /sys/class/dmi/id/sys_vendor 2>/dev/null || echo 'Generic'"
        )
        self.collected_data['model'] = self._run_bash(
            "cat /sys/class/dmi/id/product_name 2>/dev/null || echo 'Generic Model'"
        )
        
        # Serial number with multiple fallbacks
        serial = self._run_bash("cat /sys/class/dmi/id/product_serial 2>/dev/null")
        if not serial or serial.lower() in ['unknown', 'not specified', 'to be filled by o.e.m.']:
            serial = self._run_bash("cat /sys/class/dmi/id/board_serial 2>/dev/null")
        if not serial or serial.lower() in ['unknown', 'not specified']:
            # Generate consistent serial from hostname and MAC
            hostname = self.collected_data.get('hostname', 'unknown')
            mac = self._run_bash("cat /sys/class/net/$(ls /sys/class/net | grep -v lo | head -1)/address 2>/dev/null")
            if mac:
                serial = f"LINUX-{hostname}-{mac.replace(':', '')[:8].upper()}"
            else:
                serial = f"LINUX-{hostname}"
        self.collected_data['serial_number'] = serial
        
        # Hardware - Processor
        processor = self._run_bash(
            "cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d: -f2 | sed 's/^ *//'"
        )
        self.collected_data['processor'] = processor if processor else "Unknown"
        
        # Memory information
        total_memory = self._run_bash("free -g | awk 'NR==2{printf \"%.2f\", $2}'")
        self.collected_data['memory_total_gb'] = f"{total_memory} GB" if total_memory else "Unknown"
        
        used_memory = self._run_bash("free -g | awk 'NR==2{printf \"%.2f\", $3}'")
        if total_memory and used_memory:
            try:
                total = float(total_memory)
                used = float(used_memory)
                percent = (used / total) * 100 if total > 0 else 0
                self.collected_data['ram_usage'] = f"{used:.2f} GB ({percent:.1f}%)"
            except ValueError:
                self.collected_data['ram_usage'] = "Unknown"
        else:
            self.collected_data['ram_usage'] = "Unknown"
        
        # Storage information
        total_storage = self._run_bash("lsblk -d -b -o SIZE | tail -n +2 | awk '{sum+=$1} END {printf \"%.2f\", sum/1024/1024/1024}'")
        self.collected_data['total_storage_gb'] = f"{total_storage} GB" if total_storage else "Unknown"
        
        disk_used = self._run_bash("df -BG / | tail -1 | awk '{print $3}' | sed 's/G//'")
        disk_total = self._run_bash("df -BG / | tail -1 | awk '{print $2}' | sed 's/G//'")
        if disk_used and disk_total:
            try:
                used = float(disk_used)
                total = float(disk_total)
                percent = (used / total) * 100 if total > 0 else 0
                self.collected_data['disk_space_used'] = f"{used:.2f} GB / {total:.2f} GB ({percent:.1f}%)"
            except ValueError:
                self.collected_data['disk_space_used'] = "Unknown"
        else:
            self.collected_data['disk_space_used'] = "Unknown"
        
        storage_info = self._run_bash("lsblk -d -o NAME,MODEL,SIZE | tail -n +2 | head -3 | tr '\\n' '; '")
        self.collected_data['storage_information'] = storage_info if storage_info else "Unknown"
        
        # Network information
        ip_address = self._run_bash("hostname -I | awk '{print $1}'")
        self.collected_data['ip_address'] = ip_address if ip_address else "Unknown"
        
        mac_address = self._run_bash(
            "cat /sys/class/net/$(ls /sys/class/net | grep -v lo | head -1)/address 2>/dev/null"
        )
        self.collected_data['mac_address'] = mac_address if mac_address else "Unknown"
        
        # Operating System
        os_info = self._run_bash("cat /etc/os-release | grep PRETTY_NAME | cut -d'\"' -f2")
        if not os_info:
            os_info = self._run_bash("lsb_release -d | cut -f2")
        self.collected_data['operating_system'] = os_info if os_info else "Linux (Unknown Distribution)"
        
        # OS Install Date (filesystem creation time)
        install_timestamp = self._run_bash("stat -c '%W' / 2>/dev/null")
        if install_timestamp and install_timestamp != "0":
            try:
                install_date = datetime.datetime.fromtimestamp(int(install_timestamp))
                self.collected_data['os_install_date'] = install_date.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError):
                self.collected_data['os_install_date'] = "Unknown"
        else:
            self.collected_data['os_install_date'] = "Unknown"
        
        # BIOS Release Date
        bios_date = self._run_bash("cat /sys/class/dmi/id/bios_date 2>/dev/null")
        self.collected_data['bios_release_date'] = bios_date if bios_date else "Unknown"
        
        # Chassis type detection
        chassis_type = self._run_bash("cat /sys/class/dmi/id/chassis_type 2>/dev/null")
        self.collected_data['chassis_type'] = chassis_type if chassis_type else "Unknown"
        
        # Current User
        username = self._run_bash("whoami")
        self.collected_data['username'] = username if username else "Unknown"
        
        # Optional fields
        self._collect_optional_linux_fields()
    
    def _collect_optional_linux_fields(self) -> None:
        """Collect optional Linux fields if enabled in config"""
        optional_fields = self.config.get('custom_fields', {}).get('optional_fields', {})
        
        # CPU Temperature
        if optional_fields.get('cpu_temperature', {}).get('enabled', False):
            temp = self._run_bash(
                "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.1f\", $1/1000}'"
            )
            if temp:
                self.collected_data['cpu_temperature'] = f"{temp}°C"
            else:
                self.collected_data['cpu_temperature'] = "Not Available"
        
        # System Uptime
        if optional_fields.get('system_uptime', {}).get('enabled', False):
            uptime = self._run_bash("awk '{printf \"%.2f\", $1/86400}' /proc/uptime")
            self.collected_data['system_uptime'] = f"{uptime} days" if uptime else "Unknown"
        
        # Screen Size
        if optional_fields.get('screen_size', {}).get('enabled', False):
            # Try to get screen size from xrandr if available
            screen = self._run_bash(
                "xrandr 2>/dev/null | grep ' connected' | head -1 | awk '{print $3}' | cut -d'+' -f1"
            )
            self.collected_data['screen_size'] = screen if screen else "Unknown"
    
    def _collect_generic_data(self) -> None:
        """Collect minimal data for unsupported operating systems"""
        self.collected_data['hostname'] = platform.node()
        self.collected_data['manufacturer'] = "Generic"
        self.collected_data['model'] = "Generic Model"
        self.collected_data['serial_number'] = "Unknown"
        self.collected_data['operating_system'] = f"{self.os_type} {platform.release()}"
        self.collected_data['processor'] = platform.processor() or "Unknown"
        self.collected_data['username'] = "Unknown"
    
    def _map_to_custom_fields(self) -> None:
        """
        Map collected system data to Snipe-IT custom field format.
        Uses display names from config or defaults to standard names.
        """
        # Standard field mapping (internal name -> display name)
        field_mapping = {
            'operating_system': 'Operating System',
            'os_install_date': 'OS Install Date',
            'memory_total_gb': 'Memory / RAM',
            'ram_usage': 'RAM Usage',
            'bios_release_date': 'BIOS Release Date',
            'ip_address': 'IP Address',
            'processor': 'Processor / CPU',
            'username': 'Windows Username',
            'mac_address': 'MAC Address',
            'total_storage_gb': 'Total Storage',
            'storage_information': 'Storage Information',
            'disk_space_used': 'Disk Space Used',
            'agent_version': 'Agent Version',
            'cpu_temperature': 'CPU Temperature',
            'system_uptime': 'System Uptime (Days)',
            'screen_size': 'Screen Size'
        }
        
        # Map collected data to custom fields
        for internal_key, display_name in field_mapping.items():
            if internal_key in self.collected_data:
                value = self.collected_data[internal_key]
                if value and str(value).strip() and str(value).strip().lower() != 'unknown':
                    self.custom_fields[display_name] = str(value).strip()
    
    def _run_powershell(self, command: str) -> Optional[str]:
        """
        Execute a PowerShell command and return the output
        
        Args:
            command: PowerShell command to execute
            
        Returns:
            Command output as string or None if command fails
        """
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command', command],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
            )
            
            if result.returncode == 0 and result.stdout:
                output = result.stdout.strip()
                return output if output else None
            return None
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            return None
    
    def _run_bash(self, command: str) -> Optional[str]:
        """
        Execute a bash command and return the output
        
        Args:
            command: Bash command to execute
            
        Returns:
            Command output as string or None if command fails
        """
        try:
            result = subprocess.run(
                ['bash', '-c', command],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout:
                output = result.stdout.strip()
                return output if output else None
            return None
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            return None
    
    def get_asset_type(self) -> str:
        """
        Determine the asset type based on chassis type
        
        Returns:
            "laptop", "desktop", or "server"
        """
        chassis_type_str = str(self.collected_data.get('chassis_type', 'Unknown'))
        
        # Try to convert to integer
        try:
            chassis_type = int(chassis_type_str)
        except (ValueError, TypeError):
            # If can't convert, default to desktop
            return "desktop"
        
        # Laptop chassis types: 8=Portable, 9=Laptop, 10=Notebook, 11=Hand Held,
        #                       14=Sub Notebook, 30=Tablet, 31=Convertible, 32=Detachable
        laptop_types = [8, 9, 10, 11, 14, 30, 31, 32]
        
        # Server chassis types: 17=Main Server Chassis, 23=Rack Mount Chassis,
        #                       24=Sealed-case PC, 25=Multi-system chassis
        server_types = [17, 23, 24, 25]
        
        if chassis_type in laptop_types:
            return "laptop"
        elif chassis_type in server_types:
            return "server"
        else:
            # Desktop types: 3=Desktop, 4=Low Profile Desktop, 5=Pizza Box, 
            #                6=Mini Tower, 7=Tower, 13=All in One, etc.
            return "desktop"
    
    def is_laptop(self) -> bool:
        """
        Legacy method for backward compatibility
        
        Returns:
            True if laptop, False otherwise
        """
        return self.get_asset_type() == "laptop"
    
    def get_asset_data(self) -> Dict[str, Any]:
        """
        Get data formatted for Snipe-IT asset creation/update
        
        Returns:
            Dictionary with asset data including hostname, manufacturer, model, serial, and custom fields
        """
        return {
            'hostname': self.collected_data.get('hostname', 'Unknown'),
            'manufacturer': self.collected_data.get('manufacturer', 'Generic'),
            'model': self.collected_data.get('model', 'Generic Model'),
            'serial_number': self.collected_data.get('serial_number', 'Unknown'),
            'custom_fields': self.custom_fields,
            'asset_type': self.get_asset_type(),  # "laptop", "desktop", or "server"
            'is_laptop': self.is_laptop()  # Keep for backward compatibility
        }
    
    def print_summary(self) -> None:
        """Print a formatted summary of collected data"""
        print("\n" + "="*60)
        print(f"SYSTEM DATA COLLECTION SUMMARY - {self.os_type}")
        print("="*60)
        
        print("\nCore System Information:")
        print(f"  Hostname: {self.collected_data.get('hostname', 'N/A')}")
        print(f"  Manufacturer: {self.collected_data.get('manufacturer', 'N/A')}")
        print(f"  Model: {self.collected_data.get('model', 'N/A')}")
        print(f"  Serial Number: {self.collected_data.get('serial_number', 'N/A')}")
        
        print("\nHardware Information:")
        print(f"  Processor: {self.collected_data.get('processor', 'N/A')}")
        print(f"  Memory: {self.collected_data.get('memory_total_gb', 'N/A')}")
        print(f"  RAM Usage: {self.collected_data.get('ram_usage', 'N/A')}")
        print(f"  Storage: {self.collected_data.get('total_storage_gb', 'N/A')}")
        print(f"  Disk Usage: {self.collected_data.get('disk_space_used', 'N/A')}")
        
        print("\nNetwork Information:")
        print(f"  IP Address: {self.collected_data.get('ip_address', 'N/A')}")
        print(f"  MAC Address: {self.collected_data.get('mac_address', 'N/A')}")
        
        print("\nSoftware Information:")
        print(f"  Operating System: {self.collected_data.get('operating_system', 'N/A')}")
        print(f"  Current User: {self.collected_data.get('username', 'N/A')}")
        print(f"  Agent Version: {self.collected_data.get('agent_version', 'N/A')}")
        
        print(f"\nCustom Fields Prepared: {len(self.custom_fields)}")
        print("="*60 + "\n")


if __name__ == "__main__":
    # Test the collector
    print("Testing System Data Collector...")
    print(f"Detected OS: {platform.system()}")
    
    collector = SystemDataCollector()
    result = collector.collect_all()
    
    collector.print_summary()
    
    print("\nCustom Fields for Snipe-IT:")
    for field_name, value in result['custom_fields'].items():
        print(f"  {field_name}: {value}")
