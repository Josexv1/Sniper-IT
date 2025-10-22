"""
Sniper-IT Agent - Sync Manager
Orchestrates the full synchronization process
"""

from typing import Dict, Any, Optional
from datetime import datetime

from core.api_client import SnipeITClient
from core.config_manager import ConfigManager
from collectors.system_collector import SystemDataCollector
from collectors.monitor_collector import MonitorCollector
from managers.asset_manager import AssetManager
from managers.monitor_manager import MonitorManager
from cli.formatters import console, print_header, print_info, print_error, print_warning, spinner
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
        self.logger.quiet("")
        
        try:
            # Show spinner for quiet mode, detailed output for verbose
            if self.verbosity == 0:
                with spinner("🔍 Collecting system data...", "dots"):
                    collector = SystemDataCollector(self.config)
                    system_data = collector.collect_all()
            else:
                self.logger.verbose(f"{STATUS_INFO} Collecting system data...")
                self.logger.verbose("=" * 70)
                collector = SystemDataCollector(self.config)
                system_data = collector.collect_all()
            
            # Display summary
            hostname = system_data['system_data'].get('hostname', 'Unknown')
            manufacturer = system_data['system_data'].get('manufacturer', 'Unknown')
            model = system_data['system_data'].get('model', 'Unknown')
            serial = system_data['system_data'].get('serial_number', 'Unknown')
            os_type = system_data.get('os_type', 'Unknown')
            
            self.logger.quiet(f"{STATUS_OK} System data collected")
            self.logger.verbose(f"    Hostname: {hostname}")
            self.logger.verbose(f"    Manufacturer: {manufacturer}")
            self.logger.verbose(f"    Model: {model}")
            self.logger.verbose(f"    Serial: {serial}")
            self.logger.verbose(f"    OS: {os_type}")
            self.logger.debug(f"    Custom Fields: {len(system_data['custom_fields'])} fields collected")
            
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
        self.logger.quiet("")
        
        try:
            # Show spinner for quiet mode, detailed output for verbose
            if self.verbosity == 0:
                with spinner("🖥️  Collecting monitor data...", "dots"):
                    collector = MonitorCollector(self.config)
                    monitors = collector.collect_monitors()
            else:
                self.logger.verbose(f"{STATUS_INFO} Collecting monitor data...")
                self.logger.verbose("=" * 70)
                collector = MonitorCollector(self.config)
                monitors = collector.collect_monitors()
            
            if monitors:
                self.logger.quiet(f"{STATUS_OK} Found {len(monitors)} external monitor(s)")
                for i, monitor in enumerate(monitors, start=1):
                    self.logger.verbose(f"    Monitor {i}: {monitor.get('manufacturer', 'Unknown')} {monitor.get('model', 'Unknown')}")
            else:
                self.logger.verbose(f"{STATUS_INFO} No external monitors detected")
                self.logger.debug("    (Internal laptop displays are automatically excluded)")
            
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
        
        # Step 5: Process laptop/desktop asset
        self.logger.quiet("")
        if self.verbosity == 0:
            with spinner("💻 Syncing laptop/desktop to Snipe-IT...", "dots"):
                asset_result = self.asset_manager.process_asset(system_data)
        else:
            self.logger.verbose(f"{STATUS_INFO} Processing laptop/desktop asset...")
            asset_result = self.asset_manager.process_asset(system_data)
        
        if not asset_result:
            print_error("Failed to process laptop/desktop asset")
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
        console.print("[bold cyan]LAPTOP/DESKTOP DATA:[/bold cyan]")
        console.print()
        
        sd = system_data['system_data']
        console.print(f"  Hostname:      {sd.get('hostname', 'N/A')}")
        console.print(f"  Manufacturer:  {sd.get('manufacturer', 'N/A')}")
        console.print(f"  Model:         {sd.get('model', 'N/A')}")
        console.print(f"  Serial:        {sd.get('serial_number', 'N/A')}")
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
        
        console.print()
        console.print("=" * 70)
        console.print(f"{STATUS_OK} SYNCHRONIZATION COMPLETE")
        console.print("=" * 70)
        
        # Laptop/Desktop summary
        console.print()
        console.print("[bold cyan]Laptop/Desktop Asset:[/bold cyan]")
        console.print(f"  Asset ID:       {asset_result.get('asset_id', 'N/A')}")
        console.print(f"  Hostname:       {asset_result.get('hostname', 'N/A')}")
        console.print(f"  Action:         {asset_result.get('action', 'N/A').upper()}")
        
        verification = asset_result.get('verification', {})
        if verification:
            console.print(f"  Custom Fields:  {verification.get('populated_fields', 0)}/{verification.get('total_fields', 0)} populated")
        
        # Monitor summary
        if monitor_results:
            console.print()
            console.print(f"[bold cyan]Monitor Assets ({len(monitor_results)}):[/bold cyan]")
            for i, result in enumerate(monitor_results, start=1):
                console.print(f"  Monitor {i}:")
                console.print(f"    Asset ID:     {result.get('asset_id', 'N/A')}")
                console.print(f"    Name:         {result.get('name', 'N/A')}")
                console.print(f"    Action:       {result.get('action', 'N/A').upper()}")
                if result.get('checked_out_to'):
                    console.print(f"    Checked Out:  Yes (to Asset #{result.get('checked_out_to')})")
                else:
                    console.print(f"    Checked Out:  No")
        
        console.print()
        console.print(f"Elapsed Time: {elapsed:.2f} seconds")
        console.print("=" * 70)
        console.print()


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
