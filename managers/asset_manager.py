#!/usr/bin/env python3
"""
Robust Asset Manager for SniperIT Agent
Handles hostname-based asset detection, model creation with fieldsets, and data verification
"""

import requests
import json
from config.settings import GlobalSettings

class AssetManager:
    def __init__(self, verify_ssl=True):
        self.config = GlobalSettings().config
        self.verify_ssl = verify_ssl
        self.api_key = self.config['SERVER']['api_key']
        self.base_url = self.config['SERVER']['site'].replace('/api/v1', '')
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json"
        }
    
    def find_asset_by_hostname(self, hostname):
        """Find asset by hostname (name field)"""
        print(f"🔍 Searching for asset with hostname: {hostname}")
        
        # Search by name field which should contain the hostname
        endpoint = f"{self.base_url}/api/v1/hardware"
        params = {
            'search': hostname,
            'limit': 50
        }
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                assets = data.get('rows', [])
                
                # Look for exact hostname match
                for asset in assets:
                    if asset.get('name', '').lower() == hostname.lower():
                        print(f"✅ Found existing asset: {asset['name']} (ID: {asset['id']})")
                        return asset['id']
                
                print(f"❌ No asset found with hostname: {hostname}")
                return None
            else:
                print(f"❌ Search failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error searching for asset: {e}")
            return None
    
    def find_or_create_manufacturer(self, manufacturer_name):
        """Find existing manufacturer or create new one"""
        print(f"🏭 Processing manufacturer: {manufacturer_name}")
        
        # Search for existing manufacturer
        endpoint = f"{self.base_url}/api/v1/manufacturers"
        params = {'search': manufacturer_name, 'limit': 50}
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                manufacturers = data.get('rows', [])
                
                # Look for exact match
                for mfg in manufacturers:
                    if mfg.get('name', '').lower() == manufacturer_name.lower():
                        print(f"✅ Found existing manufacturer: {mfg['name']} (ID: {mfg['id']})")
                        return mfg['id']
                
                # Create new manufacturer
                print(f"➕ Creating new manufacturer: {manufacturer_name}")
                create_endpoint = f"{self.base_url}/api/v1/manufacturers"
                payload = {"name": manufacturer_name}
                
                create_response = requests.post(create_endpoint, json=payload, headers=self.headers, verify=self.verify_ssl, timeout=10)
                
                if create_response.status_code == 200:
                    create_data = create_response.json()
                    if create_data.get('status') == 'success':
                        manufacturer_id = create_data['payload']['id']
                        print(f"✅ Created manufacturer: {manufacturer_name} (ID: {manufacturer_id})")
                        return manufacturer_id
                
                print(f"❌ Failed to create manufacturer: {create_response.text}")
                return None
            
        except Exception as e:
            print(f"❌ Error processing manufacturer: {e}")
            return None
    
    def find_or_create_model(self, model_name, model_number, manufacturer_id):
        """Find existing model or create new one with proper fieldset"""
        print(f"📱 Processing model: {model_name}")
        
        # Search for existing model
        endpoint = f"{self.base_url}/api/v1/models"
        params = {'search': model_name, 'limit': 50}
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                models = data.get('rows', [])
                
                # Look for exact match with same manufacturer
                for model in models:
                    if (model.get('name', '').lower() == model_name.lower() and 
                        model.get('manufacturer', {}).get('id') == manufacturer_id):
                        print(f"✅ Found existing model: {model['name']} (ID: {model['id']})")
                        return model['id']
                
                # Create new model
                print(f"➕ Creating new model: {model_name}")
                
                # Get default configuration values
                category_id = self.config['DEFAULTS']['snipeit_category_id']
                fieldset_id = self.config['DEFAULTS']['snipeit_fieldset_id']
                
                payload = {
                    "name": model_name,
                    "model_number": model_number,
                    "category_id": int(category_id),
                    "manufacturer_id": manufacturer_id,
                    "fieldset_id": int(fieldset_id)  # This is crucial for custom fields
                }
                
                create_endpoint = f"{self.base_url}/api/v1/models"
                create_response = requests.post(create_endpoint, json=payload, headers=self.headers, verify=self.verify_ssl, timeout=10)
                
                if create_response.status_code == 200:
                    create_data = create_response.json()
                    if create_data.get('status') == 'success':
                        model_id = create_data['payload']['id']
                        print(f"✅ Created model: {model_name} (ID: {model_id}) with fieldset {fieldset_id}")
                        return model_id
                
                print(f"❌ Failed to create model: {create_response.text}")
                return None
            
        except Exception as e:
            print(f"❌ Error processing model: {e}")
            return None
    
    def create_asset_payload(self, asset_data, is_update=False, existing_asset_data=None):
        """Create properly formatted payload for asset creation/update"""
        
        # Basic asset fields
        payload = {
            "name": asset_data['hostname'],
            "serial": asset_data['serial_number'],
            "model_id": asset_data['model_id'],
            "status_id": int(self.config['DEFAULTS']['snipeit_status_id']),
            "company_id": int(self.config['DEFAULTS']['snipeit_company_id'])
        }
        
        # Handle asset tag intelligently
        if is_update and existing_asset_data:
            # For updates, keep existing asset tag to avoid conflicts
            existing_tag = existing_asset_data.get('asset_tag')
            if existing_tag:
                payload["asset_tag"] = existing_tag
                print(f"   📋 Keeping existing asset tag: {existing_tag}")
            else:
                payload["asset_tag"] = asset_data['serial_number']
        else:
            # For new assets, use serial as asset tag
            payload["asset_tag"] = asset_data['serial_number']
        
        # Add custom fields directly to payload (Snipe-IT expects them as top-level keys)
        custom_fields_mapping = {
            "MAC Address": "_snipeit_mac_address_1",
            "Total Storage": "_snipeit_total_storage_4", 
            "Storage Information": "_snipeit_storage_information_5",
            "Disk Space Used": "_snipeit_disk_space_used_6",
            "Agent Version": "_snipeit_agent_version_7",
            "Operating System": "_snipeit_operating_system_8",
            "OS Install Date": "_snipeit_os_install_date_9", 
            "Memory / RAM": "_snipeit_memory_ram_10",
            "RAM Usage": "_snipeit_ram_usage_11",
            "BIOS Release Date": "_snipeit_bios_release_date_12",
            "IP Address": "_snipeit_ip_address_13",
            "Processor / CPU": "_snipeit_processor_cpu_14",
            "Windows Username": "_snipeit_windows_username_15"
        }
        
        # Add custom fields to payload
        for display_name, value in asset_data.get('custom_fields', {}).items():
            if display_name in custom_fields_mapping:
                db_column = custom_fields_mapping[display_name]
                payload[db_column] = str(value)
        
        return payload
    
    def create_asset(self, asset_data):
        """Create new asset"""
        print(f"➕ Creating new asset: {asset_data['hostname']}")
        
        payload = self.create_asset_payload(asset_data, is_update=False)
        endpoint = f"{self.base_url}/api/v1/hardware"
        
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    asset_id = data['payload']['id']
                    print(f"✅ Created asset: {asset_data['hostname']} (ID: {asset_id})")
                    return asset_id
                else:
                    print(f"❌ Asset creation failed: {data.get('messages', 'Unknown error')}")
                    return None
            else:
                print(f"❌ Asset creation failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating asset: {e}")
            return None
    
    def get_asset_data(self, asset_id):
        """Get existing asset data"""
        endpoint = f"{self.base_url}/api/v1/hardware/{asset_id}"
        
        try:
            response = requests.get(endpoint, headers=self.headers, verify=self.verify_ssl, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️  Could not fetch existing asset data: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️  Error fetching existing asset data: {e}")
            return None
    
    def update_asset(self, asset_id, asset_data):
        """Update existing asset"""
        print(f"🔄 Updating asset ID: {asset_id}")
        
        # Get existing asset data first to avoid asset tag conflicts
        existing_asset_data = self.get_asset_data(asset_id)
        
        payload = self.create_asset_payload(asset_data, is_update=True, existing_asset_data=existing_asset_data)
        endpoint = f"{self.base_url}/api/v1/hardware/{asset_id}"
        
        try:
            response = requests.patch(endpoint, json=payload, headers=self.headers, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    print(f"✅ Updated asset: {asset_data['hostname']} (ID: {asset_id})")
                    return True
                else:
                    print(f"❌ Asset update failed: {data.get('messages', 'Unknown error')}")
                    return False
            else:
                print(f"❌ Asset update failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating asset: {e}")
            return False
    
    def verify_asset_data(self, asset_id):
        """Verify that asset data was saved correctly"""
        print(f"🔍 Verifying asset data for ID: {asset_id}")
        
        endpoint = f"{self.base_url}/api/v1/hardware/{asset_id}"
        
        try:
            response = requests.get(endpoint, headers=self.headers, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"📋 Verification Results:")
                print(f"   Name: {data.get('name', 'N/A')}")
                print(f"   Asset Tag: {data.get('asset_tag', 'N/A')}")
                print(f"   Serial: {data.get('serial', 'N/A')}")
                print(f"   Model: {data.get('model', {}).get('name', 'N/A')}")
                
                # Check custom fields
                custom_fields = data.get('custom_fields', {})
                populated_count = 0
                total_count = 0
                
                print(f"   Custom Fields:")
                for field_name, field_info in custom_fields.items():
                    total_count += 1
                    value = field_info.get('value', '')
                    if value:
                        populated_count += 1
                        print(f"     ✅ {field_name}: {value}")
                    else:
                        print(f"     ❌ {field_name}: (empty)")
                
                success_rate = (populated_count / total_count * 100) if total_count > 0 else 0
                print(f"   📊 Success Rate: {populated_count}/{total_count} ({success_rate:.1f}%)")
                
                return {
                    'asset_id': asset_id,
                    'populated_fields': populated_count,
                    'total_fields': total_count,
                    'success_rate': success_rate,
                    'asset_data': data
                }
            else:
                print(f"❌ Verification failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Error during verification: {e}")
            return None
    
    def process_asset(self, system_data):
        """Main method to process asset end-to-end"""
        print("🎯 STARTING ASSET PROCESSING")
        print("=" * 50)
        
        asset_data = system_data['system_data']
        custom_fields = system_data['custom_fields']
        
        # Step 1: Find or create manufacturer
        manufacturer_id = self.find_or_create_manufacturer(asset_data['manufacturer'])
        if not manufacturer_id:
            print("❌ Failed to process manufacturer")
            return None
        
        # Step 2: Find or create model
        model_id = self.find_or_create_model(
            asset_data['model'], 
            asset_data.get('model', 'Unknown'),  # Use model name as model number if not specified
            manufacturer_id
        )
        if not model_id:
            print("❌ Failed to process model")
            return None
        
        # Step 3: Prepare asset data
        asset_payload_data = {
            'hostname': asset_data['hostname'],
            'serial_number': asset_data['serial_number'],
            'model_id': model_id,
            'custom_fields': custom_fields
        }
        
        # Step 4: Find existing asset by hostname
        existing_asset_id = self.find_asset_by_hostname(asset_data['hostname'])
        
        # Step 5: Create or update asset
        if existing_asset_id:
            success = self.update_asset(existing_asset_id, asset_payload_data)
            final_asset_id = existing_asset_id if success else None
        else:
            final_asset_id = self.create_asset(asset_payload_data)
        
        if not final_asset_id:
            print("❌ Failed to create/update asset")
            return None
        
        # Step 6: Verify the results
        verification = self.verify_asset_data(final_asset_id)
        
        print("\n🎉 ASSET PROCESSING COMPLETED")
        print("=" * 50)
        
        return {
            'asset_id': final_asset_id,
            'manufacturer_id': manufacturer_id,
            'model_id': model_id,
            'verification': verification
        }

if __name__ == "__main__":
    # Test with mock data
    mock_system_data = {
        'system_data': {
            'hostname': 'test-host',
            'manufacturer': 'Test Manufacturer',
            'model': 'Test Model',
            'serial_number': 'TEST-123-456'
        },
        'custom_fields': {
            'Operating System': 'Test OS',
            'Memory / RAM': '8',
            'Processor / CPU': 'Test CPU'
        }
    }
    
    manager = AssetManager(verify_ssl=False)
    result = manager.process_asset(mock_system_data)
    print(f"Result: {result}")