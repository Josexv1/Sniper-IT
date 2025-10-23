"""
Sniper-IT Agent - Monitor Manager
Handles monitor asset operations in Snipe-IT
"""

import re
from typing import Dict, Any, Optional, List
from core.api_client import SnipeITClient
from cli.formatters import (print_info, print_error, print_warning, console,
                             print_section, print_step, print_subsection)
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
    
    def _calculate_levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance (edit distance) between two strings.
        Used as a safety upper bound for fuzzy matching.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Minimum number of single-character edits (insertions, deletions, substitutions)
        """
        if len(s1) < len(s2):
            return self._calculate_levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        # Create array of distances
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost of insertions, deletions, or substitutions
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _normalize_serial(self, serial: str) -> str:
        """
        Normalize serial number for comparison by removing common variations
        
        Args:
            serial: Raw serial number
            
        Returns:
            Normalized serial (uppercase, no leading zeros on segments)
        """
        if not serial:
            return ''
        
        # Convert to uppercase
        normalized = serial.upper().strip()
        
        # Remove common prefixes/suffixes that might vary
        # Keep the core serial intact
        return normalized
    
    def _normalize_model_name(self, model_name: str) -> str:
        """
        Normalize model name for comparison (remove extra spaces, lowercase)
        
        Args:
            model_name: Model name to normalize
            
        Returns:
            Normalized model name
        """
        if not model_name:
            return ''
        # Convert to lowercase, remove extra spaces, strip
        return ' '.join(model_name.lower().split())
    
    def _serials_match(self, serial1: str, serial2: str) -> bool:
        """
        Check if two serial numbers match, accounting for common ZERO-ONLY variations.
        Uses segment-based comparison with Levenshtein distance as safety upper bound.
        
        RESEARCH-BACKED ALGORITHM:
        1. Normalize serials (uppercase, trim)
        2. Check exact match (fast path)
        3. Calculate Levenshtein distance as safety check (max 3 edits allowed)
        4. Split into letter/number segments (e.g., "UK02239" → ["UK", "02239"])
        5. Compare letter segments EXACTLY (no fuzzy matching)
        6. Compare number segments as integers (ignores leading zeros ONLY)
        
        EXAMPLES:
        ✅ MATCH: UK2239016158 vs UK02239016158 (zero insertion in number)
        ✅ MATCH: XFXP6HA12946 vs XFXP6HA012946 (zero padding in number)
        ✅ MATCH: 0001234 vs 1234 (leading zeros)
        ❌ NO MATCH: 3CM22239ZQ vs 3CM22239Z0 (Q≠0, different letters)
        ❌ NO MATCH: 3CM22339ZF vs 3CM22339ZC (F≠C, different letters)
        ❌ NO MATCH: ABC123 vs ABC124 (123≠124, different numbers)
        ❌ NO MATCH: 00AB123 vs AB123 (different segment count)
        
        Args:
            serial1: First serial number (e.g., from EDID)
            serial2: Second serial number (e.g., from Snipe-IT database)
            
        Returns:
            True if serials match (exactly or with zero-only variations), False otherwise
        """
        if not serial1 or not serial2:
            self.logger.debug(f"      [dim]Serial match: Empty serial(s) - NO MATCH[/dim]")
            return False
        
        # Normalize both
        s1 = self._normalize_serial(serial1)
        s2 = self._normalize_serial(serial2)
        
        self.logger.debug(f"      [dim]Comparing serials:[/dim]")
        self.logger.debug(f"        [dim]New (EDID):  '{serial1}' → '{s1}'[/dim]")
        self.logger.debug(f"        [dim]Database:    '{serial2}' → '{s2}'[/dim]")
        
        # Exact match (fastest path)
        if s1 == s2:
            self.logger.debug(f"        [green]✓ EXACT MATCH[/green]")
            return True
        
        # Calculate Levenshtein distance as safety check
        lev_distance = self._calculate_levenshtein_distance(s1, s2)
        self.logger.debug(f"        [dim]Levenshtein distance: {lev_distance}[/dim]")
        
        # Safety check: if too many edits needed, definitely not the same serial
        # Allow up to 3 character differences (typically zero insertions/removals)
        MAX_EDIT_DISTANCE = 3
        if lev_distance > MAX_EDIT_DISTANCE:
            self.logger.debug(f"        [yellow]✗ Too different (Levenshtein {lev_distance} > {MAX_EDIT_DISTANCE}) - NO MATCH[/yellow]")
            return False
        
        # Only proceed if lengths are close and difference could be zeros
        len_diff = abs(len(s1) - len(s2))
        if len_diff > MAX_EDIT_DISTANCE:
            self.logger.debug(f"        [yellow]✗ Length difference too large ({len_diff}) - NO MATCH[/yellow]")
            return False
        
        if len_diff == 0 and s1 != s2:
            # Same length but different - could be Q vs 0 case
            self.logger.debug(f"        [yellow]✗ Same length but different content - NO MATCH[/yellow]")
            return False
        
        # Split on letter/number boundaries for segment comparison
        # This is the ONLY fuzzy matching we do (numeric segments ignore leading zeros)
        s1_parts = re.findall(r'[A-Z]+|\d+', s1)
        s2_parts = re.findall(r'[A-Z]+|\d+', s2)
        
        self.logger.debug(f"        [dim]Segments:[/dim]")
        self.logger.debug(f"          [dim]S1: {s1_parts}[/dim]")
        self.logger.debug(f"          [dim]S2: {s2_parts}[/dim]")
        
        # Must have same number of segments
        if len(s1_parts) != len(s2_parts):
            self.logger.debug(f"        [yellow]✗ Different segment count ({len(s1_parts)} vs {len(s2_parts)}) - NO MATCH[/yellow]")
            return False
        
        # Compare each segment
        for i, (p1, p2) in enumerate(zip(s1_parts, s2_parts)):
            # Letters must match EXACTLY (no fuzzy matching on letters)
            if p1.isalpha() and p2.isalpha():
                if p1 != p2:
                    self.logger.debug(f"          [yellow]✗ Segment {i+1}: Letter mismatch '{p1}' ≠ '{p2}' - NO MATCH[/yellow]")
                    return False
                else:
                    self.logger.debug(f"          [green]✓ Segment {i+1}: '{p1}' == '{p2}' (exact)[/green]")
            
            # Numbers: compare as integers (ignores leading zeros)
            # This is safe because int('0123') == int('123')
            elif p1.isdigit() and p2.isdigit():
                try:
                    num1 = int(p1)
                    num2 = int(p2)
                    if num1 != num2:
                        self.logger.debug(f"          [yellow]✗ Segment {i+1}: Number mismatch {num1} ≠ {num2} - NO MATCH[/yellow]")
                        return False
                    else:
                        if p1 != p2:
                            self.logger.debug(f"          [cyan]✓ Segment {i+1}: '{p1}' == '{p2}' (zero padding difference, {num1} == {num2})[/cyan]")
                        else:
                            self.logger.debug(f"          [green]✓ Segment {i+1}: '{p1}' == '{p2}' (exact)[/green]")
                except ValueError:
                    # Shouldn't happen, but be safe
                    self.logger.debug(f"          [red]✗ Segment {i+1}: Invalid number format - NO MATCH[/red]")
                    return False
            
            # Mixed type segments (one is letter, one is number) = different serial
            else:
                self.logger.debug(f"          [yellow]✗ Segment {i+1}: Type mismatch ('{p1}' vs '{p2}') - NO MATCH[/yellow]")
                return False
        
        # All segments matched - this is the same serial with zero variations
        self.logger.verbose(f"    [cyan]→ Serial match found: '{serial1}' ≈ '{serial2}' (zero-padding variation)[/cyan]")
        self.logger.debug(f"        [green]✓ ALL SEGMENTS MATCH - FUZZY MATCH CONFIRMED[/green]")
        return True
    
    def _get_clean_model_name(self, monitor_data: Dict[str, Any]) -> str:
        """
        Extract clean model name without EDID manufacturer codes
        
        Args:
            monitor_data: Monitor data dictionary
            
        Returns:
            Clean model name (e.g., "275V8" not "PHL 275V8", "M24fe FHD" not "HP M24fe FHD")
        """
        manufacturer = monitor_data.get('manufacturer', 'Unknown')
        model = monitor_data.get('model', 'Monitor')
        
        model_lower = model.lower()
        manufacturer_lower = manufacturer.lower()
        
        # Check if model starts with EDID manufacturer code (2-4 letter prefix)
        edid_match = re.match(r'^([A-Z]{2,4})\s+(.+)$', model)
        if edid_match:
            edid_code = edid_match.group(1)
            model_without_code = edid_match.group(2)
            
            # Strip EDID code if it's different from manufacturer
            if edid_code.lower() != manufacturer_lower:
                return model_without_code
        
        # Check if model starts with full manufacturer name
        if model.lower().startswith(manufacturer_lower + ' '):
            # Strip manufacturer from model (e.g., "HP M24fe FHD" → "M24fe FHD")
            return model[len(manufacturer)+1:].strip()
        
        # Return model as-is
        return model
    
    def _generate_monitor_name(self, monitor_data: Dict[str, Any], index: int) -> str:
        """
        Generate a descriptive name for the monitor asset
        
        Args:
            monitor_data: Monitor data dictionary
            index: Monitor index (unused - kept for compatibility)
            
        Returns:
            Monitor name string (e.g., "Philips 275V8", "HP M24fe FHD")
        """
        manufacturer = monitor_data.get('manufacturer', 'Unknown')
        clean_model = self._get_clean_model_name(monitor_data)
        
        # Always format as "Manufacturer Model"
        return f"{manufacturer} {clean_model}"
    
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
            return []
        
        print_section(f"SYNCING MONITORS ({len(monitors)} total)")
        
        results = []
        
        for i, monitor_data in enumerate(monitors, start=1):
            if self.logger.verbosity >= 2:
                print_subsection(f"Monitor {i}/{len(monitors)}")
            
            result = self._process_single_monitor(monitor_data, i, parent_hostname, parent_asset_id)
            
            if result:
                results.append(result)
            else:
                self.logger.verbose(f"  [yellow]⚠[/yellow] Monitor {i} processing had issues")
        
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
            
            # Get clean model name (without EDID codes)
            clean_model = self._get_clean_model_name(monitor_data)
            
            # Generate monitor name for the asset
            monitor_name = self._generate_monitor_name(monitor_data, index)
            
            # Show basic info only in debug mode (-vv)
            if self.logger.verbosity >= 2:
                console.print(f"  [dim]Name:[/dim] {monitor_name}")
                console.print(f"  [dim]Serial:[/dim] {serial if serial else '(empty)'}")
                console.print(f"  [dim]Resolution:[/dim] {resolution}")
            
            # Step 1: Find or create manufacturer
            self.logger.debug("")
            print_step(f"Processing {monitor_name}", "processing")
            manufacturer_id = self.api.find_or_create_manufacturer(manufacturer)
            self.logger.debug(f"    Manufacturer ID: {manufacturer_id}")
            
            # Step 2: Find or create model (use clean model name without EDID codes)
            # Model name = clean model only (e.g., "23xi", "275V8", "M24fe FHD")
            # Model number = manufacturer + model for clarity (e.g., "HP 23xi", "Philips 275V8")
            model_id = self.api.find_or_create_model(
                name=clean_model,
                model_number=monitor_name,  # Use full name for clarity
                manufacturer_id=manufacturer_id,
                category_id=self.defaults.get('monitor_category_id', 5),
                fieldset_id=self.defaults.get('monitor_fieldset_id', 2)
            )
            self.logger.debug(f"    Model ID: {model_id}")
            
            # Search for existing monitor
            # Search by serial if available, otherwise by name
            # Uses fuzzy matching to handle serial variations (extra/missing zeros)
            existing_asset_id = None
            monitor_category_id = self.defaults.get('monitor_category_id')
            
            self.logger.debug(f"    Searching for existing monitor")
            if serial and serial.strip():
                self.logger.debug(f"      Target serial: '{serial}'")
            self.logger.debug(f"      Target model: '{monitor_name}'")
            
            # SINGLE API CALL: Search by manufacturer (gets ALL monitors from this brand)
            # Then we filter in memory - much more efficient than multiple API calls
            self.logger.verbose(f"    Searching monitors by manufacturer: '{manufacturer}'")
            all_results = self.api.search_hardware(manufacturer, limit=200, category_id=monitor_category_id)
            self.logger.debug(f"      Found {len(all_results)} monitors from '{manufacturer}'")
            
            # Apply fuzzy matching to ALL results (model name AND serial)
            existing_data = {}  # Initialize
            if len(all_results) > 0:
                self.logger.debug(f"      [bold]Filtering and matching {len(all_results)} assets:[/bold]")
                
                for idx, asset in enumerate(all_results, 1):
                    asset_serial = asset.get('serial', '')
                    asset_name = asset.get('name', 'Unknown')
                    asset_id = asset['id']
                    
                    self.logger.debug(f"      [{idx}/{len(all_results)}] Asset #{asset_id}: '{asset_name}' (Serial: '{asset_serial}')")
                    
                    # First check: Does the model name match (for cases like "HP EX21" vs "HP EX 21")
                    model_matches = self._normalize_model_name(asset_name) == self._normalize_model_name(monitor_name)
                    
                    # Second check: Does the serial match (with fuzzy matching)
                    serial_matches = False
                    if serial and serial.strip() and asset_serial:
                        serial_matches = self._serials_match(asset_serial, serial)
                    
                    # Match if EITHER model matches (and no serial) OR serial matches
                    if model_matches or serial_matches:
                        existing_asset_id = asset_id
                        
                        if serial_matches and asset_serial != serial:
                            self.logger.verbose(f"    [cyan]✓ Found by serial match: Asset #{asset_id}[/cyan]")
                            self.logger.verbose(f"    [yellow]→ Will update DB serial to match EDID: '{asset_serial}' → '{serial}'[/yellow]")
                            existing_data = {'needs_serial_update': True, 'old_serial': asset_serial}
                        elif model_matches and not serial:
                            self.logger.verbose(f"    [cyan]✓ Found by model name match (no serial): Asset #{asset_id}[/cyan]")
                            existing_data = {'needs_serial_update': False}
                        elif model_matches and serial_matches:
                            if asset_serial != serial:
                                self.logger.verbose(f"    [cyan]✓ Found match (model + serial): Asset #{asset_id}[/cyan]")
                                self.logger.verbose(f"    [yellow]→ Will update DB serial to match EDID: '{asset_serial}' → '{serial}'[/yellow]")
                                existing_data = {'needs_serial_update': True, 'old_serial': asset_serial}
                            else:
                                self.logger.verbose(f"    [green]✓ Found exact match (model + serial): Asset #{asset_id}[/green]")
                                existing_data = {'needs_serial_update': False}
                        else:
                            self.logger.verbose(f"    [green]✓ Found exact match: Asset #{asset_id}[/green]")
                            existing_data = {'needs_serial_update': False}
                        break
                
                if not existing_asset_id:
                    self.logger.debug(f"      [yellow]No matches found in {len(all_results)} assets[/yellow]")
            
            if not existing_asset_id:
                # Search by name as fallback
                self.logger.verbose(f"    Searching by monitor name: '{monitor_name}'")
                search_results = self.api.search_hardware(monitor_name, limit=50, category_id=monitor_category_id)
                self.logger.debug(f"      Name search returned {len(search_results)} results")
                
                for asset in search_results:
                    if asset.get('name', '').lower() == monitor_name.lower():
                        existing_asset_id = asset['id']
                        self.logger.verbose(f"    [green]✓ Found by name: Asset #{existing_asset_id}[/green]")
                        break
                
                if not existing_asset_id:
                    self.logger.debug(f"      [yellow]No name matches found[/yellow]")
            
            # Prepare payload
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
            
            # Create or update asset
            if existing_asset_id:
                self.logger.verbose(f"    Updating existing monitor (Asset #{existing_asset_id})")
                
                # Get full existing data to preserve asset_tag and detect changes
                full_existing_data = self.api.get_hardware_by_id(existing_asset_id)
                existing_tag = full_existing_data.get('asset_tag', '')
                
                # Check if we need to update the serial to match EDID
                if isinstance(existing_data, dict) and existing_data.get('needs_serial_update'):
                    old_serial = existing_data['old_serial']
                    self.logger.verbose(f"    [cyan]↻ Updating serial in database: '{old_serial}' → '{serial}'[/cyan]")
                    # Payload already has the correct EDID serial, so it will be updated
                
                # Generate or preserve asset tag based on naming convention
                payload['asset_tag'] = self._generate_or_preserve_monitor_asset_tag(serial, existing_tag)
                self.logger.debug(f"    Asset tag: {payload['asset_tag']}")
                
                # Check if update is needed
                change_info = self._detect_monitor_changes(full_existing_data, payload, model_id)
                has_changes = change_info['has_changes']
                monitor_changes = change_info['summary']
                monitor_detailed_changes = change_info['details']
                
                if not has_changes:
                    print_step(f"Monitor up to date (ID: {existing_asset_id})", "ok")
                    asset_id = existing_asset_id
                    action = 'no_change'
                else:
                    print_step(f"Updating monitor (ID: {existing_asset_id})", "processing")
                    for change in monitor_changes:
                        self.logger.debug(f"    • {change}")
                    result = self.api.update_hardware(existing_asset_id, payload)
                    
                    if result.get('status') == 'success':
                        self.logger.debug(f"    [green]✓[/green] Monitor updated")
                        asset_id = existing_asset_id
                        action = 'updated'
                    else:
                        print_error(f"Update failed: {result.get('messages', 'Unknown error')}")
                        return None
            else:
                # Generate asset tag based on naming convention
                payload['asset_tag'] = self._generate_monitor_asset_tag(serial)
                self.logger.debug(f"    Generated asset tag: {payload['asset_tag']}")
                
                # For new monitors, no changes to track
                monitor_changes = []
                monitor_detailed_changes = {}
                
                print_step("Creating new monitor", "processing")
                result = self.api.create_hardware(payload)
                
                if result.get('status') == 'success':
                    asset_id = result['payload']['id']
                    self.logger.debug(f"    [green]✓[/green] Monitor created (ID: {asset_id})")
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
                                self.logger.debug(f"    Already checked out to: {assigned_user_name}")
                        
                        # Only perform checkout if not already correct
                        if not already_correct:
                            # Check in first if currently checked out to someone else
                            if monitor_assigned_to:
                                self.logger.debug(f"    Checking in from previous user...")
                                checkin_result = self.api.checkin_hardware(
                                    asset_id=asset_id,
                                    note="Auto-checkin before reassignment"
                                )
                            
                            print_step(f"Checking out to {assigned_user_name}", "processing")
                            
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
                                self.logger.debug(f"    [green]✓[/green] Checked out to {assigned_user_name}")
                            else:
                                self.logger.debug(f"    [yellow]⚠[/yellow] Checkout warning: {checkout_result.get('messages', 'Unknown')}")
                    else:
                        self.logger.debug(f"    [yellow]⚠[/yellow] Parent asset not assigned to a user")
                        
                except Exception as e:
                    self.logger.debug(f"    [yellow]⚠[/yellow] Checkout failed: {e}")
            
            return {
                'asset_id': asset_id,
                'name': monitor_name,
                'manufacturer': manufacturer,
                'model': clean_model,
                'serial': serial,
                'manufacturer_id': manufacturer_id,
                'model_id': model_id,
                'action': action,
                'parent_hostname': parent_hostname,
                'parent_asset_id': parent_asset_id,
                'checked_out_to_user': assigned_user_id,
                'checked_out_to_user_name': assigned_user_name,
                'changes': monitor_changes,
                'detailed_changes': monitor_detailed_changes
            }
            
        except APIError as e:
            print_error(f"API error: {e}")
            return None
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            return None
    
    def _detect_monitor_changes(self, existing_data: Dict[str, Any], new_payload: Dict[str, Any], new_model_id: int) -> Dict[str, Any]:
        """
        Detect if monitor data has changed
        
        Args:
            existing_data: Existing monitor data from Snipe-IT
            new_payload: New payload to be sent
            new_model_id: New model ID
            
        Returns:
            Dictionary with 'has_changes' (bool), 'summary' (list), and 'details' (dict of field changes)
        """
        changes = []
        detailed_changes = {}  # Field name -> {old: value, new: value}
        
        # Check name change
        existing_name = existing_data.get('name', '')
        new_name = new_payload.get('name', '')
        if existing_name != new_name:
            changes.append(f"Name changed: {existing_name} → {new_name}")
            detailed_changes['Name'] = {'old': existing_name, 'new': new_name}
        
        # Check model change
        existing_model_id = existing_data.get('model', {}).get('id')
        if existing_model_id and existing_model_id != new_model_id:
            existing_model_name = existing_data.get('model', {}).get('name', 'Unknown')
            changes.append(f"Model changed (was: {existing_model_name})")
            detailed_changes['Model'] = {'old': existing_model_name, 'new': 'Updated'}
        
        # Check serial change
        existing_serial = existing_data.get('serial', '')
        new_serial = new_payload.get('serial', '')
        if existing_serial != new_serial:
            changes.append(f"Serial changed: {existing_serial} → {new_serial}")
            detailed_changes['Serial'] = {'old': existing_serial, 'new': new_serial}
        
        # Check custom fields changes
        existing_custom_fields = existing_data.get('custom_fields', {})
        custom_field_changes = 0
        
        # Get display name mapping from config
        monitor_fields_config = self.config.get('monitor_custom_fields', {})
        db_to_display = {}
        for field_key, field_config in monitor_fields_config.items():
            db_column = field_config.get('db_column', '')
            if db_column:
                # Use field_key as display name (e.g., 'resolution', 'refresh_rate')
                display_name = field_key.replace('_', ' ').title()
                db_to_display[db_column] = display_name
        
        for field_key, field_value in new_payload.items():
            if field_key.startswith('_snipeit_'):
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
            'has_changes': len(changes) > 0,
            'summary': changes,
            'details': detailed_changes
        }
    
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
                
                # Replace only the LAST 'N' with the incremented number
                last_n_index = naming_convention.rfind('N')
                if last_n_index != -1:
                    new_tag = naming_convention[:last_n_index] + str(next_number).zfill(num_digits) + naming_convention[last_n_index+1:]
                else:
                    new_tag = naming_convention
                
                self.logger.debug(f"{STATUS_INFO} Found last monitor tag: {last_tag} (#{current_number})")
                self.logger.debug(f"{STATUS_INFO} Generated new monitor tag: {new_tag} (#{next_number})")
                return new_tag
            else:
                # No existing assets found - start with 0001
                # Replace only the LAST 'N'
                last_n_index = naming_convention.rfind('N')
                if last_n_index != -1:
                    new_tag = naming_convention[:last_n_index] + '0001' + naming_convention[last_n_index+1:]
                else:
                    new_tag = naming_convention
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
            tag: Asset tag to check (e.g., 'MIS-MON-2025-0027')
            pattern: Pattern with 'N' placeholder at END (e.g., 'MIS-MON-2025-N')
            
        Returns:
            True if tag matches pattern, False otherwise
        """
        if not tag or not pattern:
            return False
        
        # Convert pattern to regex - only replace the LAST 'N'
        escaped_pattern = re.escape(pattern)
        last_n_index = escaped_pattern.rfind('N')
        if last_n_index != -1:
            regex_pattern = escaped_pattern[:last_n_index] + r'(\d+)' + escaped_pattern[last_n_index+1:]
        else:
            regex_pattern = escaped_pattern
        
        return bool(re.fullmatch(regex_pattern, tag))
    
    def _find_last_monitor_asset_tag(self, pattern: str) -> Optional[str]:
        """
        Find the last monitor asset tag matching the naming pattern
        
        Args:
            pattern: Naming pattern with 'N' placeholder at the END (e.g., 'MIS-MON-N', 'MIS-MON-2025-N')
            
        Returns:
            Last matching asset tag or None if not found
        """
        # Find the last 'N' in the pattern - that's the placeholder
        # For "MIS-MON-2025-N", we want to search for "MIS-MON-2025-"
        last_n_index = pattern.rfind('N')
        if last_n_index == -1:
            self.logger.debug(f"{STATUS_WARNING} No 'N' placeholder found in pattern: {pattern}")
            return None
        
        search_prefix = pattern[:last_n_index]
        
        self.logger.debug(f"{STATUS_INFO} Searching for monitor asset tags starting with: {search_prefix}")
        
        # Search for assets with this prefix
        # Note: Snipe-IT search is limited, so we fetch up to 500 assets and filter
        search_results = self.api.search_hardware(search_prefix, limit=500)
        
        self.logger.debug(f"{STATUS_INFO} Found {len(search_results)} assets in search results")
        
        matching_tags = []
        
        # Create regex pattern - only replace the LAST 'N' with digit pattern
        # Escape the pattern first, then replace only the last N
        escaped_pattern = re.escape(pattern)
        # Find last occurrence of 'N' in escaped pattern and replace with digit pattern
        last_n_in_escaped = escaped_pattern.rfind('N')
        if last_n_in_escaped != -1:
            regex_pattern = escaped_pattern[:last_n_in_escaped] + r'(\d+)' + escaped_pattern[last_n_in_escaped+1:]
        else:
            regex_pattern = escaped_pattern
        
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
            tag: Asset tag (e.g., 'MIS-MON-2025-0027')
            pattern: Pattern with 'N' at END (e.g., 'MIS-MON-2025-N')
            
        Returns:
            Extracted number as integer
        """
        # Convert pattern to regex - only replace the LAST 'N'
        escaped_pattern = re.escape(pattern)
        last_n_index = escaped_pattern.rfind('N')
        if last_n_index != -1:
            regex_pattern = escaped_pattern[:last_n_index] + r'(\d+)' + escaped_pattern[last_n_index+1:]
        else:
            return 0
        
        match = re.fullmatch(regex_pattern, tag)
        
        if match:
            return int(match.group(1))
        return 0
