"""
Sniper-IT Agent - Monitor Data Collector
Collects monitor/display information from connected screens
Supports Windows and Linux platforms
"""

import platform
import subprocess
import json
import re
from typing import Dict, Any, List, Optional

from utils.exceptions import DataCollectionError


class MonitorCollector:
    """
    Collects monitor/display information using non-admin commands.
    Detects manufacturer, model, serial, resolution, and connection details.
    
    IMPORTANT: This collector ONLY returns EXTERNAL monitors. 
    Internal/integrated laptop displays are automatically filtered out.
    
    Detection method (Windows):
    - Uses Microsoft D3DKMDT_VIDEO_OUTPUT_TECHNOLOGY enumeration via WMI
    - Queries WmiMonitorConnectionParams for VideoOutputTechnology value
    - 100% reliable: Official Microsoft hardware-level detection
    - Internal values: 6 (LVDS), 11 (eDP), 13 (UDI Embedded), 0x80000000 (Internal)
    - External values: 0 (VGA), 4 (DVI), 5 (HDMI), 10 (DisplayPort), etc.
    
    Detection method (Linux):
    - Filters display names starting with eDP, LVDS, DSI, PANEL
    
    Reference: https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/d3dkmdt/ne-d3dkmdt-_d3dkmdt_video_output_technology
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the monitor collector
        
        Args:
            config: Optional configuration dictionary
        """
        self.os_type = platform.system()
        self.config = config or {}
        
    def collect_monitors(self) -> List[Dict[str, Any]]:
        """
        Collect all connected monitors
        
        Returns:
            List of monitor dictionaries, each containing:
            - Core asset fields: manufacturer, model, serial_number
            - Custom fields: resolution, native_resolution, refresh_rate, etc.
            
        Raises:
            DataCollectionError: If collection fails critically
        """
        try:
            if self.os_type == "Windows":
                return self._collect_windows_monitors()
            elif self.os_type == "Linux":
                return self._collect_linux_monitors()
            else:
                return []
        except Exception as e:
            raise DataCollectionError(f"Failed to collect monitor data: {e}")
    
    def _collect_windows_monitors(self) -> List[Dict[str, Any]]:
        """
        Collect Windows monitors using extended EDID/WMI/GDI data
        Uses non-admin PowerShell commands
        """
        # Complete PowerShell script with P/Invoke for detailed monitor info
        powershell_script = r"""
# P/Invoke for display settings and refresh rate
$DisplayPInvoke = @"
using System;
using System.Runtime.InteropServices;
using System.Text;

[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
public struct DISPLAY_DEVICE {
    public int cb;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
    public string DeviceName;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
    public string DeviceString;
    public int StateFlags;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
    public string DeviceID;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
    public string DeviceKey;
}

[StructLayout(LayoutKind.Sequential)]
public struct DEVMODE {
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
    public string dmDeviceName;
    public short dmSpecVersion;
    public short dmDriverVersion;
    public short dmSize;
    public short dmDriverExtra;
    public int dmFields;
    public int dmPositionX;
    public int dmPositionY;
    public int dmDisplayOrientation;
    public int dmDisplayFixedOutput;
    public short dmColor;
    public short dmDuplex;
    public short dmYResolution;
    public short dmTTOption;
    public short dmCollate;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
    public string dmFormName;
    public short dmLogPixels;
    public int dmBitsPerPel;
    public int dmPelsWidth;
    public int dmPelsHeight;
    public int dmDisplayFlags;
    public int dmDisplayFrequency;
}

public class DisplayAPI {
    [DllImport("user32.dll")]
    public static extern bool EnumDisplayDevices(string lpDevice, int iDevNum, ref DISPLAY_DEVICE lpDisplayDevice, int dwFlags);
    
    [DllImport("user32.dll")]
    public static extern bool EnumDisplaySettings(string deviceName, int modeNum, ref DEVMODE devMode);
    
    public const int ENUM_CURRENT_SETTINGS = -1;
    public const int DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x1;
}
"@

try {
    Add-Type -TypeDefinition $DisplayPInvoke -ErrorAction SilentlyContinue
} catch {
    # Type might already be loaded
}

function Get-RefreshRate {
    param([string]$DeviceName)
    try {
        $devMode = New-Object DEVMODE
        $devMode.dmSize = [System.Runtime.InteropServices.Marshal]::SizeOf($devMode)
        if ([DisplayAPI]::EnumDisplaySettings($DeviceName, [DisplayAPI]::ENUM_CURRENT_SETTINGS, [ref]$devMode)) {
            return $devMode.dmDisplayFrequency
        }
    } catch {}
    return $null
}

function Get-Normalized {
    param([int[]]$In)
    if (-not $In) { return "" }
    return ($In | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ }) -join ""
}

function Get-VideoOutputTechnology {
    param([string]$InstanceName)
    
    # Query WMI for VideoOutputTechnology (most reliable method)
    # Based on Microsoft D3DKMDT_VIDEO_OUTPUT_TECHNOLOGY enumeration
    try {
        $Connection = Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorConnectionParams | 
            Where-Object { $_.InstanceName -eq $InstanceName }
        
        if ($Connection) {
            return $Connection.VideoOutputTechnology
        }
    } catch {
        # WMI query failed
    }
    
    return $null
}

function Test-IsInternalDisplay {
    param($VideoOutputTech)  # Don't type-cast - let PowerShell handle it dynamically
    
    # Based on Microsoft D3DKMDT_VIDEO_OUTPUT_TECHNOLOGY official documentation
    # https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/d3dkmdt/ne-d3dkmdt-_d3dkmdt_video_output_technology
    
    # Internal display values:
    # 6  = D3DKMDT_VOT_LVDS (Legacy laptop displays)
    # 11 = D3DKMDT_VOT_DISPLAYPORT_EMBEDDED (Modern laptop displays - eDP)
    # 13 = D3DKMDT_VOT_UDI_EMBEDDED
    # 2147483648 (0x80000000) = D3DKMDT_VOT_INTERNAL (Explicit internal flag)
    
    # Check each value explicitly to handle large integers
    if ($VideoOutputTech -eq 6) { return $true }
    if ($VideoOutputTech -eq 11) { return $true }
    if ($VideoOutputTech -eq 13) { return $true }
    if ($VideoOutputTech -eq 2147483648) { return $true }
    
    return $false
}

# Main collection logic
$ComputerName = $env:COMPUTERNAME
$Monitors = @()

try {
    # Get screens for resolution/primary
    Add-Type -AssemblyName System.Windows.Forms
    $Screens = [System.Windows.Forms.Screen]::AllScreens
    
    # Get WMI monitors for EDID details
    $WmiMonitors = Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID | Where-Object { $_.Active -eq $true }
    
    # Get display devices for connection/refresh
    $DeviceIndex = 0
    $DisplayDevice = New-Object DISPLAY_DEVICE
    $DisplayDevice.cb = [System.Runtime.InteropServices.Marshal]::SizeOf($DisplayDevice)
    $DeviceList = @()
    
    while ([DisplayAPI]::EnumDisplayDevices($null, $DeviceIndex, [ref]$DisplayDevice, 0)) {
        if ($DisplayDevice.StateFlags -band [DisplayAPI]::DISPLAY_DEVICE_ATTACHED_TO_DESKTOP) {
            $DeviceList += [PSCustomObject]@{
                DeviceName = $DisplayDevice.DeviceName
                DeviceID = $DisplayDevice.DeviceID
                DeviceString = $DisplayDevice.DeviceString
            }
        }
        $DeviceIndex++
    }
    
    # Match and build monitor list
    $maxCount = [Math]::Max($Screens.Count, $WmiMonitors.Count)
    for ($i = 0; $i -lt $maxCount; $i++) {
        $Screen = if ($i -lt $Screens.Count) { $Screens[$i] } else { $null }
        $Wmi = if ($i -lt $WmiMonitors.Count) { $WmiMonitors[$i] } else { $null }
        $Dev = if ($i -lt $DeviceList.Count) { $DeviceList[$i] } else { $null }
        
        # Extract serial number
        $Serial = if ($Wmi) { Get-Normalized $Wmi.SerialNumberID } else { "" }
        if ([string]::IsNullOrWhiteSpace($Serial) -or $Serial -eq "Default_Monitor") {
            $Serial = ""
        }
        
        # Extract manufacturer
        $Manufacturer = if ($Wmi) { Get-Normalized $Wmi.ManufacturerName } else { "Unknown" }
        if ([string]::IsNullOrWhiteSpace($Manufacturer)) { $Manufacturer = "Unknown" }
        
        # Extract model
        $Model = if ($Wmi) { Get-Normalized $Wmi.UserFriendlyName } else { "Unknown Monitor" }
        if ([string]::IsNullOrWhiteSpace($Model)) { $Model = "Unknown Monitor" }
        
        # Current resolution
        $Resolution = if ($Screen) { "$($Screen.Bounds.Width)x$($Screen.Bounds.Height)" } else { "N/A" }
        
        # Native resolution (simplified - using current as fallback)
        $NativeResolution = $Resolution
        
        # Primary display flag
        $IsPrimary = if ($Screen) { if ($Screen.Primary) { "Yes" } else { "No" } } else { "No" }
        
        # Get VideoOutputTechnology (most reliable method for internal/external detection)
        $VideoOutputTech = $null
        $ConnectionLabel = "Unknown"
        if ($Wmi -and $Wmi.InstanceName) {
            $VideoOutputTech = Get-VideoOutputTechnology -InstanceName $Wmi.InstanceName
            
            # Map VideoOutputTech to connection label
            # Based on Microsoft D3DKMDT_VIDEO_OUTPUT_TECHNOLOGY
            if ($VideoOutputTech -ne $null) {
                switch ($VideoOutputTech) {
                    -2 { $ConnectionLabel = "Uninitialized" }
                    -1 { $ConnectionLabel = "Other" }
                    0 { $ConnectionLabel = "VGA" }
                    1 { $ConnectionLabel = "S-Video" }
                    2 { $ConnectionLabel = "Composite" }
                    3 { $ConnectionLabel = "Component" }
                    4 { $ConnectionLabel = "DVI" }
                    5 { $ConnectionLabel = "HDMI" }
                    6 { $ConnectionLabel = "LVDS (Internal)" }
                    8 { $ConnectionLabel = "D-JPN" }
                    9 { $ConnectionLabel = "SDI" }
                    10 { $ConnectionLabel = "DisplayPort" }
                    11 { $ConnectionLabel = "eDP (Internal)" }
                    12 { $ConnectionLabel = "UDI External" }
                    13 { $ConnectionLabel = "UDI Embedded (Internal)" }
                    14 { $ConnectionLabel = "SDTV Dongle" }
                    15 { $ConnectionLabel = "Miracast" }
                    16 { $ConnectionLabel = "Indirect Wired" }
                    2147483648 { $ConnectionLabel = "Built-in (Internal)" }
                    default { $ConnectionLabel = "Unknown (0x{0:X})" -f $VideoOutputTech }
                }
            }
        }
        
        # Check if this is an internal/embedded display (laptop screen)
        $IsInternal = if ($VideoOutputTech -ne $null) {
            Test-IsInternalDisplay -VideoOutputTech $VideoOutputTech
        } else {
            $false  # If we can't determine, assume external (safer)
        }
        
        # Refresh rate
        $RefreshRate = if ($Dev) {
            $rr = Get-RefreshRate -DeviceName $Dev.DeviceName
            if ($rr -and $rr -gt 0) { "$rr Hz" } else { "N/A" }
        } else { "N/A" }
        
        # Bit depth from DEVMODE
        $BitDepth = if ($Dev) {
            $devMode = New-Object DEVMODE
            $devMode.dmSize = [System.Runtime.InteropServices.Marshal]::SizeOf($devMode)
            if ([DisplayAPI]::EnumDisplaySettings($Dev.DeviceName, [DisplayAPI]::ENUM_CURRENT_SETTINGS, [ref]$devMode)) {
                "$($devMode.dmBitsPerPel)-bit"
            } else { "N/A" }
        } else { "N/A" }
        
        # Only add external monitors (skip internal laptop displays)
        if (-not $IsInternal) {
            $Monitors += [PSCustomObject]@{
                'connected_to_laptop' = $ComputerName
                'manufacturer'        = $Manufacturer
                'model'               = $Model
                'serial_number'       = $Serial
                'resolution'          = $Resolution
                'native_resolution'   = $NativeResolution
                'primary_display'     = $IsPrimary
                'refresh_rate'        = $RefreshRate
                'connection_interface'= $ConnectionLabel
                'bit_depth'           = $BitDepth
                'video_output_tech'   = $VideoOutputTech
            }
        }
    }
    
} catch {
    # If collection fails, return empty array with error info
    Write-Error "Collection failed: $_" 
    $Monitors = @()
}

# Always output JSON, even if empty
if ($Monitors.Count -eq 0) {
    "[]"
} else {
    $Monitors | ConvertTo-Json -Depth 3
}
"""
        
        # Execute PowerShell script
        result = self._run_powershell(powershell_script)
        
        if not result:
            return []
        
        # Parse JSON output
        try:
            monitors_raw = json.loads(result)
            
            # Handle single monitor (PowerShell returns object, not array)
            if isinstance(monitors_raw, dict):
                monitors_raw = [monitors_raw]
            
            # Process and normalize each monitor
            monitors = []
            for monitor in monitors_raw:
                processed = self._process_monitor_data(monitor)
                if processed:
                    monitors.append(processed)
            
            return monitors
            
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse monitor data: {e}")
            return []
    
    def _collect_linux_monitors(self) -> List[Dict[str, Any]]:
        """
        Collect Linux monitors using xrandr and sys files
        """
        monitors = []
        
        try:
            # Use xrandr for monitor detection
            result = self._run_bash("xrandr --query")
            
            if not result:
                return []
            
            # Parse xrandr output (simplified)
            current_monitor = None
            for line in result.split('\n'):
                if ' connected' in line:
                    # New monitor detected
                    if current_monitor:
                        monitors.append(current_monitor)
                    
                    parts = line.split()
                    name = parts[0]
                    is_primary = 'primary' in line
                    
                    # Skip internal laptop displays (eDP, LVDS, DSI)
                    if name.startswith(('eDP', 'LVDS', 'DSI', 'PANEL')):
                        continue
                    
                    # Extract resolution
                    resolution = "Unknown"
                    if len(parts) > 2:
                        res_match = re.search(r'(\d+x\d+)', ' '.join(parts))
                        if res_match:
                            resolution = res_match.group(1)
                    
                    current_monitor = {
                        'manufacturer': 'Unknown',
                        'model': name,
                        'serial_number': '',
                        'resolution': resolution,
                        'native_resolution': resolution,
                        'primary_display': 'Yes' if is_primary else 'No',
                        'refresh_rate': 'N/A',
                        'connection_interface': name.split('-')[0] if '-' in name else 'Unknown',
                        'bit_depth': 'N/A',
                        'connected_to_laptop': self._run_bash("hostname") or "Unknown"
                    }
            
            # Add last monitor
            if current_monitor:
                monitors.append(current_monitor)
        
        except Exception as e:
            print(f"Warning: Failed to collect Linux monitors: {e}")
        
        return monitors
    
    def _process_monitor_data(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process and normalize raw monitor data
        Handles empty serials, normalizes values, etc.
        
        Args:
            raw_data: Raw monitor data from PowerShell
            
        Returns:
            Processed monitor dictionary or None if invalid
        """
        try:
            # Extract core fields
            manufacturer = str(raw_data.get('manufacturer', 'Unknown')).strip()
            model = str(raw_data.get('model', 'Unknown Monitor')).strip()
            serial = str(raw_data.get('serial_number', '')).strip()
            
            # Normalize empty/invalid values
            if not manufacturer or manufacturer.lower() in ['unknown', 'n/a', '']:
                manufacturer = 'Unknown'
            
            if not model or model.lower() in ['unknown', 'n/a', '', 'unknown monitor']:
                model = 'Unknown Monitor'
            
            # Normalize serial number (handle empty/default cases)
            serial = self._normalize_serial_number(serial, manufacturer, model)
            
            # Build processed monitor data
            monitor = {
                # Core asset fields (for Snipe-IT asset creation)
                'manufacturer': manufacturer,
                'model': model,
                'serial_number': serial,
                
                # Custom fields
                'resolution': raw_data.get('resolution', 'N/A'),
                'native_resolution': raw_data.get('native_resolution', 'N/A'),
                'primary_display': raw_data.get('primary_display', 'No'),
                'refresh_rate': raw_data.get('refresh_rate', 'N/A'),
                'connection_interface': raw_data.get('connection_interface', 'N/A'),
                'bit_depth': raw_data.get('bit_depth', 'N/A'),
                'connected_to_laptop': raw_data.get('connected_to_laptop', 'Unknown')
            }
            
            return monitor
            
        except Exception as e:
            print(f"Warning: Failed to process monitor data: {e}")
            return None
    
    def _normalize_serial_number(self, serial: str, manufacturer: str, model: str) -> str:
        """
        Normalize serial number, handle empty/default cases
        
        For empty or invalid serials, generates a pseudo-unique identifier
        in format: N/A-MANUFACTURER-MODEL
        
        Args:
            serial: Raw serial number
            manufacturer: Monitor manufacturer
            model: Monitor model
            
        Returns:
            Normalized serial number or N/A variant
        """
        # List of known invalid/default serials
        INVALID_SERIALS = [
            '',
            'unknown',
            'n/a',
            'default_monitor',
            'default monitor',
            '0',
            '00000000',
            '0000000000000',
            'to be filled by o.e.m.',
            'not specified',
            'not available',
            '123456789',
            'aabbccddeeff',
            'empty'
        ]
        
        # Clean the serial
        clean_serial = serial.strip().lower() if serial else ''
        
        # Check if invalid
        if not clean_serial or clean_serial in INVALID_SERIALS:
            # Generate pseudo-unique identifier
            # Format: N/A-MANUFACTURER-MODEL (truncated to reasonable length)
            mfr = manufacturer[:10].replace(' ', '-')
            mdl = model[:10].replace(' ', '-')
            return f"N/A-{mfr}-{mdl}"
        
        return serial.strip()
    
    def _run_powershell(self, script: str) -> Optional[str]:
        """
        Execute a PowerShell script and return output
        
        Args:
            script: PowerShell script to execute
            
        Returns:
            Script output or None if failed
        """
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
                capture_output=True,
                text=True,
                timeout=60,  # Longer timeout for complex script
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
            )
            
            # Debug: Print errors if any
            if result.stderr:
                print(f"PowerShell stderr: {result.stderr}")
            
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()
            
            if result.returncode != 0:
                print(f"PowerShell failed with return code {result.returncode}")
            
            return None
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            return None
    
    def _run_bash(self, command: str) -> Optional[str]:
        """
        Execute a bash command and return output
        
        Args:
            command: Bash command to execute
            
        Returns:
            Command output or None if failed
        """
        try:
            result = subprocess.run(
                ['bash', '-c', command],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()
            
            return None
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            return None
    
    def print_summary(self, monitors: List[Dict[str, Any]]) -> None:
        """Print a formatted summary of collected monitors"""
        if not monitors:
            print("\nNo external monitors detected.")
            print("(Internal laptop displays are automatically excluded)")
            return
        
        print("\n" + "="*70)
        print(f"MONITOR DETECTION SUMMARY - Found {len(monitors)} monitor(s)")
        print("="*70)
        
        for i, monitor in enumerate(monitors):
            print(f"\nMonitor {i+1}:")
            print(f"  Manufacturer: {monitor['manufacturer']}")
            print(f"  Model: {monitor['model']}")
            print(f"  Serial Number: {monitor['serial_number']}")
            print(f"  Resolution: {monitor['resolution']}")
            print(f"  Refresh Rate: {monitor['refresh_rate']}")
            print(f"  Primary Display: {monitor['primary_display']}")
            print(f"  Connection: {monitor['connection_interface']}")
            print(f"  Bit Depth: {monitor['bit_depth']}")
        
        print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    # Test the monitor collector
    print("Testing Monitor Data Collector...")
    print(f"Detected OS: {platform.system()}")
    
    collector = MonitorCollector()
    monitors = collector.collect_monitors()
    
    collector.print_summary(monitors)
    
    # Show data structure
    if monitors:
        print("\nData Structure (for Snipe-IT):")
        import json
        print(json.dumps(monitors, indent=2))
