"""
Sniper-IT Agent - Asset Manager
Handles laptop/desktop asset operations in Snipe-IT
"""

import re
from typing import Dict, Any, Optional
from core.api_client import SnipeITClient
from cli.formatters import print_info, print_error, print_warning, console
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
        Process laptop/desktop asset end-to-end
        
        Args:
            system_data: Dictionary containing:
                - system_data: Core system information
                - custom_fields: Custom field data
                - os_type: Operating system type
                
        Returns:
            Dictionary with processing results or None if failed
        """
        self.logger.verbose("")
        self.logger.verbose(f"{STATUS_INFO} Processing laptop/desktop asset...")
        self.logger.verbose("=" * 70)
        
        try:
            # Extract data
            asset_data = system_data['system_data']
            custom_fields = system_data['custom_fields']
            
            hostname = asset_data.get('hostname', 'Unknown')
            manufacturer = asset_data.get('manufacturer', 'Unknown')
            model = asset_data.get('model', 'Unknown')
            serial = asset_data.get('serial_number', 'Unknown')
            
            self.logger.verbose(f"{STATUS_INFO} Hostname: {hostname}")
            self.logger.verbose(f"{STATUS_INFO} Manufacturer: {manufacturer}")
            self.logger.verbose(f"{STATUS_INFO} Model: {model}")
            self.logger.verbose(f"{STATUS_INFO} Serial: {serial}")
            self.logger.verbose("")
            
            # Step 1: Find or create manufacturer
            self.logger.verbose(f"{STATUS_INFO} Processing manufacturer: {manufacturer}")
            manufacturer_id = self.api.find_or_create_manufacturer(manufacturer)
            self.logger.verbose(f"{STATUS_OK} Manufacturer ID: {manufacturer_id}")
            
            # Step 2: Find or create model
            self.logger.verbose(f"{STATUS_INFO} Processing model: {model}")
            model_id = self.api.find_or_create_model(
                name=model,
                model_number=model,  # Use model name as model number
                manufacturer_id=manufacturer_id,
                category_id=self.defaults.get('laptop_category_id', 2),
                fieldset_id=self.defaults.get('laptop_fieldset_id', 1)
            )
            self.logger.verbose(f"{STATUS_OK} Model ID: {model_id}")
            
            # Step 3: Check if asset exists by hostname
            self.logger.verbose(f"{STATUS_INFO} Searching for existing asset: {hostname}")
            existing_asset_id = self.api.find_hardware_by_hostname(hostname)
            
            # Step 4: Prepare payload
            payload = {
                'name': hostname,
                'serial': serial,
                'model_id': model_id,
                'status_id': self.defaults.get('status_id', 2),
                'company_id': self.defaults.get('company_id', 1)
            }
            
            # Add custom fields
            custom_field_payload = self._map_custom_fields_to_payload(custom_fields)
            payload.update(custom_field_payload)
            
            # Step 5: Create or update asset
            if existing_asset_id:
                self.logger.verbose(f"{STATUS_OK} Found existing asset ID: {existing_asset_id}")
                
                # Get existing data to preserve asset_tag
                existing_data = self.api.get_hardware_by_id(existing_asset_id)
                existing_tag = existing_data.get('asset_tag', '')
                
                if existing_tag:
                    payload['asset_tag'] = existing_tag
                    self.logger.verbose(f"{STATUS_INFO} Preserving asset tag: {existing_tag}")
                else:
                    # Generate new asset tag
                    payload['asset_tag'] = self._generate_asset_tag(hostname)
                
                self.logger.verbose(f"{STATUS_INFO} Updating asset...")
                result = self.api.update_hardware(existing_asset_id, payload)
                
                if result.get('status') == 'success':
                    self.logger.verbose(f"{STATUS_OK} Asset updated successfully")
                    asset_id = existing_asset_id
                else:
                    print_error(f"Update failed: {result.get('messages', 'Unknown error')}")
                    return None
            else:
                self.logger.verbose(f"{STATUS_INFO} No existing asset found - creating new")
                # Generate asset tag based on naming convention
                payload['asset_tag'] = self._generate_asset_tag(hostname)
                self.logger.verbose(f"{STATUS_INFO} Generated asset tag: {payload['asset_tag']}")
                
                result = self.api.create_hardware(payload)
                
                if result.get('status') == 'success':
                    asset_id = result['payload']['id']
                    self.logger.verbose(f"{STATUS_OK} Asset created successfully (ID: {asset_id})")
                else:
                    print_error(f"Creation failed: {result.get('messages', 'Unknown error')}")
                    return None
            
            # Step 6: Verify the asset
            self.logger.verbose(f"{STATUS_INFO} Verifying asset data...")
            verification = self._verify_asset(asset_id)
            
            self.logger.verbose("")
            self.logger.verbose("=" * 70)
            self.logger.verbose(f"{STATUS_OK} Laptop/Desktop asset processing completed")
            self.logger.verbose("")
            
            return {
                'asset_id': asset_id,
                'hostname': hostname,
                'manufacturer_id': manufacturer_id,
                'model_id': model_id,
                'verification': verification,
                'action': 'updated' if existing_asset_id else 'created'
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
            
            self.logger.verbose(f"{STATUS_INFO} Custom fields: {populated_count}/{total_count} populated ({success_rate:.1f}%)")
            
            return {
                'asset_id': asset_id,
                'populated_fields': populated_count,
                'total_fields': total_count,
                'success_rate': success_rate,
                'asset_data': data
            }
            
        except Exception as e:
            self.logger.verbose(f"{STATUS_WARNING} Verification warning: {e}")
            return {
                'asset_id': asset_id,
                'error': str(e)
            }
    
    def _generate_asset_tag(self, hostname: str) -> str:
        """
        Generate asset tag based on naming convention or use hostname
        
        Args:
            hostname: Computer hostname to use as fallback
            
        Returns:
            Generated asset tag string
        """
        naming_convention = self.defaults.get('naming_convention', '').strip()
        
        # If no naming convention, use hostname
        if not naming_convention:
            return hostname
        
        # Find the last asset with this naming pattern
        try:
            last_tag = self._find_last_asset_tag(naming_convention)
            
            if last_tag:
                # Extract number and increment
                next_number = self._extract_and_increment_number(last_tag, naming_convention)
                new_tag = naming_convention.replace('N', str(next_number).zfill(len(str(next_number))))
                return new_tag
            else:
                # No existing assets found - start with 0001
                new_tag = naming_convention.replace('N', '0001')
                return new_tag
                
        except Exception as e:
            self.logger.verbose(f"{STATUS_WARNING} Asset tag generation failed: {e}")
            self.logger.verbose(f"{STATUS_INFO} Falling back to hostname")
            return hostname
    
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
        
        # Search for assets with this prefix
        # Note: Snipe-IT search is limited, so we fetch laptops and filter
        search_results = self.api.search_hardware(search_prefix, limit=500)
        
        matching_tags = []
        
        # Create regex pattern to match the naming convention
        # Replace 'N' with digit pattern
        regex_pattern = re.escape(pattern).replace('N', r'(\d+)')
        
        for asset in search_results:
            asset_tag = asset.get('asset_tag', '')
            if re.fullmatch(regex_pattern, asset_tag):
                matching_tags.append(asset_tag)
        
        if not matching_tags:
            return None
        
        # Sort by the numeric part and return the last one
        matching_tags.sort(key=lambda tag: self._extract_number_from_tag(tag, pattern))
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
    
    def _extract_and_increment_number(self, last_tag: str, pattern: str) -> int:
        """
        Extract number from last tag and increment by 1
        
        Args:
            last_tag: Last asset tag found (e.g., 'MIS-2026-0026')
            pattern: Pattern with 'N' (e.g., 'MIS-2026-N')
            
        Returns:
            Incremented number
        """
        current_number = self._extract_number_from_tag(last_tag, pattern)
        return current_number + 1
