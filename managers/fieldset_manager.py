#!/usr/bin/env python3
"""
Fieldset Manager for SniperIT Agent
Comprehensive fieldset validation, creation and assignment to models
Includes step-by-step validation and detailed progress reporting
"""

import requests
import json
from config.settings import GlobalSettings

class FieldsetManager:
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
    
    def get_categories(self):
        """Fetch all categories from Snipe-IT"""
        print("📂 Fetching categories from Snipe-IT...")
        
        endpoint = f"{self.base_url}/api/v1/categories"
        params = {'limit': 500}  # Get more categories
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                categories = data.get('rows', [])
                print(f"✅ Found {len(categories)} categories")
                return categories
            else:
                print(f"❌ Failed to fetch categories: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching categories: {e}")
            return []
    
    def get_models_by_categories(self, category_ids):
        """Get all models that belong to the specified categories"""
        print(f"📱 Fetching models for categories: {category_ids}")
        
        endpoint = f"{self.base_url}/api/v1/models"
        params = {'limit': 500}  # Get more models
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                all_models = data.get('rows', [])
                
                # Filter models by selected categories
                filtered_models = []
                for model in all_models:
                    if model.get('category_id') in category_ids:
                        filtered_models.append(model)
                
                print(f"✅ Found {len(filtered_models)} models in selected categories")
                return filtered_models
            else:
                print(f"❌ Failed to fetch models: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching models: {e}")
            return []
    
    def get_custom_fields(self):
        """Get all available custom fields"""
        print("📋 Fetching custom fields from Snipe-IT...")
        
        endpoint = f"{self.base_url}/api/v1/fields"
        params = {'limit': 500}
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                fields = data.get('rows', [])
                print(f"✅ Found {len(fields)} custom fields")
                return fields
            else:
                print(f"❌ Failed to fetch custom fields: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching custom fields: {e}")
            return []
    
    def get_total_models_count(self):
        """Get total count of models in the system"""
        try:
            endpoint = f"{self.base_url}/api/v1/models"
            params = {'limit': 1}  # Just get count
            
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('total', 0)
            return 0
        except:
            return 0
    
    def validate_custom_fields(self):
        """
        STEP 1: Validate all required custom fields exist with correct structure
        """
        print("\n🔍 STEP 1: VALIDATING CUSTOM FIELDS")
        print("=" * 60)
        
        # Load expected fields from config
        try:
            with open('config/custom_fields.json', 'r') as f:
                config_fields = json.load(f)
        except Exception as e:
            print(f"❌ Failed to load custom_fields.json: {e}")
            return False, []
        
        # Get current fields from Snipe-IT
        current_fields = self.get_custom_fields()
        if not current_fields:
            print("❌ Failed to fetch current custom fields from Snipe-IT")
            return False, []
        
        # Create lookup dictionary for current fields
        current_fields_dict = {}
        for field in current_fields:
            # Map both by database column name and display name
            db_name = field.get('db_column_name', '')
            display_name = field.get('name', '')
            current_fields_dict[db_name] = field
            current_fields_dict[display_name] = field
        
        # Check each expected field
        expected_fields = config_fields.get('custom_fields', {})
        results = {
            'missing': [],
            'existing_correct': [],
            'existing_incorrect': [],
            'valid_field_ids': []
        }
        
        print(f"🔍 Checking {len(expected_fields)} expected custom fields...")
        
        for db_column, expected_config in expected_fields.items():
            expected_name = expected_config.get('name', '')
            print(f"\n📋 Checking: {expected_name} ({db_column})")
            
            # Check if field exists by database column name
            current_field = current_fields_dict.get(db_column)
            if not current_field:
                # Also check by display name
                current_field = current_fields_dict.get(expected_name)
            
            if not current_field:
                print(f"   ❌ MISSING: {expected_name}")
                results['missing'].append({
                    'db_column': db_column,
                    'name': expected_name,
                    'config': expected_config
                })
            else:
                # Field exists, validate structure
                current_name = current_field.get('name', '')
                current_type = current_field.get('type', '')
                field_id = current_field.get('id')
                
                # Basic validation
                name_match = current_name == expected_name
                
                if name_match:
                    print(f"   ✅ EXISTS & CORRECT: {expected_name} (ID: {field_id})")
                    results['existing_correct'].append(current_field)
                    results['valid_field_ids'].append(field_id)
                else:
                    print(f"   ⚠️  EXISTS BUT DIFFERENT:")
                    print(f"      Expected name: {expected_name}")
                    print(f"      Current name:  {current_name}")
                    results['existing_incorrect'].append({
                        'expected': expected_config,
                        'current': current_field
                    })
        
        # Summary
        print(f"\n📊 CUSTOM FIELDS VALIDATION SUMMARY:")
        print(f"   ✅ Existing & Correct: {len(results['existing_correct'])}")
        print(f"   ❌ Missing: {len(results['missing'])}")
        print(f"   ⚠️  Existing but Incorrect: {len(results['existing_incorrect'])}")
        
        # Handle issues
        if results['existing_incorrect']:
            print(f"\n❌ VALIDATION FAILED!")
            print(f"   Found {len(results['existing_incorrect'])} fields with incorrect structure.")
            print(f"   Please fix these fields in Snipe-IT before proceeding:")
            for item in results['existing_incorrect']:
                expected = item['expected']
                current = item['current']
                print(f"   • Field '{current.get('name')}' should be '{expected.get('name')}'")
            return False, []
        
        if results['missing']:
            print(f"\n⚠️  MISSING FIELDS DETECTED!")
            print(f"   {len(results['missing'])} required fields are missing.")
            print(f"   You need to create these fields in Snipe-IT first:")
            for field in results['missing']:
                print(f"   • {field['name']} ({field['db_column']})")
            return False, []
        
        print(f"\n✅ ALL CUSTOM FIELDS VALIDATED SUCCESSFULLY!")
        print(f"   Found {len(results['valid_field_ids'])} valid fields ready for fieldset creation.")
        
        return True, results['valid_field_ids']
    
    def validate_fieldset(self, fieldset_name, required_field_ids):
        """
        Check if fieldset exists and validate it has the required fields
        """
        print(f"\n🔍 VALIDATING FIELDSET '{fieldset_name}'")
        print("=" * 50)
        
        # Get all fieldsets
        fieldsets = self.get_fieldsets()
        if not fieldsets:
            print("❌ Failed to fetch fieldsets from Snipe-IT")
            return False, None
        
        # Check if fieldset exists
        existing_fieldset = None
        for fieldset in fieldsets:
            if fieldset.get('name', '').lower() == fieldset_name.lower():
                existing_fieldset = fieldset
                break
        
        if existing_fieldset:
            fieldset_id = existing_fieldset.get('id')
            existing_fields = existing_fieldset.get('fields', [])
            
            # Handle both string IDs and object formats
            existing_field_ids = []
            for f in existing_fields:
                if isinstance(f, dict):
                    field_id = f.get('id')
                    if field_id:
                        existing_field_ids.append(field_id)
                elif isinstance(f, (str, int)):
                    # Only convert to int if it's actually numeric
                    try:
                        existing_field_ids.append(int(f))
                    except (ValueError, TypeError):
                        # Skip non-numeric values like 'total'
                        continue
            
            print(f"✅ FIELDSET EXISTS: '{fieldset_name}' (ID: {fieldset_id})")
            print(f"   📋 Current fields: {len(existing_fields)}")
            print(f"   📋 Required fields: {len(required_field_ids)}")
            
            # Check if existing fieldset has all required fields
            missing_fields = set(required_field_ids) - set(existing_field_ids)
            extra_fields = set(existing_field_ids) - set(required_field_ids)
            
            if not missing_fields and not extra_fields:
                print(f"   ✅ Fieldset has exactly the required fields")
                return True, fieldset_id
            else:
                print(f"   ⚠️  Fieldset structure mismatch:")
                if missing_fields:
                    print(f"      Missing field IDs: {list(missing_fields)}")
                if extra_fields:
                    print(f"      Extra field IDs: {list(extra_fields)}")
                print(f"   🔄 Will update fieldset to match requirements")
                
                # Update the existing fieldset
                success = self.update_fieldset(fieldset_id, fieldset_name, required_field_ids)
                if success:
                    print(f"   ✅ Fieldset updated successfully")
                    return True, fieldset_id
                else:
                    print(f"   ❌ Failed to update fieldset")
                    return False, None
        else:
            print(f"❌ FIELDSET NOT FOUND: '{fieldset_name}'")
            print(f"   🔄 Will create new fieldset")
            return False, None
    
    def get_fieldsets(self):
        """Get all fieldsets from Snipe-IT"""
        try:
            endpoint = f"{self.base_url}/api/v1/fieldsets"
            params = {'limit': 500}
            
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('rows', [])
            else:
                print(f"❌ Failed to fetch fieldsets: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error fetching fieldsets: {e}")
            return []
    
    def update_fieldset(self, fieldset_id, name, field_ids):
        """Update an existing fieldset with new fields"""
        print(f"🔄 Updating fieldset: {name} (ID: {fieldset_id})")
        
        endpoint = f"{self.base_url}/api/v1/fieldsets/{fieldset_id}"
        payload = {
            "name": name,
            "fields": field_ids
        }
        
        try:
            response = requests.patch(endpoint, json=payload, headers=self.headers, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    print(f"✅ Updated fieldset: {name}")
                    return True
                else:
                    print(f"❌ Failed to update fieldset: {data.get('messages', 'Unknown error')}")
                    return False
            else:
                print(f"❌ Failed to update fieldset: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating fieldset: {e}")
            return False
    
    def validate_models_fieldset_assignment(self, category_ids, fieldset_id):
        """
        Check which models need fieldset assignment
        """
        print(f"\n🔍 VALIDATING MODEL FIELDSET ASSIGNMENTS")
        print("=" * 50)
        
        # Get models from selected categories
        models = self.get_models_by_categories(category_ids)
        if not models:
            total_models = self.get_total_models_count()
            print(f"❌ No models found in selected categories")
            print(f"   💡 Found {total_models} total models but none assigned to these categories")
            print(f"   💡 Please assign models to categories in Snipe-IT first")
            return False, [], []
        
        print(f"📱 Found {len(models)} models in selected categories")
        
        # Check fieldset assignments
        models_with_correct_fieldset = []
        models_needing_fieldset = []
        
        for model in models:
            model_id = model.get('id')
            model_name = model.get('name')
            current_fieldset_id = model.get('fieldset_id')
            
            if current_fieldset_id == fieldset_id:
                print(f"   ✅ {model_name} (ID: {model_id}) - Already using correct fieldset")
                models_with_correct_fieldset.append(model)
            else:
                current_fieldset_name = "None" if not current_fieldset_id else f"ID {current_fieldset_id}"
                print(f"   🔄 {model_name} (ID: {model_id}) - Needs update (current: {current_fieldset_name})")
                models_needing_fieldset.append(model)
        
        print(f"\n📊 MODEL FIELDSET ASSIGNMENT SUMMARY:")
        print(f"   ✅ Already correct: {len(models_with_correct_fieldset)} models")
        print(f"   🔄 Need update: {len(models_needing_fieldset)} models")
        
        return True, models_with_correct_fieldset, models_needing_fieldset
    
    def validate_all_models_fieldset_assignment(self, fieldset_id):
        """
        Check ALL models in the system for fieldset assignment
        """
        print(f"\n🔍 VALIDATING ALL MODELS FIELDSET ASSIGNMENTS")
        print("=" * 50)
        
        # Get ALL models
        try:
            endpoint = f"{self.base_url}/api/v1/models"
            params = {'limit': 500}  # Get all models
            
            response = requests.get(endpoint, headers=self.headers, params=params, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                all_models = data.get('rows', [])
            else:
                print(f"❌ Failed to fetch models: {response.status_code}")
                return False, [], []
                
        except Exception as e:
            print(f"❌ Error fetching models: {e}")
            return False, [], []
        
        if not all_models:
            print(f"❌ No models found in the system")
            return False, [], []
        
        print(f"📱 Found {len(all_models)} total models in system")
        
        # Check fieldset assignments
        models_with_correct_fieldset = []
        models_needing_fieldset = []
        
        for model in all_models:
            model_id = model.get('id')
            model_name = model.get('name')
            current_fieldset_id = model.get('fieldset_id')
            
            if current_fieldset_id == fieldset_id:
                models_with_correct_fieldset.append(model)
            else:
                models_needing_fieldset.append(model)
        
        print(f"\n📊 ALL MODELS FIELDSET ASSIGNMENT SUMMARY:")
        print(f"   ✅ Already correct: {len(models_with_correct_fieldset)} models")
        print(f"   🔄 Need update: {len(models_needing_fieldset)} models")
        
        # Show some examples
        if models_needing_fieldset:
            print(f"\n🔄 Examples of models to update:")
            for model in models_needing_fieldset[:5]:  # Show first 5
                current_fieldset_name = "None" if not model.get('fieldset_id') else f"ID {model.get('fieldset_id')}"
                print(f"   • {model.get('name')} (current: {current_fieldset_name})")
            if len(models_needing_fieldset) > 5:
                print(f"   ... and {len(models_needing_fieldset) - 5} more models")
        
        return True, models_with_correct_fieldset, models_needing_fieldset
    
    def create_fieldset(self, name, field_ids):
        """Create a new fieldset with specified fields"""
        print(f"➕ Creating fieldset: {name}")
        
        endpoint = f"{self.base_url}/api/v1/fieldsets"
        payload = {
            "name": name,
            "fields": field_ids
        }
        
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    fieldset_id = data['payload']['id']
                    print(f"✅ Created fieldset: {name} (ID: {fieldset_id})")
                    return fieldset_id
                else:
                    print(f"❌ Failed to create fieldset: {data.get('messages', 'Unknown error')}")
                    return None
            else:
                print(f"❌ Failed to create fieldset: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating fieldset: {e}")
            return None
    
    def update_model_fieldset(self, model_id, fieldset_id, model_name):
        """Update a model to use the specified fieldset"""
        print(f"🔄 Updating model {model_name} (ID: {model_id}) to use fieldset {fieldset_id}")
        
        endpoint = f"{self.base_url}/api/v1/models/{model_id}"
        payload = {
            "fieldset_id": fieldset_id
        }
        
        try:
            response = requests.patch(endpoint, json=payload, headers=self.headers, verify=self.verify_ssl, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    print(f"✅ Updated model: {model_name}")
                    return True
                else:
                    print(f"❌ Failed to update model {model_name}: {data.get('messages', 'Unknown error')}")
                    return False
            else:
                print(f"❌ Failed to update model {model_name}: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating model {model_name}: {e}")
            return False
    
    def interactive_fieldset_creation(self):
        """
        Comprehensive fieldset validation and creation process
        Includes step-by-step validation with detailed progress reporting
        """
        print("🚀 COMPREHENSIVE FIELDSET VALIDATION & CREATION WIZARD")
        print("=" * 70)
        
        # STEP 1: Validate Custom Fields
        print(f"\n📋 STEP 1: VALIDATING CUSTOM FIELDS")
        print("-" * 50)
        fields_valid, valid_field_ids = self.validate_custom_fields()
        if not fields_valid:
            print(f"\n❌ PROCESS STOPPED: Custom fields validation failed")
            print(f"   Please fix the issues above and try again")
            return False
        
        # STEP 2: Get Categories and Selection
        print(f"\n📂 STEP 2: CATEGORY SELECTION")
        print("-" * 50)
        categories = self.get_categories()
        if not categories:
            print("❌ No categories found. Cannot proceed.")
            return False
        
        print("Available Categories:")
        for i, category in enumerate(categories, 1):
            cat_type = category.get('category_type', 'unknown')
            print(f"{i:2d}. {category.get('name', 'N/A')} (ID: {category.get('id', 'N/A')}) - Type: {cat_type}")
        
        print("\n🎯 Select categories for fieldset assignment:")
        print("   Enter category numbers separated by commas (e.g., 1,3,7)")
        
        while True:
            try:
                selection = input("\n➤ Category numbers: ").strip()
                if not selection:
                    print("❌ Please enter at least one category number.")
                    continue
                
                # Parse selection
                selected_indices = [int(x.strip()) - 1 for x in selection.split(',')]
                
                # Validate selection
                if all(0 <= idx < len(categories) for idx in selected_indices):
                    selected_categories = [categories[idx] for idx in selected_indices]
                    category_ids = [cat['id'] for cat in selected_categories]
                    
                    print(f"\n✅ Selected categories:")
                    for cat in selected_categories:
                        print(f"   • {cat['name']} (ID: {cat['id']})")
                    break
                else:
                    print("❌ Invalid selection. Please enter valid category numbers.")
                    
            except ValueError:
                print("❌ Please enter numbers separated by commas.")
            except EOFError:
                print("\n❌ Interactive input required. Please run this command in an interactive terminal.")
                return False
        
        # STEP 3: Get Fieldset Name
        print(f"\n📋 STEP 3: FIELDSET CONFIGURATION")
        print("-" * 50)
        while True:
            try:
                fieldset_name = input("➤ Enter name for fieldset: ").strip()
                if fieldset_name:
                    break
                print("❌ Please enter a valid fieldset name.")
            except EOFError:
                print("\n❌ Interactive input required. Please run this command in an interactive terminal.")
                return False
        
        # STEP 4: Validate/Create Fieldset
        print(f"\n🔍 STEP 4: FIELDSET VALIDATION")
        print("-" * 50)
        fieldset_exists, fieldset_id = self.validate_fieldset(fieldset_name, valid_field_ids)
        
        if not fieldset_exists:
            # Need to create fieldset
            print(f"\n➕ Creating new fieldset: '{fieldset_name}'")
            fieldset_id = self.create_fieldset(fieldset_name, valid_field_ids)
            if not fieldset_id:
                print("❌ Failed to create fieldset.")
                return False
            print(f"✅ Successfully created fieldset '{fieldset_name}' (ID: {fieldset_id})")
        
        # STEP 5: Validate Model Assignments  
        print(f"\n🔍 STEP 5: MODEL VALIDATION")
        print("-" * 50)
        models_valid, models_correct, models_needing_update = self.validate_models_fieldset_assignment(category_ids, fieldset_id)
        
        # If no models in categories, offer to update ALL models
        if not models_valid:
            print(f"\n💡 No models found in selected categories, but found {self.get_total_models_count()} total models")
            print(f"   Would you like to update ALL models to use this fieldset instead?")
            
            try:
                use_all_models = input("❓ Update ALL models to use fieldset? (y/N): ").strip().lower()
                if use_all_models == 'y':
                    print(f"\n🔄 Switching to ALL MODELS mode...")
                    models_valid, models_correct, models_needing_update = self.validate_all_models_fieldset_assignment(fieldset_id)
                    if not models_valid:
                        print(f"\n❌ PROCESS STOPPED: Failed to fetch models")
                        return False
                else:
                    print(f"\n❌ PROCESS STOPPED: No models to update")
                    return False
            except EOFError:
                print("\n❌ Interactive input required. Please run this command in an interactive terminal.")
                return False
        
        if not models_needing_update:
            print(f"\n🎉 PERFECT! NOTHING TO DO!")
            print("=" * 50)
            print(f"✅ Fieldset '{fieldset_name}' is already assigned to ALL {len(models_correct)} models")
            print(f"✅ All models in selected categories are properly configured")
            print(f"📋 Categories: {', '.join([cat['name'] for cat in selected_categories])}")
            return True
        
        # STEP 6: Show Summary and Confirm
        total_models = len(models_correct) + len(models_needing_update)
        print(f"\n📊 STEP 6: FINAL SUMMARY")
        print("-" * 50)
        print(f"   Fieldset: '{fieldset_name}' (ID: {fieldset_id})")
        print(f"   Fields: {len(valid_field_ids)} custom fields")
        print(f"   Categories: {', '.join([cat['name'] for cat in selected_categories])}")
        print(f"   Models already correct: {len(models_correct)}")
        print(f"   Models needing update: {len(models_needing_update)}")
        print(f"   Total models: {total_models}")
        
        if models_needing_update:
            print(f"\n🔄 Models to update:")
            for model in models_needing_update:
                current_fieldset = "None" if not model.get('fieldset_id') else f"ID {model.get('fieldset_id')}"
                print(f"   • {model.get('name')} (current: {current_fieldset})")
        
        try:
            confirm = input(f"\n❓ Update {len(models_needing_update)} models? (y/N): ").strip().lower()
            if confirm != 'y':
                print("❌ Operation cancelled.")
                return False
        except EOFError:
            print("\n❌ Interactive input required. Please run this command in an interactive terminal.")
            return False
        
        # STEP 7: Update Models
        print(f"\n🔄 STEP 7: UPDATING MODELS")
        print("-" * 50)
        success_count = 0
        
        for model in models_needing_update:
            if self.update_model_fieldset(model['id'], fieldset_id, model['name']):
                success_count += 1
        
        # Final Summary
        print(f"\n🎉 PROCESS COMPLETED!")
        print("=" * 50)
        print(f"✅ Fieldset: '{fieldset_name}' (ID: {fieldset_id})")
        print(f"✅ Custom Fields: {len(valid_field_ids)} fields")
        print(f"✅ Models Updated: {success_count}/{len(models_needing_update)}")
        print(f"✅ Total Models Using Fieldset: {len(models_correct) + success_count}/{total_models}")
        
        if success_count == len(models_needing_update):
            print("🏆 ALL UPDATES SUCCESSFUL!")
        else:
            failed_count = len(models_needing_update) - success_count
            print(f"⚠️  {failed_count} models failed to update")
        
        return True

if __name__ == "__main__":
    # Test the fieldset manager
    manager = FieldsetManager(verify_ssl=False)
    manager.interactive_fieldset_creation()