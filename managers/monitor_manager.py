"""
Sniper-IT Agent - Monitor Manager
Handles monitor asset operations in Snipe-IT
"""

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
                
                # Get existing data to preserve asset_tag
                existing_data = self.api.get_hardware_by_id(existing_asset_id)
                existing_tag = existing_data.get('asset_tag', '')
                
                if existing_tag:
                    payload['asset_tag'] = existing_tag
                else:
                    payload['asset_tag'] = payload['serial']
                
                self.logger.verbose(f"  {STATUS_INFO} Updating monitor...")
                result = self.api.update_hardware(existing_asset_id, payload)
                
                if result.get('status') == 'success':
                    self.logger.verbose(f"  {STATUS_OK} Monitor updated successfully")
                    asset_id = existing_asset_id
                    action = 'updated'
                else:
                    print_error(f"Update failed: {result.get('messages', 'Unknown error')}")
                    return None
            else:
                self.logger.verbose(f"  {STATUS_INFO} Creating new monitor...")
                payload['asset_tag'] = payload['serial']
                
                result = self.api.create_hardware(payload)
                
                if result.get('status') == 'success':
                    asset_id = result['payload']['id']
                    self.logger.verbose(f"  {STATUS_OK} Monitor created (ID: {asset_id})")
                    action = 'created'
                else:
                    print_error(f"Creation failed: {result.get('messages', 'Unknown error')}")
                    return None
            
            # Step 6: Checkout monitor to parent laptop (if provided)
            if parent_asset_id:
                self.logger.verbose(f"  {STATUS_INFO} Checking out monitor to laptop (Asset #{parent_asset_id})...")
                try:
                    checkout_result = self.api.checkout_hardware(
                        asset_id=asset_id,
                        checkout_to_type='asset',
                        assigned_id=parent_asset_id,
                        status_id=self.defaults.get('status_id', 2),
                        note=f"Auto-assigned to {parent_hostname}"
                    )
                    
                    if checkout_result.get('status') == 'success':
                        self.logger.verbose(f"  {STATUS_OK} Monitor checked out to laptop")
                    else:
                        self.logger.verbose(f"  {STATUS_WARNING} Checkout warning: {checkout_result.get('messages', 'Unknown')}")
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
                'checked_out_to': parent_asset_id
            }
            
        except APIError as e:
            print_error(f"API error: {e}")
            return None
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            return None
