"""
Sniper-IT Agent - Sync Manager
Orchestrates the full synchronization process
"""

from typing import Dict, Any, Optional
from datetime import datetime
import urllib3

from core.api_client import SnipeITClient
from core.config_manager import ConfigManager
from collectors.system_collector import SystemDataCollector
from collectors.monitor_collector import MonitorCollector
from managers.asset_manager import AssetManager
from managers.monitor_manager import MonitorManager
from cli.formatters import (console, print_header, print_info, print_error, print_warning, spinner,
                             print_section, print_box_header, print_box_item, print_box_footer, 
                             print_step, print_subsection)
from core.constants import STATUS_OK, STATUS_ERROR, STATUS_WARNING, STATUS_INFO, APPLICATION_NAME, VERSION
from utils.exceptions import ConfigurationError, DataCollectionError, APIError
from utils.logger import get_logger


class SyncManager:
    """
    Main synchronization manager
    Orchestrates data collection and asset synchronization
    """
    
    def __init__(self, config_path: Optional[str] = None, verify_ssl: bool = True, verbosity: int = 0):
        """
        Initialize sync manager
        
        Args:
            config_path: Path to configuration file
            verify_ssl: Whether to verify SSL certificates
            verbosity: Verbosity level (0=quiet, 1=verbose, 2=debug)
        """
        self.config_path = config_path
        self.verify_ssl = verify_ssl
        self.verbosity = verbosity
        self.logger = get_logger()
        self.config = None
        self.api_client = None
        self.asset_manager = None
        self.monitor_manager = None
        
    def _load_configuration(self) -> bool:
        """
        Load and validate configuration
        
        Returns:
            True if successful, False otherwise
        """
        self.logger.quiet("")
        self.logger.verbose(f"{STATUS_INFO} Loading configuration...")
        
        try:
            config_mgr = ConfigManager(self.config_path)
            
            if not config_mgr.exists():
                print_error("Configuration file not found!")
                console.print()
                console.print("Please run the setup wizard first:")
                console.print("  Sniper-IT-Agent.exe --setup")
                console.print()
                return False
            
            self.config = config_mgr.load()
            self.logger.verbose(f"{STATUS_OK} Configuration loaded successfully")
            return True
            
        except ConfigurationError as e:
            print_error(f"Configuration error: {e}")
            return False
        except Exception as e:
            print_error(f"Failed to load configuration: {e}")
            return False
    
    def _initialize_clients(self) -> bool:
        """
        Initialize API client and managers
        
        Returns:
            True if successful, False otherwise
        """
        self.logger.verbose(f"{STATUS_INFO} Initializing API client...")
        
        try:
            # Try to load build-time secrets first (hardcoded credentials)
            base_url = None
            api_key = None
            verify_ssl = True
            
            try:
                from core.build_secrets import BUILD_SERVER_URL, BUILD_API_KEY, BUILD_IGNORE_SSL
                if BUILD_SERVER_URL and BUILD_API_KEY:
                    base_url = BUILD_SERVER_URL
                    api_key = BUILD_API_KEY
                    verify_ssl = not BUILD_IGNORE_SSL  # Invert because BUILD_IGNORE_SSL means don't verify
                    
                    # Suppress SSL warnings if BUILD_IGNORE_SSL is enabled
                    if BUILD_IGNORE_SSL:
                        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    
                    self.logger.verbose(f"{STATUS_INFO} Using build-time credentials (hardcoded)")
            except (ImportError, AttributeError):
                # No build secrets, fall back to config file
                pass
            
            # Fall back to config file if no build secrets
            if not base_url or not api_key:
                server_config = self.config.get('server', {})
                base_url = server_config.get('url', '')
                api_key = server_config.get('api_key', '')
                
                # Override SSL setting if specified via command line
                verify_ssl = self.verify_ssl and server_config.get('verify_ssl', True)
                self.logger.verbose(f"{STATUS_INFO} Using credentials from config file")
            
            # Initialize API client
            self.api_client = SnipeITClient(base_url, api_key, verify_ssl)
            
            # Test connection
            self.logger.verbose(f"{STATUS_INFO} Testing API connection...")
            connection_test = self.api_client.test_connection()
            
            if not connection_test.get('connected', False):
                print_error(f"API connection failed: {connection_test.get('error', 'Unknown error')}")
                return False
            
            self.logger.verbose(f"{STATUS_OK} Connected to Snipe-IT")
            self.logger.debug(f"    Server: {connection_test.get('server_url', 'Unknown')}")
            self.logger.debug(f"    Total Assets: {connection_test.get('total_assets', 0)}")
            
            # Initialize managers
            self.asset_manager = AssetManager(self.api_client, self.config)
            self.monitor_manager = MonitorManager(self.api_client, self.config)
            
            self.logger.verbose(f"{STATUS_OK} Managers initialized")
            return True
            
        except APIError as e:
            print_error(f"API error: {e}")
            return False
        except Exception as e:
            print_error(f"Initialization error: {e}")
            return False
    
    def _collect_system_data(self) -> Optional[Dict[str, Any]]:
        """
        Collect system data from the local computer
        
        Returns:
            System data dictionary or None if failed
        """
        try:
            # Show spinner for quiet mode, detailed output for verbose
            if self.verbosity == 0:
                with spinner("🔍 Collecting system data...", "dots"):
                    collector = SystemDataCollector(self.config)
                    system_data = collector.collect_all()
                self.logger.quiet(f"{STATUS_OK} System data collected")
            else:
                print_section("COLLECTING SYSTEM DATA")
                collector = SystemDataCollector(self.config)
                system_data = collector.collect_all()
                
                # Display collected data based on verbosity
                sd = system_data['system_data']
                hostname = sd.get('hostname', 'Unknown')
                manufacturer = sd.get('manufacturer', 'Unknown')
                model = sd.get('model', 'Unknown')
                serial = sd.get('serial_number', 'Unknown')
                os_type = system_data.get('os_type', 'Unknown')
                asset_type = system_data.get('asset_type', 'desktop').capitalize()
                
                print_box_header("Computer Information")
                print_box_item("Asset Type", asset_type)
                print_box_item("Hostname", hostname)
                print_box_item("Manufacturer", manufacturer)
                print_box_item("Model", model)
                print_box_item("Serial", serial)
                print_box_item("OS", os_type)
                
                # Show detailed information in debug mode (-vv)
                if self.verbosity >= 2:
                    chassis_type = sd.get('chassis_type', 'N/A')
                    processor = sd.get('processor', 'N/A')
                    memory = sd.get('memory_total_gb', 'N/A')
                    disk_total = sd.get('disk_space_total_gb', 'N/A')
                    disk_used = sd.get('disk_space_used_gb', 'N/A')
                    ip_address = sd.get('ip_address', 'N/A')
                    mac_address = sd.get('mac_address', 'N/A')
                    os_version = sd.get('operating_system', 'N/A')
                    os_install_date = sd.get('os_install_date', 'N/A')
                    bios_version = sd.get('bios_version', 'N/A')
                    
                    console.print(f"[dim]│ [/dim][dim]─────────────────────────────────[/dim]")
                    print_box_item("Chassis Type", chassis_type)
                    print_box_item("Processor", processor)
                    print_box_item("Memory", f"{memory} GB" if memory != 'N/A' else 'N/A')
                    print_box_item("Disk Space", f"{disk_used} GB / {disk_total} GB" if disk_total != 'N/A' else 'N/A')
                    print_box_item("IP Address", ip_address)
                    print_box_item("MAC Address", mac_address)
                    print_box_item("OS Version", os_version)
                    print_box_item("OS Install Date", os_install_date)
                    print_box_item("BIOS Version", bios_version)
                    console.print(f"[dim]│ [/dim][dim]─────────────────────────────────[/dim]")
                    
                    # Show custom fields summary
                    custom_fields = system_data.get('custom_fields', {})
                    console.print(f"[dim]│ [/dim][cyan]Custom Fields:[/cyan] {len(custom_fields)} collected")
                    for field_name, value in custom_fields.items():
                        # Truncate long values for cleaner display
                        display_value = str(value)[:50] + '...' if len(str(value)) > 50 else str(value)
                        console.print(f"[dim]│   [/dim][dim]• {field_name}:[/dim] {display_value}")
                else:
                    console.print(f"[dim]│ [/dim][cyan]Custom Fields:[/cyan] {len(system_data['custom_fields'])} collected")
                
                print_box_footer()
            
            return system_data
            
        except DataCollectionError as e:
            print_error(f"Data collection error: {e}")
            return None
        except Exception as e:
            print_error(f"Unexpected error during data collection: {e}")
            return None
    
    def _collect_monitor_data(self) -> list:
        """
        Collect monitor data from connected displays
        
        Returns:
            List of monitor data dictionaries (empty if none found)
        """
        try:
            # Show spinner for quiet mode, detailed output for verbose
            if self.verbosity == 0:
                with spinner("🖥️  Collecting monitor data...", "dots"):
                    collector = MonitorCollector(self.config)
                    monitors = collector.collect_monitors()
                self.logger.quiet(f"{STATUS_OK} Found {len(monitors)} external monitor(s)" if monitors else f"{STATUS_INFO} No external monitors detected")
            else:
                print_section("COLLECTING MONITOR DATA")
                collector = MonitorCollector(self.config)
                monitors = collector.collect_monitors()
                
                if monitors:
                    print_box_header(f"External Monitors ({len(monitors)} found)")
                    for i, monitor in enumerate(monitors, start=1):
                        manufacturer = monitor.get('manufacturer', 'Unknown')
                        model = monitor.get('model', 'Unknown')
                        serial = monitor.get('serial_number', '')
                        resolution = monitor.get('resolution', 'N/A')
                        
                        console.print(f"[dim]│ [/dim][bold cyan]Monitor {i}:[/bold cyan] {manufacturer} {model}")
                        
                        # Show detailed monitor info in debug mode (-vv)
                        if self.verbosity >= 2:
                            native_res = monitor.get('native_resolution', 'N/A')
                            refresh_rate = monitor.get('refresh_rate', 'N/A')
                            connection = monitor.get('connection_interface', 'N/A')
                            bit_depth = monitor.get('bit_depth', 'N/A')
                            screen_size = monitor.get('monitor_screen_size', 'N/A')
                            edid_manufacturer = monitor.get('edid_manufacturer_code', 'N/A')
                            
                            console.print(f"[dim]│   [/dim][dim]Serial:[/dim] {serial if serial else '(empty)'}")
                            console.print(f"[dim]│   [/dim][dim]Resolution:[/dim] {resolution}")
                            console.print(f"[dim]│   [/dim][dim]Native Resolution:[/dim] {native_res}")
                            console.print(f"[dim]│   [/dim][dim]Refresh Rate:[/dim] {refresh_rate}")
                            console.print(f"[dim]│   [/dim][dim]Connection:[/dim] {connection}")
                            console.print(f"[dim]│   [/dim][dim]Bit Depth:[/dim] {bit_depth}")
                            console.print(f"[dim]│   [/dim][dim]Screen Size:[/dim] {screen_size}")
                            console.print(f"[dim]│   [/dim][dim]EDID Code:[/dim] {edid_manufacturer}")
                        else:
                            console.print(f"[dim]│   [/dim][dim]Serial:[/dim] {serial if serial else '(empty)'}")
                            console.print(f"[dim]│   [/dim][dim]Resolution:[/dim] {resolution}")
                    print_box_footer()
                else:
                    print_step("No external monitors detected", "info")
            
            return monitors
            
        except DataCollectionError as e:
            print_warning(f"Monitor collection error: {e}")
            return []
        except Exception as e:
            print_warning(f"Unexpected error during monitor collection: {e}")
            return []
    
    def run_sync(self, test_mode: bool = False) -> bool:
        """
        Run full synchronization process
        
        Args:
            test_mode: If True, collect and display data but don't push to Snipe-IT
            
        Returns:
            True if successful, False otherwise
        """
        # Print header
        print_header(f"{APPLICATION_NAME} - v{VERSION}")
        
        if test_mode:
            console.print(f"{STATUS_INFO} Running in TEST mode - no data will be pushed to Snipe-IT")
            console.print()
        
        start_time = datetime.now()
        
        # Step 1: Load configuration
        if not self._load_configuration():
            return False
        
        # Step 2: Initialize API client and managers
        if not self._initialize_clients():
            return False
        
        # Step 3: Collect system data
        system_data = self._collect_system_data()
        if not system_data:
            print_error("Failed to collect system data")
            return False
        
        # Step 4: Collect monitor data
        monitors = self._collect_monitor_data()
        
        # TEST MODE: Display collected data and exit
        if test_mode:
            self._display_test_results(system_data, monitors)
            return True
        
        # Step 5: Process computer asset (laptop/desktop/server)
        self.logger.quiet("")
        if self.verbosity == 0:
            with spinner("💻 Syncing computer asset to Snipe-IT...", "dots"):
                asset_result = self.asset_manager.process_asset(system_data)
        else:
            asset_result = self.asset_manager.process_asset(system_data)
        
        if not asset_result:
            print_error("Failed to process computer asset")
            return False
        
        # Step 6: Process monitor assets
        parent_hostname = system_data['system_data'].get('hostname', 'Unknown')
        parent_asset_id = asset_result.get('asset_id')
        monitor_results = None
        if monitors:
            self.logger.quiet("")
            if self.verbosity == 0:
                with spinner("🖥️  Syncing monitors to Snipe-IT...", "dots"):
                    monitor_results = self.monitor_manager.process_monitors(
                        monitors, 
                        parent_hostname,
                        parent_asset_id
                    )
            else:
                self.logger.verbose(f"{STATUS_INFO} Processing monitor assets...")
                monitor_results = self.monitor_manager.process_monitors(
                    monitors, 
                    parent_hostname,
                    parent_asset_id
                )
        
        # Step 7: Display final summary
        self._display_sync_summary(asset_result, monitor_results, start_time)
        
        return True
    
    def _display_test_results(self, system_data: Dict[str, Any], monitors: list) -> None:
        """Display test mode results"""
        console.print()
        console.print("=" * 70)
        console.print(f"{STATUS_OK} TEST MODE - Data Collection Complete")
        console.print("=" * 70)
        
        # System data summary
        console.print()
        asset_type = system_data.get('asset_type', 'desktop')  # "laptop", "desktop", or "server"
        asset_type_display = asset_type.capitalize()
        console.print(f"[bold cyan]{asset_type.upper()} DATA:[/bold cyan]")
        console.print()
        
        sd = system_data['system_data']
        console.print(f"  Asset Type:    {asset_type_display}")
        console.print(f"  Hostname:      {sd.get('hostname', 'N/A')}")
        console.print(f"  Manufacturer:  {sd.get('manufacturer', 'N/A')}")
        console.print(f"  Model:         {sd.get('model', 'N/A')}")
        console.print(f"  Serial:        {sd.get('serial_number', 'N/A')}")
        console.print(f"  Chassis Type:  {sd.get('chassis_type', 'N/A')}")
        console.print(f"  OS:            {sd.get('operating_system', 'N/A')}")
        console.print(f"  Processor:     {sd.get('processor', 'N/A')}")
        console.print(f"  Memory:        {sd.get('memory_total_gb', 'N/A')}")
        console.print(f"  IP Address:    {sd.get('ip_address', 'N/A')}")
        
        console.print()
        console.print(f"[bold cyan]CUSTOM FIELDS ({len(system_data['custom_fields'])} fields):[/bold cyan]")
        for field_name, value in system_data['custom_fields'].items():
            console.print(f"  {field_name}: {value}")
        
        # Monitor data summary
        if monitors:
            console.print()
            console.print(f"[bold cyan]MONITOR DATA ({len(monitors)} monitor(s)):[/bold cyan]")
            for i, monitor in enumerate(monitors, start=1):
                console.print()
                console.print(f"  Monitor {i}:")
                console.print(f"    Manufacturer:  {monitor.get('manufacturer', 'N/A')}")
                console.print(f"    Model:         {monitor.get('model', 'N/A')}")
                console.print(f"    Serial:        {monitor.get('serial_number', 'N/A') or '(empty)'}")
                console.print(f"    Resolution:    {monitor.get('resolution', 'N/A')}")
                console.print(f"    Refresh Rate:  {monitor.get('refresh_rate', 'N/A')}")
                console.print(f"    Connection:    {monitor.get('connection_interface', 'N/A')}")
        else:
            console.print()
            console.print("[bold cyan]MONITOR DATA:[/bold cyan]")
            console.print("  No external monitors detected")
        
        console.print()
        console.print("=" * 70)
        console.print(f"{STATUS_OK} Data looks good! Run without --test to sync to Snipe-IT")
        console.print("=" * 70)
        console.print()
    
    def _display_sync_summary(self, asset_result: Dict[str, Any], 
                             monitor_results: Optional[list], 
                             start_time: datetime) -> None:
        """Display final synchronization summary"""
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Determine overall status
        action = asset_result.get('action', 'N/A')
        if action == 'created':
            status_text = "CREATED"
        elif action == 'updated':
            status_text = "UPDATED"
        else:
            status_text = "UP TO DATE"
        
        console.print()
        console.print(f"[bold green]{'═' * 70}[/bold green]")
        console.print(f"[bold green]  SYNCHRONIZATION COMPLETE - {status_text}[/bold green]")
        console.print(f"[bold green]{'═' * 70}[/bold green]")
        
        # Computer asset summary
        print_box_header("Computer Asset")
        print_box_item("Asset ID", str(asset_result.get('asset_id', 'N/A')))
        print_box_item("Hostname", asset_result.get('hostname', 'N/A'))
        print_box_item("Status", status_text)
        
        # Show what changed if updated
        changes = asset_result.get('changes')
        detailed_changes = asset_result.get('detailed_changes', {})
        
        if changes and len(changes) > 0:
            console.print(f"[dim]│ [/dim][cyan]Changes:[/cyan]")
            
            # Show detailed changes in debug mode (-vv)
            if self.verbosity >= 2 and detailed_changes:
                for field_name, change_data in detailed_changes.items():
                    old_val = change_data['old']
                    new_val = change_data['new']
                    console.print(f"[dim]│   [/dim][dim]• {field_name}:[/dim] {old_val} [yellow]→[/yellow] {new_val}")
            else:
                # Show summary in verbose mode (-v)
                for change in changes:
                    console.print(f"[dim]│   [/dim][dim]• {change}[/dim]")
        
        verification = asset_result.get('verification', {})
        if verification:
            populated = verification.get('populated_fields', 0)
            total = verification.get('total_fields', 0)
            percentage = f"({populated/total*100:.0f}%)" if total > 0 else ""
            print_box_item("Custom Fields", f"{populated}/{total} populated {percentage}")
        print_box_footer()
        
        # Monitor summary
        if monitor_results:
            print_box_header(f"Monitor Assets ({len(monitor_results)} total)")
            for i, result in enumerate(monitor_results, start=1):
                mon_action = result.get('action', 'N/A')
                if mon_action == 'created':
                    mon_status = "[green]CREATED[/green]"
                elif mon_action == 'updated':
                    mon_status = "[yellow]UPDATED[/yellow]"
                else:
                    mon_status = "[dim]UP TO DATE[/dim]"
                
                console.print(f"[dim]│ [/dim][bold cyan]Monitor {i}:[/bold cyan] {result.get('name', 'N/A')}")
                console.print(f"[dim]│   [/dim][dim]Asset ID:[/dim] {result.get('asset_id', 'N/A')}")
                console.print(f"[dim]│   [/dim][dim]Status:[/dim] {mon_status}")
                
                # Show monitor changes if updated (with detailed info in debug mode)
                mon_changes = result.get('changes', [])
                mon_detailed_changes = result.get('detailed_changes', {})
                if mon_changes and len(mon_changes) > 0:
                    console.print(f"[dim]│   [/dim][cyan]Changes:[/cyan]")
                    
                    # Show detailed changes in debug mode (-vv)
                    if self.verbosity >= 2 and mon_detailed_changes:
                        for field_name, change_data in mon_detailed_changes.items():
                            old_val = change_data['old']
                            new_val = change_data['new']
                            console.print(f"[dim]│     [/dim][dim]• {field_name}:[/dim] {old_val} [yellow]→[/yellow] {new_val}")
                    else:
                        # Show summary in verbose mode (-v)
                        for change in mon_changes:
                            console.print(f"[dim]│     [/dim][dim]• {change}[/dim]")
                
                if result.get('checked_out_to_user'):
                    user_name = result.get('checked_out_to_user_name', f"User #{result.get('checked_out_to_user')}")
                    console.print(f"[dim]│   [/dim][dim]Checked Out:[/dim] {user_name}")
            print_box_footer()
        
        console.print(f"\n[dim]Completed in {elapsed:.2f}s[/dim]\n")


def run_sync(test_mode: bool = False, verify_ssl: bool = True, 
             config_path: Optional[str] = None, verbosity: int = 0) -> bool:
    """
    Convenience function to run synchronization
    
    Args:
        test_mode: Run in test mode (no data pushed)
        verify_ssl: Verify SSL certificates
        config_path: Path to configuration file
        verbosity: Verbosity level (0=quiet, 1=verbose, 2=debug)
        
    Returns:
        True if successful, False otherwise
    """
    sync_manager = SyncManager(config_path, verify_ssl, verbosity)
    return sync_manager.run_sync(test_mode)
