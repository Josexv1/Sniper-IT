"""
Sniper-IT Agent - Setup Manager
Interactive setup wizard to generate config.yaml
"""

import requests
import urllib3
from typing import Dict, Any, Optional, List
from pathlib import Path

from core.config_manager import ConfigManager, create_default_config
from core.constants import APPLICATION_NAME, VERSION, CONFIG_FILENAME, MONITOR_FIELD_DEFINITIONS
from cli.formatters import (
    console, print_header, print_ok, print_error, print_warning, print_info,
    prompt_input, prompt_yes_no, display_companies_table, display_categories_table,
    display_fieldsets_table, display_status_list, display_custom_fields_table,
    print_success_summary, print_error_summary, display_table
)
from utils.exceptions import SetupError, APIConnectionError


def get_internal_field_definitions() -> Dict[str, str]:
    """
    Get our internal laptop custom field definitions
    
    Returns:
        Dict mapping field names to their expected db_column prefix (without ID suffix)
    
    Note: Snipe-IT appends _<ID> to db_columns where ID is the field creation order.
          We match on the prefix only, ignoring the ID suffix.
          
    IMPORTANT: Snipe-IT auto-generates db_column names from field names by:
               - Converting to lowercase
               - Replacing spaces/special chars with underscores
               - Adding _snipeit_ prefix and _<ID> suffix
               
               So "Agent Version" becomes "_snipeit_agent_version_<ID>"
               But "Sniper-IT Agent Version" becomes "_snipeit_sniper_it_agent_version_<ID>"
    """
    return {
        'Operating System': '_snipeit_operating_system_',
        'OS Install Date': '_snipeit_os_install_date_',
        'Memory / RAM': '_snipeit_memory_ram_',
        'RAM Usage': '_snipeit_ram_usage_',
        'BIOS Release Date': '_snipeit_bios_release_date_',
        'IP Address': '_snipeit_ip_address_',
        'Processor / CPU': '_snipeit_processor_cpu_',
        'Windows Username': '_snipeit_windows_username_',
        'MAC Address': '_snipeit_mac_address_',
        'Total Storage': '_snipeit_total_storage_',
        'Storage Information': '_snipeit_storage_information_',
        'Disk Space Used': '_snipeit_disk_space_used_',
        'Agent Version': '_snipeit_agent_version_',  # Changed from "Sniper-IT Agent Version"
        'CPU Temperature': '_snipeit_cpu_temperature_',
        'Uptime': '_snipeit_uptime_',  # Changed from "System Uptime (Days)"
        'Screen Size': '_snipeit_screen_size_'
    }


def get_monitor_field_definitions() -> Dict[str, str]:
    """
    Get our internal monitor custom field definitions
    
    Returns:
        Dict mapping field names to their expected db_column prefix (without ID suffix)
        
    Note: Manufacturer, Model, and Serial Number are standard Snipe-IT asset fields,
          not custom fields. They don't need to be defined here.
    """
    return {
        'Resolution': '_snipeit_resolution_',
        'Native Resolution': '_snipeit_native_resolution_',
        'Refresh Rate': '_snipeit_refresh_rate_',
        'Connection Interface': '_snipeit_connection_interface_',
        'Bit Depth': '_snipeit_bit_depth_',
        'Monitor Screen Size': '_snipeit_monitor_screen_size_'
    }


