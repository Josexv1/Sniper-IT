#!/usr/bin/env python3
"""
OS-aware data collection, hostname-based asset detection, and verified data sync
"""

import argparse
import sys
import urllib3
from collectors.system_collector import SystemDataCollector  
from managers.asset_manager import AssetManager
from managers.fieldset_manager import FieldsetManager
from config.settings import GlobalSettings
import config.constants as c

def test_snipe_it_connection(verify_ssl=True):
    """Test connection to Snipe-IT API"""
    print("🔍 Testing Snipe-IT API connection...")
    
    try:
        config = GlobalSettings().config
        api_url = config['SERVER']['site']
        api_key = config['SERVER']['api_key']
        
        print(f"📍 API URL: {api_url}")
        print(f"🔑 API Key: {api_key[:20]}...")
        
        import requests
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json"
        }
        
        base_url = api_url.replace('/api/v1', '')
        test_url = base_url + '/api/v1/hardware?limit=1'
        
        response = requests.get(test_url, headers=headers, verify=verify_ssl, timeout=10)
        
        if response.status_code == 200:
            print("✅ API connection: SUCCESS")
            return True
        else:
            print(f"❌ API connection failed: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ API connection error: {e}")
        return False

def main():
    print(f"🚀 {c.APPLICATION_NAME} - Enhanced Asset Sync Tool")
    print(f"📦 Version: {c.VERSION}")
    print("=" * 60)
    
    parser = argparse.ArgumentParser(description=f"{c.APPLICATION_NAME} - Enhanced Asset Sync Tool")
    parser.add_argument('-issl', '--ignore-ssl', action='store_true', 
                       help='Ignore SSL certificate verification (useful for self-signed certificates)')
    parser.add_argument('--test-only', action='store_true',
                       help='Run data collection test without syncing to Snipe-IT')
    parser.add_argument('--generate-fields', action='store_true',
                       help='Generate and assign fieldsets to models by category')
    args = parser.parse_args()

    verify_ssl = not args.ignore_ssl
    
    if not verify_ssl:
        print("⚠️  Warning: SSL certificate verification is disabled.")
        # Suppress SSL warnings when -issl flag is used
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        # Step 1: Test API connection
        if not test_snipe_it_connection(verify_ssl):
            print("❌ Cannot proceed without valid API connection")
            return 1
        
        # Handle --generate-fields flag
        if args.generate_fields:
            print("\n🔄 FIELDSET GENERATION MODE")
            print("=" * 50)
            
            fieldset_manager = FieldsetManager(verify_ssl=verify_ssl)
            success = fieldset_manager.interactive_fieldset_creation()
            
            if success:
                print("\n🎉 Fieldset generation completed successfully!")
                return 0
            else:
                print("\n❌ Fieldset generation failed or was cancelled")
                return 1
        
        # Step 2: Collect system data
        print("\n🔄 PHASE 1: SYSTEM DATA COLLECTION")
        print("=" * 50)
        
        collector = SystemDataCollector()
        system_data = collector.collect_all_data()
        
        if args.test_only:
            print("\n✅ Test completed successfully! Data collection working.")
            return 0
        
        # Step 3: Process asset in Snipe-IT
        print("\n🔄 PHASE 2: SNIPE-IT ASSET PROCESSING")
        print("=" * 50)
        
        asset_manager = AssetManager(verify_ssl=verify_ssl)
        result = asset_manager.process_asset(system_data)
        
        if result:
            verification = result.get('verification', {})
            success_rate = verification.get('success_rate', 0)
            
            print(f"\n🎉 SYNC COMPLETED SUCCESSFULLY!")
            print(f"📊 Asset ID: {result['asset_id']}")
            print(f"📊 Custom Fields Success Rate: {success_rate:.1f}%")
            
            if success_rate >= 80:
                print("✅ Excellent sync quality!")
                return 0
            elif success_rate >= 60:
                print("⚠️  Good sync - some fields may need attention")
                return 0
            else:
                print("❌ Poor sync quality - please check configuration")
                return 1
        else:
            print("❌ Asset processing failed")
            return 1
            
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())