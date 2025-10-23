"""
Sniper-IT Agent - Asset Manager
Handles laptop/desktop asset operations in Snipe-IT
"""

import re
from typing import Dict, Any, Optional
from core.api_client import SnipeITClient
from cli.formatters import (print_info, print_error, print_warning, console,
                             print_section, print_step, print_subsection)
from core.constants import STATUS_OK, STATUS_ERROR, STATUS_WARNING, STATUS_INFO
from utils.exceptions import APIError
from utils.logger import get_logger


class AssetManager:
    """
    Manages laptop/desktop asset operations
    - Find/create manufacturers and models
    - Create/update assets
    - Map custom fields to Snipe-IT format
    """
    
    def __init__(self, api_client: SnipeITClient, config: Dict[str, Any]):
        """
        Initialize asset manager
        
        Args:
            api_client: Snipe-IT API client instance
            config: Configuration dictionary
        """
        self.api = api_client
        self.config = config
        self.defaults = config.get('defaults', {})
        self.logger = get_logger()
        
    def _map_custom_fields_to_payload(self, custom_fields: Dict[str, str]) -> Dict[str, str]:
        """
        Map custom field display names to database column names
        
        Args:
            custom_fields: Dictionary with display names as keys
            
        Returns:
            Dictionary with db_column names as keys
        """
        payload = {}
        
        # Get field configuration - ONLY use basic_system_fields for laptops
        # Optional fields may not be in the fieldset
        basic_fields = self.config.get('custom_fields', {}).get('basic_system_fields', {})
        
        # Build display_name -> db_column mapping
        field_mapping = {}
        for field_key, field_config in basic_fields.items():
            if field_config.get('enabled', False):
                display_name = field_config.get('display_name', '')
                db_column = field_config.get('db_column', '')
                if display_name and db_column:
                    field_mapping[display_name] = db_column
        
        # Map the custom fields
        for display_name, value in custom_fields.items():
            if display_name in field_mapping:
                db_column = field_mapping[display_name]
                payload[db_column] = str(value)
        
        return payload
    
    def process_asset(self, system_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process laptop/desktop/server asset end-to-end
        
        Args:
            system_data: Dictionary containing:
                - system_data: Core system information
                - custom_fields: Custom field data
                - os_type: Operating system type
                - asset_type: Asset type ("laptop", "desktop", or "server")
                
        Returns:
            Dictionary with processing results or None if failed
        """
        try:
            # Extract data
            asset_data = system_data['system_data']
            custom_fields = system_data['custom_fields']
            asset_type = system_data.get('asset_type', 'desktop')  # "laptop", "desktop", or "server"
            
            hostname = asset_data.get('hostname', 'Unknown')
            manufacturer = asset_data.get('manufacturer', 'Unknown')
            model = asset_data.get('model', 'Unknown')
            serial = asset_data.get('serial_number', 'Unknown')
            
            # Capitalize for display
            asset_type_display = asset_type.capitalize()
            
            # Show section header
            print_section(f"SYNCING {asset_type_display.upper()} ASSET")
            
            # Check if serial is valid (not a placeholder)
            is_serial_valid = self._is_serial_valid(serial)
            if not is_serial_valid and self.logger.verbosity >= 2:
                console.print(f"  [yellow]⚠ Serial appears invalid, will use hostname as serial[/yellow]")
            
            # Find or create manufacturer
            self.logger.debug("")
            print_step(f"Processing manufacturer: {manufacturer}", "processing")
            manufacturer_id = self.api.find_or_create_manufacturer(manufacturer)
            print_step(f"Manufacturer ID: {manufacturer_id}", "ok")
            
            # Find or create model (using appropriate category based on asset type)
            print_step(f"Processing model: {model}", "processing")
            
            # Select category based on asset type
            if asset_type == 'laptop':
                category_id = self.defaults.get('laptop_category_id', 2)
            elif asset_type == 'server':
                category_id = self.defaults.get('server_category_id', 4)
            else:  # desktop
                category_id = self.defaults.get('desktop_category_id', 3)
            
            model_id = self.api.find_or_create_model(
                name=model,
                model_number=model,  # Use model name as model number
                manufacturer_id=manufacturer_id,
                category_id=category_id,
                fieldset_id=self.defaults.get('laptop_fieldset_id', 1)
            )
            print_info(f"Model ID: {model_id}")
            
            # Search for existing asset
            print_subsection(f"Searching for existing asset: {hostname}")
            existing_asset_id = self.api.find_hardware_by_hostname(hostname)
            
            # Prepare payload
            # Use hostname as serial for assets with invalid serials (mostly desktops)
            # This ensures uniqueness since all machines are domain-joined
            effective_serial = serial if is_serial_valid else hostname
            self.logger.debug(f"    Effective serial: {effective_serial}")
            
            payload = {
                'name': hostname,
                'serial': effective_serial,
                'model_id': model_id,
                'status_id': self.defaults.get('status_id', 2),
                'company_id': self.defaults.get('company_id', 1)
            }
            
            # Add custom fields
            custom_field_payload = self._map_custom_fields_to_payload(custom_fields)
            payload.update(custom_field_payload)
            
            # Create or update asset
            if existing_asset_id:
                self.logger.debug(f"  [green]✓[/green] Found existing asset ID: {existing_asset_id}")
                
                # Get existing data to check category and asset tag
                existing_data = self.api.get_hardware_by_id(existing_asset_id)
                existing_model = existing_data.get('model', {})
                existing_category = existing_model.get('category', {})
                existing_category_id = existing_category.get('id')
                existing_category_name = existing_category.get('name', 'Unknown')
                existing_asset_tag = existing_data.get('asset_tag', '')
                
                # Check if asset is in wrong category
                if existing_category_id and existing_category_id != category_id:
                    self.logger.debug(f"    [yellow]Wrong category:[/yellow] {existing_category_name} → {asset_type_display}")
                
                # Preserve existing asset tag if it matches naming convention, otherwise generate new one
                payload['asset_tag'] = self._generate_or_preserve_asset_tag(hostname, existing_asset_tag)
                self.logger.debug(f"    Asset tag: {payload['asset_tag']}")
                
                # Track changes between existing and new data
                change_info = self._detect_changes(existing_data, payload, model_id)
                changes = change_info['summary']
                detailed_changes = change_info['details']
                
                if not changes:
                    print_step(f"Asset up to date (ID: {existing_asset_id})", "ok")
                    asset_id = existing_asset_id
                    action = 'no_change'
                else:
                    print_step(f"Updating asset with {len(changes)} change(s)", "processing")
                    for change in changes:
                        self.logger.debug(f"    • {change}")
                    
                    result = self.api.update_hardware(existing_asset_id, payload)
                    
                    if result.get('status') == 'success':
                        print_step(f"Asset updated successfully (ID: {existing_asset_id})", "ok")
                        asset_id = existing_asset_id
                        action = 'updated'
                    else:
                        print_error(f"Update failed: {result.get('messages', 'Unknown error')}")
                        return None
            else:
                self.logger.debug(f"  [cyan]ℹ[/cyan] No existing asset found")
                # Generate asset tag based on naming convention
                payload['asset_tag'] = self._generate_asset_tag(hostname)
                self.logger.debug(f"    Generated asset tag: {payload['asset_tag']}")
                
                # For new assets, no changes to track
                changes = []
                detailed_changes = {}
                
                print_step("Creating new asset", "processing")
                result = self.api.create_hardware(payload)
                
                if result.get('status') == 'success':
                    asset_id = result['payload']['id']
                    print_step(f"Asset created successfully (ID: {asset_id})", "ok")
                    action = 'created'
                else:
                    print_error(f"Creation failed: {result.get('messages', 'Unknown error')}")
                    return None
            
            # Verify the asset
            verification = self._verify_asset(asset_id)
            
            # Determine action and changes
            return {
                'asset_id': asset_id,
                'hostname': hostname,
                'manufacturer_id': manufacturer_id,
                'model_id': model_id,
                'verification': verification,
                'action': action,
                'changes': changes,
                'detailed_changes': detailed_changes
            }
            
        except APIError as e:
            print_error(f"API error: {e}")
            return None
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            return None
    
    def _verify_asset(self, asset_id: int) -> Dict[str, Any]:
        """
        Verify asset data was saved correctly
        
        Args:
            asset_id: Asset ID to verify
            
        Returns:
            Verification results dictionary
        """
        try:
            data = self.api.get_hardware_by_id(asset_id)
            
            # Count populated custom fields
            custom_fields = data.get('custom_fields', {})
            populated_count = 0
            total_count = 0
            
            for field_name, field_info in custom_fields.items():
                total_count += 1
                value = field_info.get('value', '')
                if value and str(value).strip():
                    populated_count += 1
            
            success_rate = (populated_count / total_count * 100) if total_count > 0 else 0
            
            self.logger.debug(f"    Custom fields: {populated_count}/{total_count} populated ({success_rate:.1f}%)")
            
            return {
                'asset_id': asset_id,
                'populated_fields': populated_count,
                'total_fields': total_count,
                'success_rate': success_rate,
                'asset_data': data
            }
            
        except Exception as e:
            self.logger.debug(f"    [yellow]Verification warning:[/yellow] {e}")
            return {
                'asset_id': asset_id,
                'error': str(e)
            }
    
    def _generate_or_preserve_asset_tag(self, hostname: str, existing_tag: str = '') -> str:
        """
        Generate asset tag based on naming convention or preserve existing valid tag.
        
        Args:
            hostname: Computer hostname to use as fallback
            existing_tag: Existing asset tag (if updating an asset)
            
        Returns:
            Asset tag string (e.g., MIS-2025-0027)
        """
        naming_convention = self.defaults.get('naming_convention', '').strip()
        
        # If no naming convention, use hostname
        if not naming_convention:
            return hostname
        
        # Check if existing tag matches the naming convention pattern
        if existing_tag and self._tag_matches_pattern(existing_tag, naming_convention):
            self.logger.debug(f"{STATUS_INFO} Preserving existing asset tag: {existing_tag}")
            return existing_tag
        
        # Generate new tag
        return self._generate_asset_tag(hostname)
    
    def _generate_asset_tag(self, hostname: str) -> str:
        """
        Generate new asset tag based on naming convention.
        
        Args:
            hostname: Computer hostname to use as fallback
            
        Returns:
            Generated asset tag string (e.g., MIS-2025-0027)
        """
        naming_convention = self.defaults.get('naming_convention', '').strip()
        
        # If no naming convention, use hostname
        if not naming_convention:
            return hostname
        
        # Find the last asset with this naming pattern
        try:
            self.logger.debug(f"{STATUS_INFO} Searching for assets with pattern: {naming_convention}")
            last_tag = self._find_last_asset_tag(naming_convention)
            
            if last_tag:
                # Extract number and increment
                current_number = self._extract_number_from_tag(last_tag, naming_convention)
                next_number = current_number + 1
                
                # Determine padding from pattern or last tag
                num_digits = len(str(current_number))
                new_tag = naming_convention.replace('N', str(next_number).zfill(num_digits))
                
                self.logger.debug(f"{STATUS_INFO} Found last tag: {last_tag} (#{current_number})")
                self.logger.debug(f"{STATUS_INFO} Generated new tag: {new_tag} (#{next_number})")
                return new_tag
            else:
                # No existing assets found - start with 0001
                new_tag = naming_convention.replace('N', '0001')
                self.logger.debug(f"{STATUS_INFO} No existing tags found, starting with: {new_tag}")
                return new_tag
                
        except Exception as e:
            self.logger.verbose(f"{STATUS_WARNING} Asset tag generation failed: {e}")
            self.logger.verbose(f"{STATUS_INFO} Falling back to hostname")
            return hostname
    
    def _tag_matches_pattern(self, tag: str, pattern: str) -> bool:
        """
        Check if an asset tag matches the naming convention pattern.
        
        Args:
            tag: Asset tag to check (e.g., 'MIS-2025-0027')
            pattern: Pattern with 'N' placeholder (e.g., 'MIS-2025-N')
            
        Returns:
            True if tag matches pattern, False otherwise
        """
        if not tag or not pattern:
            return False
        
        # Convert pattern to regex
        regex_pattern = re.escape(pattern).replace('N', r'(\d+)')
        return bool(re.fullmatch(regex_pattern, tag))
    
    def _find_last_asset_tag(self, pattern: str) -> Optional[str]:
        """
        Find the last asset tag matching the naming pattern
        
        Args:
            pattern: Naming pattern with 'N' placeholder (e.g., 'MIS-2026-N')
            
        Returns:
            Last matching asset tag or None if not found
        """
        # Convert pattern to search query (replace N with wildcard)
        # For pattern "MIS-2026-N" we search for "MIS-2026"
        search_prefix = pattern.split('N')[0]
        
        self.logger.debug(f"{STATUS_INFO} Searching for asset tags starting with: {search_prefix}")
        
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
        
        self.logger.debug(f"{STATUS_INFO} Found {len(matching_tags)} assets matching pattern '{pattern}'")
        
        if not matching_tags:
            return None
        
        # Sort by the numeric part and return the last one
        matching_tags.sort(key=lambda tag: self._extract_number_from_tag(tag, pattern))
        
        self.logger.debug(f"{STATUS_INFO} Highest tag in sequence: {matching_tags[-1]}")
        
        return matching_tags[-1]
    
    def _extract_number_from_tag(self, tag: str, pattern: str) -> int:
        """
        Extract the numeric part from an asset tag
        
        Args:
            tag: Asset tag (e.g., 'MIS-2026-0027')
            pattern: Pattern with 'N' (e.g., 'MIS-2026-N')
            
        Returns:
            Extracted number as integer
        """
        regex_pattern = re.escape(pattern).replace('N', r'(\d+)')
        match = re.fullmatch(regex_pattern, tag)
        
        if match:
            return int(match.group(1))
        return 0
    
    
    def _detect_changes(self, existing_data: Dict[str, Any], new_payload: Dict[str, Any], new_model_id: int) -> Dict[str, Any]:
        """
        Detect changes between existing asset data and new payload.
        
        Args:
            existing_data: Existing asset data from Snipe-IT
            new_payload: New payload to be sent
            new_model_id: New model ID
            
        Returns:
            Dictionary with 'summary' (list of change descriptions) and 'details' (dict of field changes)
        """
        changes = []
        detailed_changes = {}  # Field name -> {old: value, new: value}
        
        # Check model change
        existing_model_id = existing_data.get('model', {}).get('id')
        if existing_model_id and existing_model_id != new_model_id:
            existing_model_name = existing_data.get('model', {}).get('name', 'Unknown')
            changes.append(f"Model changed (was: {existing_model_name})")
            detailed_changes['Model'] = {'old': existing_model_name, 'new': 'Updated'}
        
        # Check asset tag change
        existing_tag = existing_data.get('asset_tag', '')
        new_tag = new_payload.get('asset_tag', '')
        if existing_tag != new_tag:
            changes.append(f"Asset tag changed: {existing_tag} → {new_tag}")
            detailed_changes['Asset Tag'] = {'old': existing_tag, 'new': new_tag}
        
        # Check serial change
        existing_serial = existing_data.get('serial', '')
        new_serial = new_payload.get('serial', '')
        if existing_serial != new_serial:
            changes.append(f"Serial changed: {existing_serial} → {new_serial}")
            detailed_changes['Serial'] = {'old': existing_serial, 'new': new_serial}
        
        # Check status change
        existing_status_id = existing_data.get('status_label', {}).get('id')
        new_status_id = new_payload.get('status_id')
        if existing_status_id and existing_status_id != new_status_id:
            existing_status_name = existing_data.get('status_label', {}).get('name', 'Unknown')
            changes.append(f"Status changed (was: {existing_status_name})")
            detailed_changes['Status'] = {'old': existing_status_name, 'new': 'Updated'}
        
        # Check custom fields changes
        existing_custom_fields = existing_data.get('custom_fields', {})
        custom_field_changes = 0
        
        # Fields to ignore in change detection (volatile data that changes frequently)
        ignored_fields = ['disk_space_used', 'ram_usage']
        
        # Get display name mapping from config
        custom_fields_config = self.config.get('custom_fields', {}).get('basic_system_fields', {})
        db_to_display = {}
        for field_key, field_config in custom_fields_config.items():
            if field_config.get('enabled', False):
                db_column = field_config.get('db_column', '')
                display_name = field_config.get('display_name', '')
                if db_column and display_name:
                    db_to_display[db_column] = display_name
        
        for field_key, field_value in new_payload.items():
            if field_key.startswith('_snipeit_'):
                # Skip ignored fields (disk space, RAM usage, etc.)
                if any(ignored in field_key for ignored in ignored_fields):
                    continue
                
                # Get proper display name from config, fallback to formatted key
                field_display_name = db_to_display.get(field_key, 
                    field_key.replace('_snipeit_', '').replace('_', ' ').title())
                
                # Find matching field in existing data
                existing_value = None
                for cf_key, cf_data in existing_custom_fields.items():
                    if cf_data.get('field') == field_key:
                        existing_value = cf_data.get('value', '')
                        break
                
                # Compare values (normalize to strings)
                existing_str = str(existing_value or '').strip()
                new_str = str(field_value or '').strip()
                
                if existing_str != new_str:
                    custom_field_changes += 1
                    # Store detailed change with proper display name
                    detailed_changes[field_display_name] = {
                        'old': existing_str if existing_str else '(empty)',
                        'new': new_str if new_str else '(empty)'
                    }
        
        if custom_field_changes > 0:
            changes.append(f"{custom_field_changes} custom field(s) updated")
        
        return {
            'summary': changes,
            'details': detailed_changes
        }
    
    def _is_serial_valid(self, serial: str) -> bool:
        """
        Check if serial number is valid (not a placeholder)
        
        Args:
            serial: Serial number to validate
            
        Returns:
            True if valid, False if placeholder/invalid
        """
        if not serial or not serial.strip():
            return False
        
        serial_lower = serial.lower().strip()
        
        # Common placeholder values
        invalid_patterns = [
            'unknown',
            'to be filled by o.e.m.',
            'to be filled by o.e.m',
            'default string',
            'not specified',
            'not available',
            'system serial number',
            'chassis serial number',
            '0123456789',
            'n/a',
            'none',
            '000000000000',
            '111111111111'
        ]
        
        return serial_lower not in invalid_patterns