class SetupManager:
    """Manages the interactive setup wizard"""
    
    def __init__(self, verify_ssl: bool = True):
        self.config_manager = ConfigManager()
        self.api_url: Optional[str] = None
        self.api_key: Optional[str] = None
        self.verify_ssl: bool = verify_ssl
        self.session: Optional[requests.Session] = None
        self.actual_field_mappings: Dict[str, str] = {}  # Maps laptop field name to actual db_column
        self.actual_monitor_field_mappings: Dict[str, str] = {}  # Maps monitor field name to actual db_column
    
    def run_setup(self) -> bool:
        """
        Run the interactive setup wizard
        
        Returns:
            True if setup completed successfully, False otherwise
        """
        console.print()
        print_header(f"{APPLICATION_NAME} - Interactive Setup Wizard")
        console.print(f"Version: {VERSION}\n", style="dim")
        
        # Check if config already exists
        if self.config_manager.exists():
            print_warning(f"Configuration file already exists: {self.config_manager.config_path}")
            if not prompt_yes_no("Do you want to overwrite it?", default=False):
                print_info("Setup cancelled. Using existing configuration.")
                return False
            console.print()
        
        # Check if build secrets exist (hardcoded credentials)
        has_build_secrets = False
        try:
            from core.build_secrets import BUILD_SERVER_URL, BUILD_API_KEY, BUILD_IGNORE_SSL
            if BUILD_SERVER_URL and BUILD_API_KEY:
                has_build_secrets = True
                self.api_url = BUILD_SERVER_URL
                self.api_key = BUILD_API_KEY
                # Override verify_ssl if build secrets specify ignore SSL
                if BUILD_IGNORE_SSL:
                    self.verify_ssl = False
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                
                console.print()
                print_ok("Build-time credentials detected!")
                print_info(f"Server: {self.api_url}")
                print_info(f"SSL Verification: {'Enabled' if self.verify_ssl else 'Disabled'}")
                console.print()
                print_info("Server configuration will be skipped - credentials are hardcoded in executable")
                console.print()
        except (ImportError, AttributeError):
            pass
        
        try:
            # Skip server configuration if credentials are hardcoded
            if not has_build_secrets:
                # Step 1: Server Configuration
                if not self._step_server_configuration():
                    return False
                
                # Step 2: Test API Connection
                if not self._step_test_connection():
                    return False
            else:
                # Use build secrets to create session and test connection
                if not self._step_test_connection_with_build_secrets():
                    return False
            
            # Step 3: Select Company
            company_id = self._step_select_company()
            if company_id is None:
                return False
            
            # Step 4: Select Status (shared for both laptop and monitors)
            status_id = self._step_select_status()
            if status_id is None:
                return False
            
            console.print()
            console.print()
            console.print("[bold cyan]═══════════════════════════════════════════════[/bold cyan]")
            console.print("[bold cyan]    COMPUTER ASSET CONFIGURATION           [/bold cyan]")
            console.print("[bold cyan]═══════════════════════════════════════════════[/bold cyan]")
            console.print()
            
            # Step 5: Select Laptop, Desktop, and Server Categories
            category_ids = self._step_select_computer_categories()
            if category_ids is None:
                return False
            
            laptop_category_id = category_ids['laptop']
            desktop_category_id = category_ids['desktop']
            server_category_id = category_ids['server']
            
            # Step 6: Select or Create Computer Fieldset (shared for Laptop, Desktop, Server)
            laptop_fieldset_id = self._step_select_or_create_fieldset("Computer")
            if laptop_fieldset_id is None:
                return False
            
            # Step 7: Review and Create Computer Custom Fields
            if not self._step_review_and_create_custom_fields(laptop_fieldset_id, "Computer"):
                return False
            
            console.print()
            console.print()
            console.print("[bold cyan]═══════════════════════════════════════════════[/bold cyan]")
            console.print("[bold cyan]       MONITOR ASSET CONFIGURATION          [/bold cyan]")
            console.print("[bold cyan]═══════════════════════════════════════════════[/bold cyan]")
            console.print()
            
            # Step 8: Select Monitor Category
            monitor_category_id = self._step_select_category("Monitor")
            if monitor_category_id is None:
                return False
            
            # Step 9: Select or Create Monitor Fieldset
            monitor_fieldset_id = self._step_select_or_create_fieldset("Monitor")
            if monitor_fieldset_id is None:
                return False
            
            # Step 10: Review and Create Monitor Custom Fields
            if not self._step_review_and_create_custom_fields(monitor_fieldset_id, "Monitor"):
                return False
            
            # Step 11: Computer Asset Tag Naming Convention (Optional)
            naming_convention = self._step_configure_naming_convention("Computer")
            
            # Step 12: Monitor Asset Tag Naming Convention (Optional)
            monitor_naming_convention = self._step_configure_naming_convention("Monitor")
            
            # Ask if user wants to generate config
            console.print()
            if not prompt_yes_no("Generate configuration file?", default=True):
                print_info("Setup cancelled. Configuration not saved.")
                return False
            
            # Step 13: Generate Configuration
            if not self._step_generate_config(
                company_id, 
                laptop_category_id,
                desktop_category_id,
                server_category_id,
                laptop_fieldset_id, 
                monitor_category_id,
                monitor_fieldset_id,
                status_id,
                naming_convention,
                monitor_naming_convention
            ):
                return False
            
            # Success!
            self._display_success()
            return True
            
        except KeyboardInterrupt:
            console.print("\n")
            print_error("Setup cancelled by user")
            return False
        except Exception as e:
            console.print("\n")
            print_error(f"Setup failed: {e}")
            return False
        finally:
            if self.session:
                self.session.close()
    
    def _step_server_configuration(self) -> bool:
        """Step 1: Get server URL and API key"""
        print_header("Step 1/8: Server Configuration")
        console.print()
        
        # Get server URL
        while True:
            url = prompt_input("Snipe-IT Server URL (e.g., https://snipeit.company.com)")
            
            if not url:
                print_error("Server URL cannot be empty")
                continue
            
            # Normalize URL
            url = url.strip().rstrip('/')
            if not url.startswith(('http://', 'https://')):
                url = f"https://{url}"
            
            # Remove /api/v1 if user included it
            url = url.replace('/api/v1', '')
            
            self.api_url = url
            break
        
        # Get API key
        while True:
            api_key = prompt_input("Snipe-IT API Key")
            
            if not api_key or not api_key.strip():
                print_error("API key cannot be empty")
                continue
            
            self.api_key = api_key.strip()
            break
        
        # Only ask about SSL verification if not already set via --issl
        if self.verify_ssl:  # If True (default), ask user
            self.verify_ssl = prompt_yes_no("Verify SSL certificates?", default=True)
            
            if not self.verify_ssl:
                print_warning("SSL verification disabled")
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        else:
            # Already disabled via --issl
            print_info("SSL verification: Disabled (--issl flag)")
        
        return True
    
    def _step_test_connection(self) -> bool:
        """Step 2: Test API connection"""
        print_header("Step 2/8: API Connection Test")
        console.print()
        
        print_info(f"Server: {self.api_url}")
        print_info(f"API Key: {self.api_key[:20]}...")
        print_info(f"SSL Verification: {'Enabled' if self.verify_ssl else 'Disabled'}")
        console.print()
        
        print_info("Testing connection...")
        
        try:
            # Create session
            self.session = requests.Session()
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })
            
            # Test endpoint
            response = self.session.get(
                f"{self.api_url}/api/v1/hardware",
                params={'limit': 1},
                verify=self.verify_ssl,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                total_assets = data.get('total', 0)
                print_ok("Connection successful!")
                print_info(f"Total assets in Snipe-IT: {total_assets:,}")
                return True
            elif response.status_code == 401:
                print_error("Authentication failed - Invalid API key")
                return False
            else:
                print_error(f"Connection failed: HTTP {response.status_code}")
                print_info(f"Response: {response.text[:200]}")
                return False
                
        except requests.exceptions.SSLError as e:
            print_error(f"SSL Certificate Error: {e}")
            print_warning("Try using --issl flag to ignore SSL verification")
            return False
        except requests.exceptions.ConnectionError:
            print_error(f"Connection Error: Cannot reach {self.api_url}")
            print_warning("Check the server URL and your network connection")
            return False
        except requests.exceptions.Timeout:
            print_error("Connection Timeout: Server took too long to respond")
            return False
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            return False
    
    def _step_test_connection_with_build_secrets(self) -> bool:
        """Test API connection using build secrets (hardcoded credentials)"""
        print_header("API Connection Test")
        console.print()
        
        print_info("Testing connection with hardcoded credentials...")
        console.print()
        
        try:
            # Create session
            self.session = requests.Session()
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })
            
            # Test endpoint
            response = self.session.get(
                f"{self.api_url}/api/v1/hardware",
                params={'limit': 1},
                verify=self.verify_ssl,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                total_assets = data.get('total', 0)
                print_ok("Connection successful!")
                print_info(f"Total assets in Snipe-IT: {total_assets:,}")
                console.print()
                return True
            elif response.status_code == 401:
                print_error("Authentication failed - Invalid hardcoded API key")
                print_warning("The executable was built with invalid credentials")
                return False
            else:
                print_error(f"Connection failed: HTTP {response.status_code}")
                print_info(f"Response: {response.text[:200]}")
                return False
                
        except requests.exceptions.SSLError as e:
            print_error(f"SSL Certificate Error: {e}")
            print_warning("The executable was built with SSL verification enabled")
            print_warning("Rebuild with --ignore-ssl flag if using self-signed certificates")
            return False
        except requests.exceptions.ConnectionError:
            print_error(f"Connection Error: Cannot reach {self.api_url}")
            print_warning("Check the server URL and your network connection")
            return False
        except requests.exceptions.Timeout:
            print_error("Connection Timeout: Server took too long to respond")
            return False
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            return False
    
    def _api_get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make an API GET request"""
        try:
            response = self.session.get(
                f"{self.api_url}/api/v1/{endpoint}",
                params=params or {},
                verify=self.verify_ssl,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print_error(f"API request failed: {e}")
            return None
    
    def _step_select_company(self) -> Optional[int]:
        """Step 3: Select default company"""
        print_header("Step 3: Company Selection")
        console.print()
        
        print_info("Fetching companies...")
        data = self._api_get('companies', {'limit': 100})
        
        if not data:
            print_error("Failed to fetch companies")
            return None
        
        companies = data.get('rows', [])
        if not companies:
            print_warning("No companies found - using default ID 1")
            return 1
        
        console.print()
        display_companies_table(companies)
        console.print()
        
        while True:
            company_id = prompt_input("Select default company ID", default="1")
            try:
                company_id = int(company_id)
                # Validate ID exists
                if any(c.get('id') == company_id for c in companies):
                    print_ok(f"Selected company ID: {company_id}")
                    return company_id
                else:
                    print_warning(f"Company ID {company_id} not found in list")
            except ValueError:
                print_error("Please enter a valid number")
    
    def _step_select_category(self, asset_type: str = "Laptop") -> Optional[int]:
        """Select category for laptop or monitor"""
        print_header(f"{asset_type} Category Selection")
        console.print()
        
        print_info("Fetching categories...")
        data = self._api_get('categories', {'limit': 100})
        
        if not data:
            print_error("Failed to fetch categories")
            return None
        
        categories = data.get('rows', [])
        if not categories:
            print_warning("No categories found - using default ID 2")
            return 2
        
        # Smart detection: Find category that matches the asset type by name
        detected_id = None
        search_term = asset_type.lower()
        
        for cat in categories:
            cat_name = cat.get('name', '').lower()
            cat_id = cat.get('id')
            
            if search_term in cat_name and not detected_id:
                detected_id = cat_id
                break
        
        console.print()
        display_categories_table(categories)
        console.print()
        
        # Use detected ID if found, otherwise use defaults
        if detected_id:
            default_id = str(detected_id)
        else:
            default_id = "2" if asset_type == "Laptop" else "5"
        
        while True:
            category_id = prompt_input(f"Select {asset_type} category ID", default=default_id)
            try:
                category_id = int(category_id)
                if any(c.get('id') == category_id for c in categories):
                    print_ok(f"Selected {asset_type} category ID: {category_id}")
                    return category_id
                else:
                    print_warning(f"Category ID {category_id} not found in list")
            except ValueError:
                print_error("Please enter a valid number")
    
    def _step_select_computer_categories(self) -> Optional[Dict[str, int]]:
        """Select categories for laptop, desktop, and server (comma-separated)"""
        print_header("Computer Categories Selection")
        console.print()
        
        print_info("Fetching categories...")
        data = self._api_get('categories', {'limit': 100})
        
        if not data:
            print_error("Failed to fetch categories")
            return None
        
        categories = data.get('rows', [])
        if not categories:
            print_warning("No categories found - using defaults")
            return {'laptop': 2, 'desktop': 3, 'server': 4}
        
        # Smart detection: Find categories that match Laptop, Desktop, Server by name
        detected_laptop = None
        detected_desktop = None
        detected_server = None
        
        for cat in categories:
            cat_name = cat.get('name', '').lower()
            cat_id = cat.get('id')
            
            if 'laptop' in cat_name and not detected_laptop:
                detected_laptop = cat_id
            elif 'desktop' in cat_name and not detected_desktop:
                detected_desktop = cat_id
            elif 'server' in cat_name and not detected_server:
                detected_server = cat_id
        
        # Build smart default suggestion
        smart_default = f"{detected_laptop or 2},{detected_desktop or 3},{detected_server or 4}"
        
        console.print()
        display_categories_table(categories)
        console.print()
        
        print_info("Select Laptop, Desktop, and Server categories (comma-separated)")
        if detected_laptop or detected_desktop or detected_server:
            console.print(f"  [dim]Detected: Laptop={detected_laptop or '?'}, Desktop={detected_desktop or '?'}, Server={detected_server or '?'}[/dim]")
        console.print("  [dim]Example: 3,38,15  where 3=Laptop, 38=Desktop, 15=Server[/dim]")
        console.print()
        
        while True:
            user_input = prompt_input("Enter category IDs (Laptop,Desktop,Server)", default=smart_default)
            
            # Parse comma-separated input
            parts = [p.strip() for p in user_input.split(',')]
            
            if len(parts) != 3:
                print_error("Please enter exactly 3 category IDs separated by commas")
                console.print("  [dim]Example: 3,38,15[/dim]")
                continue
            
            try:
                laptop_id = int(parts[0])
                desktop_id = int(parts[1])
                server_id = int(parts[2])
                
                # Validate all IDs exist
                laptop_exists = any(c.get('id') == laptop_id for c in categories)
                desktop_exists = any(c.get('id') == desktop_id for c in categories)
                server_exists = any(c.get('id') == server_id for c in categories)
                
                if not laptop_exists:
                    print_warning(f"Laptop category ID {laptop_id} not found")
                    continue
                
                if not desktop_exists:
                    print_warning(f"Desktop category ID {desktop_id} not found")
                    continue
                
                if not server_exists:
                    print_warning(f"Server category ID {server_id} not found")
                    continue
                
                # Get category names for confirmation
                laptop_name = next((c.get('name') for c in categories if c.get('id') == laptop_id), 'Unknown')
                desktop_name = next((c.get('name') for c in categories if c.get('id') == desktop_id), 'Unknown')
                server_name = next((c.get('name') for c in categories if c.get('id') == server_id), 'Unknown')
                
                console.print()
                console.print(f"  [cyan]Laptop Category:[/cyan]  {laptop_name} (ID: {laptop_id})")
                console.print(f"  [cyan]Desktop Category:[/cyan] {desktop_name} (ID: {desktop_id})")
                console.print(f"  [cyan]Server Category:[/cyan]  {server_name} (ID: {server_id})")
                console.print()
                
                # Confirm selection
                if prompt_yes_no("Is this correct?", default=True):
                    print_ok(f"Selected Laptop: {laptop_id}, Desktop: {desktop_id}, Server: {server_id}")
                    return {'laptop': laptop_id, 'desktop': desktop_id, 'server': server_id}
                else:
                    console.print()
                    continue
                    
            except ValueError:
                print_error("Please enter valid numbers separated by commas")
                console.print("  [dim]Example: 3,38,15[/dim]")
    
    def _step_select_or_create_fieldset(self, asset_type: str = "Laptop") -> Optional[int]:
        """Select or create fieldset for laptop or monitor"""
        print_header(f"{asset_type} Fieldset Selection")
        console.print()
        
        print_info("Fetching fieldsets...")
        data = self._api_get('fieldsets', {'limit': 100})
        
        if not data:
            print_error("Failed to fetch fieldsets")
            return None
        
        fieldsets = data.get('rows', [])
        
        # If no fieldsets exist, create one
        if not fieldsets:
            console.print()
            print_warning("No fieldsets found in Snipe-IT")
            print_info(f"A fieldset is required to group {asset_type.lower()} custom fields")
            console.print()
            
            if not prompt_yes_no(f"Create a new {asset_type.lower()} fieldset?", default=True):
                print_error("Fieldset is required. Setup cannot continue.")
                return None
            
            # Get fieldset name
            default_name = f"{asset_type} Information" if asset_type == "Monitor" else "Computer Assets"
            fieldset_name = prompt_input(f"Enter {asset_type.lower()} fieldset name", default=default_name)
            
            # Create fieldset via API
            print_info(f"Creating fieldset '{fieldset_name}'...")
            created_fieldset = self._api_create_fieldset(fieldset_name)
            
            if created_fieldset:
                fieldset_id = created_fieldset.get('id')
                print_ok(f"Fieldset created successfully! ID: {fieldset_id}")
                return fieldset_id
            else:
                print_error("Failed to create fieldset")
                return None
        
        # Smart detection: Find fieldset that matches the asset type by name
        detected_id = None
        
        # For Computer, look for keywords like "PC", "Laptop", "Computer"
        if asset_type == "Computer":
            search_terms = ['computer', 'pc', 'laptop', 'all pc']
        else:
            search_terms = [asset_type.lower()]
        
        for fieldset in fieldsets:
            fieldset_name = fieldset.get('name', '').lower()
            fieldset_id = fieldset.get('id')
            
            for term in search_terms:
                if term in fieldset_name and not detected_id:
                    detected_id = fieldset_id
                    break
            
            if detected_id:
                break
        
        # Display available fieldsets
        console.print()
        display_fieldsets_table(fieldsets)
        console.print()
        print_info("Enter a fieldset ID, or type 'new' to create a new fieldset")
        console.print()
        
        # Use detected ID if found, otherwise use defaults
        if detected_id:
            default_id = str(detected_id)
        else:
            default_id = "1" if asset_type == "Laptop" else "2"
        
        while True:
            fieldset_id = prompt_input(f"Select {asset_type.lower()} fieldset ID (or 'new')", default=default_id)
            
            # Check if user wants to create new fieldset
            if fieldset_id.lower() == 'new':
                console.print()
                if asset_type == "Monitor":
                    default_name = "Monitor Information"
                elif asset_type == "Computer":
                    default_name = "Computer Assets"
                else:
                    default_name = f"{asset_type} Information"
                fieldset_name = prompt_input(f"Enter new {asset_type.lower()} fieldset name", default=default_name)
                
                print_info(f"Creating fieldset '{fieldset_name}'...")
                created_fieldset = self._api_create_fieldset(fieldset_name)
                
                if created_fieldset:
                    fieldset_id = created_fieldset.get('id')
                    print_ok(f"Fieldset created successfully! ID: {fieldset_id}")
                    return fieldset_id
                else:
                    print_error("Failed to create fieldset. Try again.")
                    continue
            
            try:
                fieldset_id = int(fieldset_id)
                if any(f.get('id') == fieldset_id for f in fieldsets):
                    print_ok(f"Selected {asset_type.lower()} fieldset ID: {fieldset_id}")
                    return fieldset_id
                else:
                    print_warning(f"Fieldset ID {fieldset_id} not found in list")
            except ValueError:
                print_error("Please enter a valid number or 'new'")
    
    def _api_create_fieldset(self, name: str) -> Optional[Dict[str, Any]]:
        """Create a fieldset via API"""
        try:
            response = self.session.post(
                f"{self.api_url}/api/v1/fieldsets",
                json={'name': name},
                verify=self.verify_ssl,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get('payload')
            else:
                print_error(f"API Error: HTTP {response.status_code}")
                return None
        except Exception as e:
            print_error(f"Failed to create fieldset: {e}")
            return None
    
    def _step_select_status(self) -> Optional[int]:
        """Select default status (shared for both laptop and monitors)"""
        print_header("Step 4: Status Selection (for all assets)")
        console.print()
        
        print_info("Fetching status labels...")
        data = self._api_get('statuslabels', {'limit': 100})
        
        if not data:
            print_error("Failed to fetch status labels")
            return None
        
        statuses = data.get('rows', [])
        if not statuses:
            print_warning("No statuses found - using default ID 2")
            return 2
        
        console.print()
        display_status_list(statuses)
        console.print()
        
        while True:
            status_id = prompt_input("Select default status ID", default="2")
            try:
                status_id = int(status_id)
                if any(s.get('id') == status_id for s in statuses):
                    print_ok(f"Selected status ID: {status_id}")
                    return status_id
                else:
                    print_warning(f"Status ID {status_id} not found in list")
            except ValueError:
                print_error("Please enter a valid number")
    
    def _step_configure_naming_convention(self, asset_type: str = "Computer") -> str:
        """Configure optional asset tag naming convention
        
        Args:
            asset_type: Type of asset ("Computer" or "Monitor")
            
        Returns:
            Naming convention pattern or empty string
        """
        console.print()
        console.print()
        console.print("[bold cyan]═══════════════════════════════════════════════[/bold cyan]")
        console.print(f"[bold cyan]  {asset_type.upper()} ASSET TAG NAMING CONVENTION (Optional)  [/bold cyan]")
        console.print("[bold cyan]═══════════════════════════════════════════════[/bold cyan]")
        console.print()
        
        print_info(f"{asset_type} asset tag generation options:")
        console.print()
        console.print("[bold]Option 1: Agent-managed auto-increment[/bold]")
        console.print("  • Agent searches for last tag and increments automatically")
        console.print("  • Use '-N' or '_N' as placeholder (will be replaced with number)")
        console.print("  • Pattern examples:")
        if asset_type == "Monitor":
            console.print("    - MIS-MON-N   → MIS-MON-0001, MIS-MON-0002, MIS-MON-0003...")
            console.print("    - MONITOR_N   → MONITOR_0001, MONITOR_0002, MONITOR_0003...")
            console.print("    - MON-N       → MON-0001, MON-0002, MON-0003...")
        else:
            console.print("    - MIS-2025-N  → MIS-2025-0001, MIS-2025-0002, MIS-2025-0003...")
            console.print("    - LAPTOP_N    → LAPTOP_0001, LAPTOP_0002, LAPTOP_0003...")
            console.print("    - IT-N        → IT-0001, IT-0002, IT-0003...")
        console.print()
        console.print("[bold]Option 2: Snipe-IT built-in auto-increment[/bold]")
        console.print("  • Configure in: Settings → Asset Tags → Auto-increment")
        console.print("  • Managed entirely within Snipe-IT")
        console.print()
        if asset_type == "Monitor":
            console.print("[bold]Option 3: Use serial number as asset tag[/bold]")
            console.print("  • Asset tag = monitor serial (e.g., 3CM2233B68)")
            console.print("  • Simple and guaranteed unique")
            console.print()
            console.print("[dim]Note: Monitor asset name will always be the model (e.g., HP M24fe FHD)[/dim]")
        else:
            console.print("[bold]Option 3: Use hostname as asset tag[/bold]")
            console.print("  • Asset tag = hostname (e.g., LAMAD0150)")
            console.print("  • Simple and guaranteed unique")
            console.print()
            console.print("[dim]Note: Computer asset name will always be the hostname[/dim]")
        console.print()
        
        if not prompt_yes_no(f"Do you want to use custom automatic {asset_type.lower()} asset tag generation by the Agent?", default=False):
            if asset_type == "Monitor":
                print_info("Skipping - Agent will use serial number as monitor asset tag")
            else:
                print_info("Skipping - Agent will use hostname as asset tag")
            print_info("You can configure asset tag auto-increment in Snipe-IT Settings if needed")
            return ""
        
        console.print()
        print_info("Enter your naming pattern:")
        console.print("  • Use 'N' as placeholder - it will be replaced with auto-increment number")
        if asset_type == "Monitor":
            console.print("  • Use '-N' or '_N' for best results (e.g., MIS-MON-N, MONITOR_N)")
        else:
            console.print("  • Use '-N' or '_N' for best results (e.g., MIS-2025-N, LAPTOP_N)")
        console.print("  • The 'N' will become: 0001, 0002, 0003, etc.")
        console.print()
        
        while True:
            pattern = prompt_input(f"{asset_type} asset tag pattern (or press Enter to skip)", default="")
            
            if not pattern or not pattern.strip():
                if asset_type == "Monitor":
                    print_info("No pattern configured - will use serial number as monitor asset tag")
                else:
                    print_info("No pattern configured - will use hostname as asset tag")
                return ""
            
            pattern = pattern.strip()
            
            # Validate pattern contains 'N'
            if 'N' not in pattern:
                print_error("Pattern must contain 'N' as placeholder for the auto-increment number")
                if asset_type == "Monitor":
                    console.print("  [dim]Examples: MIS-MON-N, MONITOR_N, MON-N[/dim]")
                else:
                    console.print("  [dim]Examples: MIS-2025-N, LAPTOP_N, IT-N[/dim]")
                continue
            
            # Validate pattern has only one 'N'
            if pattern.count('N') > 1:
                print_error("Pattern should contain only one 'N' placeholder")
                continue
            
            print_ok(f"Pattern configured: {pattern}")
            console.print()
            console.print(f"[dim]The 'N' will be replaced with: 0001, 0002, 0003...[/dim]")
            console.print(f"[dim]Example tags: {pattern.replace('N', '0001')}, {pattern.replace('N', '0002')}, {pattern.replace('N', '0003')}[/dim]")
            return pattern
    
    def _validate_custom_fields(
        self, 
        snipeit_fields: List[Dict[str, Any]], 
        internal_fields: Dict[str, str],
        asset_type: str = "Laptop"
    ) -> Dict[str, str]:
        """
        Validate Snipe-IT custom fields against internal definitions
        Also stores the actual field mappings for config generation
        
        Args:
            snipeit_fields: List of fields from Snipe-IT API
            internal_fields: Dict mapping field names to expected db_column prefixes
            asset_type: "Computer", "Laptop", or "Monitor" to determine which mapping dict to use
            
        Returns:
            Dict mapping db_column to validation status
        """
        validation = {}
        
        # Choose the correct field mappings dict
        # Computer and Laptop use the same field mappings (self.actual_field_mappings)
        field_mappings = self.actual_monitor_field_mappings if asset_type == "Monitor" else self.actual_field_mappings
        
        for field in snipeit_fields:
            name = field.get('name', '')
            db_column = field.get('db_column_name', '')
            field_id = field.get('id', 'N/A')
            
            # Check if this field is in our internal definitions
            if name in internal_fields:
                expected_prefix = internal_fields[name]
                
                # Match on prefix (ignore the _<ID> suffix)
                if db_column.startswith(expected_prefix):
                    # Store the actual db_column for this field
                    field_mappings[name] = db_column
                    
                    # Extract the ID from db_column
                    try:
                        suffix = db_column[len(expected_prefix):]
                        if suffix.isdigit():
                            validation[db_column] = f'[OK] ID:{suffix}'
                        else:
                            validation[db_column] = '[OK]'
                    except:
                        validation[db_column] = '[OK]'
                else:
                    # DB column prefix mismatch
                    validation[db_column] = f'[WARN] Expected prefix: {expected_prefix}*'
            else:
                # Check if db_column prefix matches but name is different
                matching_internal = None
                for internal_name, expected_prefix in internal_fields.items():
                    # Check if the db_column starts with any of our expected prefixes
                    if db_column.startswith(expected_prefix):
                        matching_internal = internal_name
                        break
                
                if matching_internal:
                    validation[db_column] = f'[WARN] Name mismatch: Expected "{matching_internal}"'
                else:
                    # Not in our internal definitions - that's okay, user-created field
                    validation[db_column] = '[INFO] Custom field'
        
        return validation
    
    def _create_missing_fields(self, missing_field_names: List[str], fieldset_id: int, asset_type: str = "Laptop") -> int:
        """
        Create missing custom fields via API
        
        Args:
            missing_field_names: List of field names to create
            fieldset_id: ID of the fieldset to assign fields to
            asset_type: "Computer", "Laptop", or "Monitor" to determine which field definitions to use
            
        Returns:
            Number of fields successfully created
        """
        # Get appropriate field definitions based on asset type
        # Computer and Laptop use the same field definitions
        if asset_type == "Monitor":
            internal_fields = get_monitor_field_definitions()
        else:
            internal_fields = get_internal_field_definitions()
        
        created_count = 0
        
        print_info(f"Creating {len(missing_field_names)} custom fields...")
        console.print()
        
        for field_name in missing_field_names:
            expected_prefix = internal_fields[field_name]
            
            # Prepare field data for API
            field_data = {
                'name': field_name,
                'element': 'text',  # Default to text field
                'format': 'ANY',
                'field_values': '',
                'show_in_email': True,
                'fieldset_id': fieldset_id
            }
            
            # Create field
            print_info(f"Creating '{field_name}'...")
            
            try:
                response = self.session.post(
                    f"{self.api_url}/api/v1/fields",
                    json=field_data,
                    verify=self.verify_ssl,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'success':
                        payload = result.get('payload', {})
                        field_id = payload.get('id')
                        
                        # Try to get db_column from different possible locations
                        db_column = (
                            payload.get('db_column_name') or 
                            payload.get('db_column') or
                            result.get('db_column_name') or
                            'Created'
                        )
                        print_ok(f"Created '{field_name}' → {db_column}")
                        
                        # Now associate the field with the fieldset explicitly
                        if field_id:
                            self._associate_field_with_fieldset(field_id, fieldset_id, field_name)
                        
                        created_count += 1
                    else:
                        messages = result.get('messages', result.get('message', 'Unknown error'))
                        print_error(f"Failed to create '{field_name}': {messages}")
                else:
                    print_error(f"Failed to create '{field_name}': HTTP {response.status_code}")
                    
            except Exception as e:
                print_error(f"Error creating '{field_name}': {e}")
        
        console.print()
        if created_count > 0:
            print_ok(f"Successfully created {created_count}/{len(missing_field_names)} custom fields")
        else:
            print_warning("No fields were created")
        
        return created_count
    
    def _associate_field_with_fieldset(self, field_id: int, fieldset_id: int, field_name: str) -> bool:
        """
        Associate a custom field with a fieldset
        
        Args:
            field_id: Custom field ID
            fieldset_id: Fieldset ID
            field_name: Field name (for display purposes)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.post(
                f"{self.api_url}/api/v1/fields/{field_id}/associate",
                json={'fieldset_id': fieldset_id},
                verify=self.verify_ssl,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    messages = result.get('messages', '')
                    # Check if field was already associated
                    if 'already' in str(messages).lower():
                        print_info(f"  → Already in fieldset #{fieldset_id}")
                    else:
                        print_ok(f"  → Associated with fieldset #{fieldset_id}")
                    return True
                else:
                    messages = result.get('messages', result.get('message', 'Unknown'))
                    # If already associated, that's actually okay
                    if 'already' in str(messages).lower():
                        print_info(f"  → Already in fieldset #{fieldset_id}")
                        return True
                    else:
                        print_warning(f"  → {messages}")
                        return False
            else:
                print_warning(f"  → Association failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print_warning(f"  → Association error: {e}")
            return False
    
    def _step_review_and_create_custom_fields(self, fieldset_id: int, asset_type: str = "Laptop") -> bool:
        """Review, validate, and create custom fields for computer or monitor"""
        print_header(f"{asset_type} Custom Fields Setup")
        console.print()
        
        print_info("Fetching custom fields from Snipe-IT...")
        data = self._api_get('fields', {'limit': 500})
        
        if not data:
            print_warning("Could not fetch custom fields")
            return True  # Continue anyway
        
        fields = data.get('rows', [])
        
        # Get appropriate field definitions based on asset type
        if asset_type == "Monitor":
            internal_fields = get_monitor_field_definitions()
        else:
            internal_fields = get_internal_field_definitions()
        
        # Validate existing fields
        if fields:
            console.print()
            print_ok(f"Found {len(fields)} custom fields in Snipe-IT")
            validation_results = self._validate_custom_fields(fields, internal_fields, asset_type)
        else:
            console.print()
            print_warning("No custom fields found in Snipe-IT")
            validation_results = {}
        
        # Find missing fields
        existing_field_names = [f.get('name') for f in fields]
        missing_fields = []
        for field_name in internal_fields.keys():
            if field_name not in existing_field_names:
                missing_fields.append(field_name)
        
        # Build summary
        matched_count = len([f for f in fields if f.get('name') in internal_fields and validation_results.get(f.get('db_column_name', ''), '').startswith('[OK]')])
        warning_count = sum(1 for v in validation_results.values() if v.startswith('[WARN]'))
        missing_count = len(missing_fields)
        
        console.print()
        print_info(f"Validation Summary:")
        console.print(f"  [green][OK][/green] Matched: {matched_count}")
        if warning_count > 0:
            console.print(f"  [yellow][WARN][/yellow] Mismatches: {warning_count}")
        if missing_count > 0:
            console.print(f"  [yellow][!][/yellow] Missing: {missing_count}")
        
        console.print()
        
        # Display validation table if requested
        if fields and prompt_yes_no("Display custom fields with validation?", default=True):
            console.print()
            display_custom_fields_table(fields, validation_results)
            console.print()
        
        # Only prompt for field association if there are warnings or missing fields
        # If all fields are matched correctly, skip the association prompt
        has_issues = warning_count > 0 or missing_count > 0
        
        if has_issues:
            # Find all existing fields that match our requirements
            fields_to_associate = []
            for field in fields:
                field_name = field.get('name')
                field_id = field.get('id')
                if field_name in internal_fields:
                    fields_to_associate.append((field_id, field_name))
            
            # Offer to associate existing fields
            if fields_to_associate:
                console.print()
                asset_types_msg = "all computer categories (Laptop, Desktop, Server)" if asset_type == "Laptop" else "Monitor category"
                print_info(f"Found {len(fields_to_associate)} existing fields for {asset_types_msg}:")
                for _, fname in fields_to_associate:
                    console.print(f"  • {fname}")
                console.print()
                
                if prompt_yes_no(f"Associate these fields with fieldset #{fieldset_id}?", default=True):
                    console.print()
                    print_info(f"Associating fields with fieldset for {asset_types_msg}...")
                    console.print("(Note: Fields already in the fieldset will be skipped)")
                    console.print()
                    associated_count = 0
                    for field_id, field_name in fields_to_associate:
                        print_info(f"Associating '{field_name}'...")
                        if self._associate_field_with_fieldset(field_id, fieldset_id, field_name):
                            associated_count += 1
                    
                    console.print()
                    if associated_count > 0:
                        print_ok(f"Successfully associated {associated_count}/{len(fields_to_associate)} fields")
        else:
            # All fields matched perfectly - silently skip association prompt
            print_ok(f"All {asset_type.lower()} fields validated successfully!")
        
        # Show missing fields
        if missing_fields:
            console.print()
            print_warning(f"Missing {len(missing_fields)} required custom fields:")
            console.print()
            
            # Display missing fields table
            missing_rows = []
            for field_name in missing_fields:
                expected_prefix = internal_fields[field_name]
                missing_rows.append([field_name, expected_prefix + '*'])
            
            display_table(
                title="Missing Custom Fields",
                columns=["Field Name", "Expected DB Column"],
                rows=missing_rows
            )
            console.print()
            
            # Ask if user wants to create them
            if prompt_yes_no("Create missing custom fields now?", default=True):
                console.print()
                created_count = self._create_missing_fields(missing_fields, fieldset_id, asset_type)
                
                if created_count > 0:
                    # Re-fetch and validate
                    console.print()
                    print_info("Re-fetching custom fields...")
                    data = self._api_get('fields', {'limit': 500})
                    
                    if data:
                        fields = data.get('rows', [])
                        print_ok(f"Now showing {len(fields)} custom fields")
                        
                        # Re-validate
                        validation_results = self._validate_custom_fields(fields, internal_fields, asset_type)
                        
                        console.print()
                        if prompt_yes_no("Display updated custom fields?", default=True):
                            console.print()
                            display_custom_fields_table(fields, validation_results)
        else:
            print_ok(f"All required {asset_type.lower()} custom fields exist!")
        
        return True
    
    def _update_config_with_actual_fields(self, config: Dict[str, Any]) -> None:
        """
        Update config with actual db_column names from Snipe-IT
        
        Args:
            config: Configuration dictionary to update
        """
        # Mapping of laptop field display names to config keys
        laptop_field_name_to_config_key = {
            'Operating System': 'operating_system',
            'OS Install Date': 'os_install_date',
            'Memory / RAM': 'memory_ram',
            'RAM Usage': 'ram_usage',
            'BIOS Release Date': 'bios_release_date',
            'IP Address': 'ip_address',
            'Processor / CPU': 'processor_cpu',
            'Windows Username': 'username',
            'MAC Address': 'mac_address',
            'Total Storage': 'total_storage',
            'Storage Information': 'storage_information',
            'Disk Space Used': 'disk_space_used',
            'Agent Version': 'agent_version',
            'CPU Temperature': 'cpu_temperature',
            'Uptime': 'system_uptime',
            'Screen Size': 'screen_size'
        }
        
        # Mapping of monitor field display names to config keys
        monitor_field_name_to_config_key = {
            'Resolution': 'resolution',
            'Native Resolution': 'native_resolution',
            'Refresh Rate': 'refresh_rate',
            'Connection Interface': 'connection_interface',
            'Bit Depth': 'bit_depth',
            'Monitor Screen Size': 'monitor_screen_size'
        }
        
        # Update laptop fields
        for field_name, actual_db_column in self.actual_field_mappings.items():
            config_key = laptop_field_name_to_config_key.get(field_name)
            if not config_key:
                continue
            
            # Find the field in config structure
            if config_key in config['custom_fields']['basic_system_fields']:
                config['custom_fields']['basic_system_fields'][config_key]['db_column'] = actual_db_column
            elif config_key in config['custom_fields']['optional_fields']:
                config['custom_fields']['optional_fields'][config_key]['db_column'] = actual_db_column
            elif config_key in config['custom_fields']['monitor_fields']:
                config['custom_fields']['monitor_fields'][config_key]['db_column'] = actual_db_column
        
        # Update monitor fields
        for field_name, actual_db_column in self.actual_monitor_field_mappings.items():
            config_key = monitor_field_name_to_config_key.get(field_name)
            if not config_key:
                continue
            
            # Monitor fields should be in monitor_custom_fields section
            if 'monitor_custom_fields' in config and config_key in config['monitor_custom_fields']:
                config['monitor_custom_fields'][config_key]['db_column'] = actual_db_column
    
    def _step_generate_config(
        self, 
        company_id: int, 
        laptop_category_id: int,
        desktop_category_id: int,
        server_category_id: int,
        laptop_fieldset_id: int,
        monitor_category_id: int,
        monitor_fieldset_id: int,
        status_id: int,
        naming_convention: str = "",
        monitor_naming_convention: str = ""
    ) -> bool:
        """Generate and save configuration"""
        print_header("Generating Configuration")
        console.print()
        
        print_info("Creating configuration file...")
        
        try:
            # Check if build secrets exist (hardcoded credentials)
            has_build_secrets = False
            try:
                from core.build_secrets import BUILD_SERVER_URL, BUILD_API_KEY
                if BUILD_SERVER_URL and BUILD_API_KEY:
                    has_build_secrets = True
                    print_info("Build-time credentials detected - server config will be skipped")
            except (ImportError, AttributeError):
                pass
            
            # Create config from template
            config = create_default_config()
            
            # Update server config only if no build secrets
            if has_build_secrets:
                # Remove server section since credentials are hardcoded
                config['server'] = {
                    '# NOTE': 'Server URL and API key are hardcoded in the executable',
                    '# NOTE2': 'To update credentials, rebuild with: python build.py --url URL --api-key KEY'
                }
            else:
                # Update with user selections
                config['server']['url'] = self.api_url
                config['server']['api_key'] = self.api_key
                config['server']['verify_ssl'] = self.verify_ssl
            
            config['defaults']['company_id'] = company_id
            config['defaults']['status_id'] = status_id
            
            # Computer-specific settings (laptop, desktop, and server)
            config['defaults']['laptop_category_id'] = laptop_category_id
            config['defaults']['desktop_category_id'] = desktop_category_id
            config['defaults']['server_category_id'] = server_category_id
            config['defaults']['laptop_fieldset_id'] = laptop_fieldset_id
            
            # Monitor-specific settings
            config['defaults']['monitor_category_id'] = monitor_category_id
            config['defaults']['monitor_fieldset_id'] = monitor_fieldset_id
            
            # Asset tag naming conventions
            config['defaults']['naming_convention'] = naming_convention
            config['defaults']['monitor_naming_convention'] = monitor_naming_convention
            
            # Update db_columns with actual values from Snipe-IT
            total_mappings = len(self.actual_field_mappings) + len(self.actual_monitor_field_mappings)
            if total_mappings > 0:
                print_info("Mapping custom fields to configuration...")
                self._update_config_with_actual_fields(config)
                print_ok(f"Mapped {len(self.actual_field_mappings)} computer field(s)")
                print_ok(f"Mapped {len(self.actual_monitor_field_mappings)} monitor field(s)")
            
            # Save configuration
            self.config_manager.save(config)
            
            print_ok(f"Configuration saved: {self.config_manager.config_path}")
            return True
            
        except Exception as e:
            print_error(f"Failed to save configuration: {e}")
            return False
    
    def _display_success(self) -> None:
        """Display success message"""
        console.print()
        print_header("Setup Complete!")
        console.print()
        
        print_ok(f"Configuration file created: {self.config_manager.config_path}")
        console.print()
        
        console.print("[bold]Next steps:[/bold]")
        console.print(f"  1. Test:  [cyan]Sniper-IT-Agent.exe --test[/cyan]")
        console.print(f"  2. Run:   [cyan]Sniper-IT-Agent.exe[/cyan]")
        console.print()
        console.print("[dim]You can edit config.yaml manually if needed[/dim]")
        console.print()


def run_interactive_setup(verify_ssl: bool = True) -> bool:
    """
    Entry point for setup wizard
    
    Args:
        verify_ssl: Whether to verify SSL certificates (False to ignore SSL errors)
    
    Returns:
        True if setup completed successfully
    """
    setup = SetupManager(verify_ssl=verify_ssl)
    return setup.run_setup()
