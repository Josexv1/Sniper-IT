"""
Sniper-IT Agent - Monitor Manager
Handles monitor asset operations in Snipe-IT
"""

import re
from typing import Dict, Any, Optional, List
from core.api_client import SnipeITClient
from cli.formatters import print_info, print_error, print_warning, console
from core.constants import STATUS_OK, STATUS_ERROR, STATUS_WARNING, STATUS_INFO
from utils.exceptions import APIError
from utils.logger import get_logger


class MonitorManager:
    """
    Manages monitor asset operations
    - Create/update monitor assets
    - Handle monitor-specific fields
    - Link monitors to parent laptop/desktop
    """
    
    def __init__(self, api_client: SnipeITClient, config: Dict[str, Any]):
        """
        Initialize monitor manager
        
        Args:
            api_client: Snipe-IT API client instance
            config: Configuration dictionary
        """
        self.api = api_client
        self.config = config
        self.defaults = config.get('defaults', {})
        self.logger = get_logger()
        
    def _map_monitor_fields_to_payload(self, monitor_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Map monitor custom fields to database column names
        
        Args:
            monitor_data: Monitor data dictionary
            
        Returns:
            Dictionary with db_column names as keys
        """
        payload = {}
        
        # Get monitor field configuration
        monitor_fields_config = self.config.get('monitor_custom_fields', {})
        
        # Build field mapping (internal_name -> db_column)
        field_mapping = {
            'resolution': monitor_fields_config.get('resolution', {}).get('db_column', ''),
            'native_resolution': monitor_fields_config.get('native_resolution', {}).get('db_column', ''),
            'refresh_rate': monitor_fields_config.get('refresh_rate', {}).get('db_column', ''),
            'connection_interface': monitor_fields_config.get('connection_interface', {}).get('db_column', ''),
            'bit_depth': monitor_fields_config.get('bit_depth', {}).get('db_column', ''),
            'monitor_screen_size': monitor_fields_config.get('monitor_screen_size', {}).get('db_column', '')
        }
        
        # Map the fields
        for field_name, db_column in field_mapping.items():
            if db_column and field_name in monitor_data:
                value = monitor_data[field_name]
                if value and str(value).strip() and str(value).lower() != 'n/a':
                    payload[db_column] = str(value)
        
        return payload
    
    def _generate_monitor_name(self, monitor_data: Dict[str, Any], index: int) -> str:
        """
        Generate a descriptive name for the monitor asset
        
        Args:
            monitor_data: Monitor data dictionary
            index: Monitor index (unused - kept for compatibility)
            
        Returns:
            Monitor name string
        """
        manufacturer = monitor_data.get('manufacturer', 'Unknown')
        model = monitor_data.get('model', 'Monitor')
        
        # Check if model already contains manufacturer name
        # If so, just use the model to avoid duplication (e.g., "HP M24fe FHD" not "HP HP M24fe FHD")
        model_lower = model.lower()
        manufacturer_lower = manufacturer.lower()
        
        if manufacturer_lower in model_lower:
            # Model already contains manufacturer, just use model
            return model
        else:
            # Model doesn't contain manufacturer, prepend it
            return f"{manufacturer} {model}"
    
    def process_monitors(self, monitors: List[Dict[str, Any]], 
                        parent_hostname: str,
                        parent_asset_id: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Process multiple monitor assets
        
        Args:
            monitors: List of monitor data dictionaries
            parent_hostname: Hostname of the laptop/desktop these monitors are connected to
            parent_asset_id: Optional asset ID of parent laptop to checkout monitors to
            
        Returns:
            List of processing results or None if failed
        """
        if not monitors:
            self.logger.verbose(f"{STATUS_INFO} No external monitors detected")
            return []
        
        self.logger.verbose("")
        self.logger.verbose(f"{STATUS_INFO} Processing {len(monitors)} monitor(s)...")
        self.logger.verbose("=" * 70)
        
        results = []
        
        for i, monitor_data in enumerate(monitors, start=1):
            self.logger.verbose(f"\n{STATUS_INFO} Processing Monitor {i}/{len(monitors)}")
            self.logger.verbose("-" * 70)
            
            result = self._process_single_monitor(monitor_data, i, parent_hostname, parent_asset_id)
            
            if result:
                results.append(result)
            else:
                self.logger.verbose(f"{STATUS_WARNING} Monitor {i} processing had issues")
        
        self.logger.verbose("")
        self.logger.verbose("=" * 70)
        self.logger.verbose(f"{STATUS_OK} Monitor processing completed: {len(results)}/{len(monitors)} successful")
        self.logger.verbose("")
        
        return results
    
    def _process_single_monitor(self, monitor_data: Dict[str, Any], 
                                index: int, parent_hostname: str,
                                parent_asset_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Process a single monitor asset
        
        Args:
            monitor_data: Monitor data dictionary
            index: Monitor index
            parent_hostname: Parent laptop hostname
            parent_asset_id: Optional asset ID of parent laptop to checkout to
            
        Returns:
            Processing result dictionary or None if failed
        """
        try:
            # Extract core data
            manufacturer = monitor_data.get('manufacturer', 'Unknown')
            model = monitor_data.get('model', 'Unknown Monitor')
            serial = monitor_data.get('serial_number', '')
            resolution = monitor_data.get('resolution', 'N/A')
            
            self.logger.verbose(f"  Manufacturer: {manufacturer}")
            self.logger.verbose(f"  Model: {model}")
            self.logger.verbose(f"  Serial: {serial if serial else '(empty)'}")
            self.logger.verbose(f"  Resolution: {resolution}")
            
            # Generate monitor name
            monitor_name = self._generate_monitor_name(monitor_data, index)
            
            # Step 1: Find or create manufacturer
            self.logger.verbose(f"  {STATUS_INFO} Processing manufacturer...")
            manufacturer_id = self.api.find_or_create_manufacturer(manufacturer)
            self.logger.verbose(f"  {STATUS_OK} Manufacturer ID: {manufacturer_id}")
            
            # Step 2: Find or create model
            self.logger.verbose(f"  {STATUS_INFO} Processing model...")
            model_id = self.api.find_or_create_model(
                name=model,
                model_number=model,
                manufacturer_id=manufacturer_id,
                category_id=self.defaults.get('monitor_category_id', 5),
                fieldset_id=self.defaults.get('monitor_fieldset_id', 2)
            )
            self.logger.verbose(f"  {STATUS_OK} Model ID: {model_id}")
            
            # Step 3: Search for existing monitor
            # Search by serial if available, otherwise by name
            existing_asset_id = None
            
            if serial and serial.strip():
                # Search by serial
                search_results = self.api.search_hardware(serial, limit=50)
                for asset in search_results:
                    if asset.get('serial', '').lower() == serial.lower():
                        existing_asset_id = asset['id']
                        break
            
            if not existing_asset_id:
                # Search by name as fallback
                search_results = self.api.search_hardware(monitor_name, limit=50)
                for asset in search_results:
                    if asset.get('name', '').lower() == monitor_name.lower():
                        existing_asset_id = asset['id']
                        break
            
            # Step 4: Prepare payload
            payload = {
                'name': monitor_name,
                'serial': serial if serial else f"N/A-{manufacturer[:10]}-{model[:10]}",
                'model_id': model_id,
                'status_id': self.defaults.get('status_id', 2),
                'company_id': self.defaults.get('company_id', 1)
            }
            
            # Add monitor-specific custom fields
            monitor_field_payload = self._map_monitor_fields_to_payload(monitor_data)
            payload.update(monitor_field_payload)
            
            # Step 5: Create or update asset
            if existing_asset_id:
                self.logger.verbose(f"  {STATUS_OK} Found existing monitor ID: {existing_asset_id}")
                
                # Get existing data to preserve asset_tag and detect changes
                existing_data = self.api.get_hardware_by_id(existing_asset_id)
                existing_tag = existing_data.get('asset_tag', '')
                
                # Generate or preserve asset tag based on naming convention
                payload['asset_tag'] = self._generate_or_preserve_monitor_asset_tag(serial, existing_tag)
                self.logger.verbose(f"  {STATUS_INFO} Preserving asset tag: {payload['asset_tag']}")
                
                # Check if update is needed
                has_changes = self._detect_monitor_changes(existing_data, payload, model_id)
                
                if not has_changes:
                    self.logger.verbose(f"  {STATUS_OK} No changes detected - monitor is already up to date")
                    asset_id = existing_asset_id
                    action = 'no_change'
                else:
                    self.logger.verbose(f"  {STATUS_INFO} Changes detected - updating monitor...")
                    result = self.api.update_hardware(existing_asset_id, payload)
                    
                    if result.get('status') == 'success':
                        self.logger.verbose(f"  {STATUS_OK} Monitor updated successfully")
                        asset_id = existing_asset_id
                        action = 'updated'
                        
                        # Verify asset tag was preserved
                        updated_data = self.api.get_hardware_by_id(asset_id)
                        updated_tag = updated_data.get('asset_tag', '')
                        if updated_tag and updated_tag != existing_tag:
                            self.logger.verbose(f"  {STATUS_WARNING} Asset tag changed: {existing_tag} -> {updated_tag}")
                        elif updated_tag:
                            self.logger.verbose(f"  {STATUS_OK} Asset tag verified: {updated_tag}")
                    else:
                        print_error(f"Update failed: {result.get('messages', 'Unknown error')}")
                        return None
            else:
                self.logger.verbose(f"  {STATUS_INFO} Creating new monitor...")
                # Generate asset tag based on naming convention
                payload['asset_tag'] = self._generate_monitor_asset_tag(serial)
                self.logger.verbose(f"  {STATUS_INFO} Generated asset tag: {payload['asset_tag']}")
                
                result = self.api.create_hardware(payload)
                
                if result.get('status') == 'success':
                    asset_id = result['payload']['id']
                    self.logger.verbose(f"  {STATUS_OK} Monitor created (ID: {asset_id})")
                    action = 'created'
                else:
                    print_error(f"Creation failed: {result.get('messages', 'Unknown error')}")
                    return None
            
            # Step 6: Checkout monitor to user (if parent asset is provided)
            assigned_user_id = None
            assigned_user_name = None
            if parent_asset_id:
                try:
                    # Get parent asset details to find the assigned user
                    self.logger.verbose(f"  {STATUS_INFO} Retrieving parent asset details...")
                    parent_asset = self.api.get_hardware_by_id(parent_asset_id)
                    
                    # Check if parent asset is assigned to a user
                    assigned_to = parent_asset.get('assigned_to')
                    if assigned_to and assigned_to.get('type') == 'user':
                        assigned_user_id = assigned_to.get('id')
                        assigned_user_name = assigned_to.get('name', 'Unknown User')
                        
                        # Check if monitor is already checked out to the correct user
                        monitor_data = self.api.get_hardware_by_id(asset_id)
                        monitor_assigned_to = monitor_data.get('assigned_to')
                        
                        # Check if already assigned to the same user
                        already_correct = False
                        if monitor_assigned_to and monitor_assigned_to.get('type') == 'user':
                            current_user_id = monitor_assigned_to.get('id')
                            if current_user_id == assigned_user_id:
                                already_correct = True
                                self.logger.verbose(f"  {STATUS_INFO} Monitor already checked out to correct user: {assigned_user_name}")
                        
                        # Only perform checkout if not already correct
                        if not already_correct:
                            # Check in first if currently checked out to someone else
                            if monitor_assigned_to:
                                self.logger.verbose(f"  {STATUS_INFO} Monitor checked out to different user - checking in first...")
                                checkin_result = self.api.checkin_hardware(
                                    asset_id=asset_id,
                                    note="Auto-checkin before reassignment"
                                )
                                if checkin_result.get('status') == 'success':
                                    self.logger.verbose(f"  {STATUS_OK} Monitor checked in successfully")
                                else:
                                    self.logger.verbose(f"  {STATUS_WARNING} Checkin warning: {checkin_result.get('messages', 'Unknown')}")
                            
                            self.logger.verbose(f"  {STATUS_INFO} Checking out monitor to user: {assigned_user_name}...")
                            
                            # Create note with device connection info
                            checkout_note = f"Connected to {parent_hostname} (Asset #{parent_asset_id})"
                            
                            checkout_result = self.api.checkout_hardware(
                                asset_id=asset_id,
                                checkout_to_type='user',
                                assigned_id=assigned_user_id,
                                status_id=self.defaults.get('status_id', 2),
                                note=checkout_note
                            )
                            
                            if checkout_result.get('status') == 'success':
                                self.logger.verbose(f"  {STATUS_OK} Monitor checked out to user: {assigned_user_name}")
                                self.logger.verbose(f"  {STATUS_INFO} Checkout note added: '{checkout_note}'")
                                self.logger.verbose(f"  {STATUS_INFO} (View in Snipe-IT History tab for this asset)")
                            else:
                                self.logger.verbose(f"  {STATUS_WARNING} Checkout warning: {checkout_result.get('messages', 'Unknown')}")
                    else:
                        self.logger.verbose(f"  {STATUS_WARNING} Parent asset not assigned to a user - skipping checkout")
                        self.logger.verbose(f"  {STATUS_INFO} Note: Monitor will remain unassigned until parent is assigned to a user")
                        
                except Exception as e:
                    self.logger.verbose(f"  {STATUS_WARNING} Checkout failed: {e}")
            
            return {
                'asset_id': asset_id,
                'name': monitor_name,
                'manufacturer': manufacturer,
                'model': model,
                'serial': serial,
                'manufacturer_id': manufacturer_id,
                'model_id': model_id,
                'action': action,
                'parent_hostname': parent_hostname,
                'parent_asset_id': parent_asset_id,
                'checked_out_to_user': assigned_user_id,
                'checked_out_to_user_name': assigned_user_name
            }
            
        except APIError as e:
            print_error(f"API error: {e}")
            return None
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            return None
    
    def _detect_monitor_changes(self, existing_data: Dict[str, Any], new_payload: Dict[str, Any], new_model_id: int) -> bool:
        """
        Detect if monitor data has changed
        
        Args:
            existing_data: Existing monitor data from Snipe-IT
            new_payload: New payload to be sent
            new_model_id: New model ID
            
        Returns:
            True if changes detected, False if monitor is already up to date
        """
        # Check name change
        existing_name = existing_data.get('name', '')
        new_name = new_payload.get('name', '')
        if existing_name != new_name:
            return True
        
        # Check model change
        existing_model_id = existing_data.get('model', {}).get('id')
        if existing_model_id and existing_model_id != new_model_id:
            return True
        
        # Check serial change
        existing_serial = existing_data.get('serial', '')
        new_serial = new_payload.get('serial', '')
        if existing_serial != new_serial:
            return True
        
        # Check custom fields changes
        existing_custom_fields = existing_data.get('custom_fields', {})
        
        for field_key, field_value in new_payload.items():
            if field_key.startswith('_snipeit_'):
                # Find matching field in existing data
                existing_value = None
                for cf_key, cf_data in existing_custom_fields.items():
                    if cf_data.get('field') == field_key:
                        existing_value = cf_data.get('value', '')
                        break
                
                # Compare values (normalize to strings)
                if str(existing_value or '') != str(field_value or ''):
                    return True
        
        return False
    
    def _generate_or_preserve_monitor_asset_tag(self, serial: str, existing_tag: str = '') -> str:
        """
        Generate monitor asset tag based on naming convention or preserve existing valid tag.
        
        Args:
            serial: Monitor serial number to use as fallback
            existing_tag: Existing asset tag (if updating a monitor)
            
        Returns:
            Asset tag string (e.g., MIS-MON-0027 or serial number)
        """
        naming_convention = self.defaults.get('monitor_naming_convention', '').strip()
        
        # If no naming convention, use serial number
        if not naming_convention:
            return serial
        
        # Check if existing tag matches the naming convention pattern
        if existing_tag and self._tag_matches_pattern(existing_tag, naming_convention):
            self.logger.debug(f"{STATUS_INFO} Preserving existing monitor asset tag: {existing_tag}")
            return existing_tag
        
        # Generate new tag
        return self._generate_monitor_asset_tag(serial)
    
    def _generate_monitor_asset_tag(self, serial: str) -> str:
        """
        Generate new monitor asset tag based on naming convention.
        
        Args:
            serial: Monitor serial number to use as fallback
            
        Returns:
            Generated asset tag string (e.g., MIS-MON-0027)
        """
        naming_convention = self.defaults.get('monitor_naming_convention', '').strip()
        
        # If no naming convention, use serial
        if not naming_convention:
            return serial
        
        # Find the last asset with this naming pattern
        try:
            self.logger.debug(f"{STATUS_INFO} Searching for monitor assets with pattern: {naming_convention}")
            last_tag = self._find_last_monitor_asset_tag(naming_convention)
            
            if last_tag:
                # Extract number and increment
                current_number = self._extract_number_from_tag(last_tag, naming_convention)
                next_number = current_number + 1
                
                # Determine padding from pattern or last tag
                num_digits = len(str(current_number))
                new_tag = naming_convention.replace('N', str(next_number).zfill(num_digits))
                
                self.logger.debug(f"{STATUS_INFO} Found last monitor tag: {last_tag} (#{current_number})")
                self.logger.debug(f"{STATUS_INFO} Generated new monitor tag: {new_tag} (#{next_number})")
                return new_tag
            else:
                # No existing assets found - start with 0001
                new_tag = naming_convention.replace('N', '0001')
                self.logger.debug(f"{STATUS_INFO} No existing monitor tags found, starting with: {new_tag}")
                return new_tag
                
        except Exception as e:
            self.logger.verbose(f"{STATUS_WARNING} Monitor asset tag generation failed: {e}")
            self.logger.verbose(f"{STATUS_INFO} Falling back to serial number")
            return serial
    
    def _tag_matches_pattern(self, tag: str, pattern: str) -> bool:
        """
        Check if an asset tag matches the naming convention pattern.
        
        Args:
            tag: Asset tag to check (e.g., 'MIS-MON-0027')
            pattern: Pattern with 'N' placeholder (e.g., 'MIS-MON-N')
            
        Returns:
            True if tag matches pattern, False otherwise
        """
        if not tag or not pattern:
            return False
        
        # Convert pattern to regex
        regex_pattern = re.escape(pattern).replace('N', r'(\d+)')
        return bool(re.fullmatch(regex_pattern, tag))
    
    def _find_last_monitor_asset_tag(self, pattern: str) -> Optional[str]:
        """
        Find the last monitor asset tag matching the naming pattern
        
        Args:
            pattern: Naming pattern with 'N' placeholder (e.g., 'MIS-MON-N')
            
        Returns:
            Last matching asset tag or None if not found
        """
        # Convert pattern to search query (replace N with wildcard)
        # For pattern "MIS-MON-N" we search for "MIS-MON"
        search_prefix = pattern.split('N')[0]
        
        self.logger.debug(f"{STATUS_INFO} Searching for monitor asset tags starting with: {search_prefix}")
        
        # Search for assets with this prefix
        # Note: Snipe-IT search is limited, so we fetch up to 500 assets and filter
        search_results = self.api.search_hardware(search_prefix, limit=500)
        
        self.logger.debug(f"{STATUS_INFO} Found {len(search_results)} assets in search results")
        
        matching_tags = []
        
        # Create regex pattern to match the naming convention
        # Replace 'N' with digit pattern
        regex_pattern = re.escape(pattern).replace('N', r'(\d+)')
        
        for asset in search_results:
            asset_tag = asset.get('asset_tag', '')
            if re.fullmatch(regex_pattern, asset_tag):
                matching_tags.append(asset_tag)
        
        self.logger.debug(f"{STATUS_INFO} Found {len(matching_tags)} monitor assets matching pattern '{pattern}'")
        
        if not matching_tags:
            return None
        
        # Sort by the numeric part and return the last one
        matching_tags.sort(key=lambda tag: self._extract_number_from_tag(tag, pattern))
        
        self.logger.debug(f"{STATUS_INFO} Highest monitor tag in sequence: {matching_tags[-1]}")
        
        return matching_tags[-1]
    
    def _extract_number_from_tag(self, tag: str, pattern: str) -> int:
        """
        Extract the numeric part from an asset tag
        
        Args:
            tag: Asset tag (e.g., 'MIS-MON-0027')
            pattern: Pattern with 'N' (e.g., 'MIS-MON-N')
            
        Returns:
            Extracted number as integer
        """
        regex_pattern = re.escape(pattern).replace('N', r'(\d+)')
        match = re.fullmatch(regex_pattern, tag)
        
        if match:
            return int(match.group(1))
        return 0
