#!/usr/bin/env python3
"""
Unified System Data Collector for SniperIT Agent
OS-aware data collection with standardized output format
"""

import platform
import subprocess
import os
import sys
import json
sys.path.append('..')
from utils.common import run_command, format_number, resolve_path
import config.constants as c

class SystemDataCollector:
    def __init__(self):
        self.os_type = platform.system()
        self.collected_data = {}
        self.custom_fields_data = {}
        self.field_config = self._load_field_config()
        
    def collect_all_data(self):
        """Main method to collect all system data based on OS"""
        print(f"🖥️  Operating System Detected: {self.os_type}")
        
        if self.os_type == "Windows":
            self._collect_windows_data()
        elif self.os_type == "Linux":
            self._collect_linux_data()
        else:
            self._collect_generic_data()
            
        # Always add Agent version
        self.collected_data['agent_version'] = c.VERSION
        self.custom_fields_data['Agent Version'] = c.VERSION
        
        # Validate and display collected data
        self._validate_and_display()
        
        return {
            'system_data': self.collected_data,
            'custom_fields': self.custom_fields_data,
            'os_type': self.os_type
        }
    
    def _collect_windows_data(self):
        """Collect data for Windows systems"""
        print("🪟 Collecting Windows system data...")
        
        # Basic system information
        self.collected_data['hostname'] = run_command("$env:COMPUTERNAME")
        self.collected_data['manufacturer'] = run_command("(Get-WmiObject -Class Win32_ComputerSystem).Manufacturer")
        self.collected_data['model'] = run_command("(Get-WmiObject -Class Win32_ComputerSystem).Model")
        self.collected_data['serial_number'] = run_command("(Get-WmiObject -Class Win32_BIOS).SerialNumber")
        
        # Hardware information
        self.collected_data['processor'] = run_command("(Get-WmiObject -Class Win32_Processor).Name")
        memory_total = format_number(run_command("[Math]::Round((Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)"))
        memory_used = format_number(run_command("[Math]::Round(((Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory - (Get-WmiObject Win32_OperatingSystem).FreePhysicalMemory * 1024) / 1GB, 2)"))
        self.collected_data['memory_total_gb'] = f"{memory_total} GB"
        self.collected_data['memory_used_gb'] = f"{memory_used} GB"
        
        # Storage information
        storage_total = format_number(run_command("$total=0; (Get-WmiObject -Class Win32_DiskDrive | Where-Object { $_.MediaType -eq 'Fixed hard disk media' }).Size | foreach-object { $total=$total+$_/1gb }; [Math]::Round($total, 2)"))
        storage_used = format_number(run_command("[Math]::Round(((Get-WmiObject Win32_LogicalDisk -Filter \"DeviceID='C:'\").Size - (Get-WmiObject Win32_LogicalDisk -Filter \"DeviceID='C:'\").FreeSpace) / 1GB, 2)"))
        self.collected_data['total_storage_gb'] = f"{storage_total} GB"
        self.collected_data['disk_used_gb'] = f"{storage_used} GB"
        self.collected_data['storage_info'] = run_command("(Get-WmiObject -Class Win32_DiskDrive | Where-Object { $_.MediaType -eq 'Fixed hard disk media' }) | ForEach-Object{ echo \"$($_.MediaType) - $($_.Model) - $($_.SerialNumber) - $([Math]::Round($_.Size/1gb,2)) GB\" }")
        
        # Network information
        self.collected_data['ip_address'] = run_command("(Test-Connection (hostname) -count 1).IPv4Address.IPAddressToString")
        self.collected_data['mac_address'] = run_command("(Get-WmiObject Win32_NetworkAdapterConfiguration | Where-Object {$_.IPEnabled -eq $true} | Select-Object -First 1).MACAddress")
        
        # Software information
        self.collected_data['os_version'] = run_command("(Get-WmiObject Win32_OperatingSystem).Caption")
        
        # OS install date - convert timestamp to readable format
        install_timestamp = run_command("[math]::Round((New-TimeSpan -Start (Get-Date '1970-01-01') -End (Get-CimInstance Win32_OperatingSystem).InstallDate).TotalSeconds)")
        self.collected_data['os_install_date'] = self._format_timestamp(install_timestamp)
        
        bios_timestamp = run_command("[math]::Round((New-TimeSpan -Start (Get-Date '1970-01-01') -End (Get-CimInstance Win32_BIOS).ReleaseDate).TotalSeconds)")
        self.collected_data['bios_date'] = self._format_timestamp(bios_timestamp)
        self.collected_data['current_user'] = run_command("[System.Security.Principal.WindowsIdentity]::GetCurrent().Name")
        
        # Collect optional fields if enabled
        self._collect_optional_fields()
        
        # Map to Snipe-IT custom field names
        self._map_to_custom_fields()
    
    def _collect_linux_data(self):
        """Collect data for Linux systems"""
        print("🐧 Collecting Linux system data...")
        
        # Basic system information
        self.collected_data['hostname'] = run_command("hostname")
        self.collected_data['manufacturer'] = run_command("cat /sys/class/dmi/id/sys_vendor 2>/dev/null || echo 'Generic Manufacturer'")
        self.collected_data['model'] = run_command("cat /sys/class/dmi/id/product_name 2>/dev/null || cat /sys/class/dmi/id/product_version 2>/dev/null || echo 'Generic Model'")
        
        # Enhanced serial number detection
        self.collected_data['serial_number'] = self._get_linux_serial()
        
        # Hardware information
        self.collected_data['processor'] = run_command("cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d: -f2 | sed 's/^ *//'")
        memory_total = format_number(run_command("free -g | awk 'NR==2{printf \"%.1f\", $2}'"))
        memory_used = format_number(run_command("free -g | awk 'NR==2{printf \"%.1f\", $3}'"))
        self.collected_data['memory_total_gb'] = f"{memory_total} GB"
        self.collected_data['memory_used_gb'] = f"{memory_used} GB"
        
        # Storage information
        storage_total = format_number(run_command("df -BG / | tail -1 | awk '{print $2}' | sed 's/G//'"))
        storage_used = format_number(run_command("df -BG / | tail -1 | awk '{print $3}' | sed 's/G//'"))
        self.collected_data['total_storage_gb'] = f"{storage_total} GB"
        self.collected_data['disk_used_gb'] = f"{storage_used} GB"
        self.collected_data['storage_info'] = run_command("lsblk -d -o NAME,MODEL,SIZE,VENDOR | grep -v 'NAME' | head -3 | tr '\n' '; '")
        
        # Network information
        self.collected_data['ip_address'] = run_command("hostname -I | awk '{print $1}'")
        self.collected_data['mac_address'] = run_command("cat /sys/class/net/$(ls /sys/class/net | grep -v lo | head -1)/address")
        
        # Software information
        self.collected_data['os_version'] = run_command("lsb_release -d | cut -f2")
        
        # OS install date - convert timestamp to readable format
        install_timestamp = run_command("stat -c '%W' /etc/os-release")
        self.collected_data['os_install_date'] = self._format_timestamp(install_timestamp)
        self.collected_data['bios_date'] = run_command("cat /sys/class/dmi/id/bios_date 2>/dev/null || echo 'Unknown'")
        self.collected_data['current_user'] = run_command("whoami")
        
        # Collect optional fields if enabled
        self._collect_optional_fields()
        
        # Map to Snipe-IT custom field names
        self._map_to_custom_fields()
    
    def _collect_generic_data(self):
        """Collect basic data for unsupported systems"""
        print("🔧 Collecting generic system data...")
        
        self.collected_data['hostname'] = run_command("hostname")
        self.collected_data['manufacturer'] = "Generic Manufacturer"
        self.collected_data['model'] = "Generic Model"
        self.collected_data['serial_number'] = "Unknown"
        self.collected_data['current_user'] = run_command("whoami")
        self.collected_data['os_version'] = f"{platform.system()} {platform.release()}"
        
        # Collect optional fields if enabled
        self._collect_optional_fields()
        
        # Map to Snipe-IT custom field names
        self._map_to_custom_fields()
    
    def _get_linux_serial(self):
        """Get serial number for Linux with multiple fallbacks"""
        serial_commands = [
            "cat /sys/class/dmi/id/product_serial 2>/dev/null",
            "cat /sys/class/dmi/id/board_serial 2>/dev/null", 
            "cat /sys/class/dmi/id/chassis_serial 2>/dev/null",
            "sudo dmidecode -s system-serial-number 2>/dev/null",
            "sudo dmidecode -s baseboard-serial-number 2>/dev/null"
        ]
        
        for cmd in serial_commands:
            result = run_command(cmd)
            if result and result.strip() and result.strip().lower() not in ['unknown', 'not specified', 'to be filled by o.e.m.', '0', '', 'none', 'n/a']:
                return result.strip()
        
        # Generate consistent serial for systems without hardware serial
        hostname = self.collected_data.get('hostname', 'unknown')
        mac = run_command("cat /sys/class/net/$(ls /sys/class/net | grep -v lo | head -1)/address 2>/dev/null || echo ''")
        if mac:
            return f"LINUX-{hostname}-{mac.replace(':', '')[:8].upper()}"
        
        return "Unknown"
    
    def _format_timestamp(self, timestamp_str):
        """Convert Unix timestamp to readable date format"""
        try:
            import datetime
            if timestamp_str and timestamp_str.strip() and timestamp_str.strip() not in ['0', 'Unknown', '']:
                timestamp = int(float(timestamp_str))
                if timestamp > 0:  # Valid timestamp
                    dt = datetime.datetime.fromtimestamp(timestamp)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
            return "Unknown"
        except (ValueError, OSError) as e:
            print(f"   ⚠️  Could not format timestamp '{timestamp_str}': {e}")
            return "Unknown"
    
    def _load_field_config(self):
        """Load field configuration from custom_fields.json"""
        try:
            config_path = resolve_path('custom_fields.json')
            if not os.path.exists(config_path):
                config_path = resolve_path('config/custom_fields.json')
            
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get('field_configuration', {})
        except Exception as e:
            print(f"⚠️  Warning: Could not load field configuration: {e}")
            return {}
    
    def _collect_optional_fields(self):
        """Collect optional fields based on configuration and OS"""
        optional_fields = self.field_config.get('optional_fields', {})
        
        for field_key, field_info in optional_fields.items():
            if not field_info.get('enabled', False):
                continue
                
            try:
                if field_key == 'cpu_temperature':
                    self.collected_data['cpu_temperature'] = self._get_cpu_temperature()
                elif field_key == 'system_uptime':
                    self.collected_data['system_uptime'] = self._get_system_uptime()
            except Exception as e:
                print(f"⚠️  Warning: Could not collect {field_key}: {e}")
    
    def _get_cpu_temperature(self):
        """Get CPU temperature if available"""
        if self.os_type == "Windows":
            # Most Windows systems don't expose temperature via WMI reliably
            return "Not Available"
        elif self.os_type == "Linux":
            # Try common thermal sensors on Linux
            temp_commands = [
                "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{print $1/1000}'",
                "sensors | grep 'Core 0' | awk '{print $3}' | cut -d'+' -f2 | cut -d'°' -f1"
            ]
            for cmd in temp_commands:
                result = run_command(cmd)
                if result and result.strip() and result.strip() != "":
                    try:
                        temp = float(result.strip())
                        return f"{temp:.1f}°C"
                    except ValueError:
                        continue
        return "Not Available"
    
    def _get_system_uptime(self):
        """Get system uptime in days"""
        try:
            if self.os_type == "Windows":
                uptime_seconds = run_command("(Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime | ForEach-Object { $_.TotalDays }")
                if uptime_seconds:
                    return f"{float(uptime_seconds):.1f} days"
            elif self.os_type == "Linux":
                uptime_seconds = run_command("awk '{print $1/86400}' /proc/uptime")
                if uptime_seconds:
                    return f"{float(uptime_seconds):.1f} days"
        except Exception:
            pass
        return "Unknown"
    
    def _map_to_custom_fields(self):
        """Map collected data to Snipe-IT custom field format"""
        # Mapping from internal field names to Snipe-IT display names
        field_mapping = {
            'os_version': 'Operating System',
            'os_install_date': 'OS Install Date',
            'memory_total_gb': 'Memory / RAM',
            'memory_used_gb': 'RAM Usage',
            'bios_date': 'BIOS Release Date',
            'ip_address': 'IP Address',
            'processor': 'Processor / CPU',
            'current_user': 'Windows Username',  # Keep this name for compatibility
            'total_storage_gb': 'Total Storage',
            'disk_used_gb': 'Disk Space Used',
            'storage_info': 'Storage Information',
            'mac_address': 'MAC Address',
            'agent_version': 'Agent Version',
            'cpu_temperature': 'CPU Temperature',
            'system_uptime': 'System Uptime (Days)'
        }
        
        for internal_name, display_name in field_mapping.items():
            if internal_name in self.collected_data:
                value = self.collected_data[internal_name]
                if value and str(value).strip():
                    self.custom_fields_data[display_name] = str(value).strip()
    
    def _validate_and_display(self):
        """Validate and display collected data"""
        print("\n📊 COLLECTED SYSTEM DATA:")
        print("=" * 50)
        
        # Core system info
        print("\n🖥️  CORE SYSTEM INFO:")
        print(f"   OS Type: {self.os_type}")
        print(f"   Hostname: {self.collected_data.get('hostname', 'N/A')}")
        print(f"   Manufacturer: {self.collected_data.get('manufacturer', 'N/A')}")
        print(f"   Model: {self.collected_data.get('model', 'N/A')}")
        print(f"   Serial Number: {self.collected_data.get('serial_number', 'N/A')}")
        
        # Hardware info
        print("\n💻 HARDWARE INFORMATION:")
        print(f"   Processor: {self.collected_data.get('processor', 'N/A')}")
        print(f"   Memory Total: {self.collected_data.get('memory_total_gb', 'N/A')}")
        print(f"   Memory Used: {self.collected_data.get('memory_used_gb', 'N/A')}")
        print(f"   Total Storage: {self.collected_data.get('total_storage_gb', 'N/A')}")
        print(f"   Disk Used: {self.collected_data.get('disk_used_gb', 'N/A')}")
        
        # Network info
        print("\n🌐 NETWORK INFORMATION:")
        print(f"   IP Address: {self.collected_data.get('ip_address', 'N/A')}")
        print(f"   MAC Address: {self.collected_data.get('mac_address', 'N/A')}")
        
        # Software info
        print("\n🔧 SOFTWARE INFORMATION:")
        print(f"   OS Version: {self.collected_data.get('os_version', 'N/A')}")
        print(f"   Current User: {self.collected_data.get('current_user', 'N/A')}")
        print(f"   Agent Version: {self.collected_data.get('agent_version', 'N/A')}")
        
        # Custom fields summary
        print(f"\n📋 CUSTOM FIELDS PREPARED ({len(self.custom_fields_data)}):")
        for field_name, value in self.custom_fields_data.items():
            print(f"   ✅ {field_name}: {value}")
        
        print("\n" + "=" * 50)
    
    def get_asset_data(self):
        """Get data formatted for asset creation/update"""
        return {
            'hostname': self.collected_data.get('hostname', 'Unknown'),
            'manufacturer': self.collected_data.get('manufacturer', 'Generic Manufacturer'),
            'model': self.collected_data.get('model', 'Generic Model'),
            'serial_number': self.collected_data.get('serial_number', 'Unknown'),
            'custom_fields': self.custom_fields_data
        }

if __name__ == "__main__":
    # Test the collector
    collector = SystemDataCollector()
    result = collector.collect_all_data()
    print(f"\n🎯 Collection completed for {result['os_type']}")