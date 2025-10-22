#!/usr/bin/env python3
"""
Monitor Model Migration Utility
Migrates all monitors from old model to new model in Snipe-IT

Usage:
    python migrate_monitor_model.py --old "HP M24fe" --new "HP M24fe FHD"
"""

import argparse
import requests
import urllib3
from typing import Optional, List, Dict, Any

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SnipeITMigrator:
    def __init__(self, api_url: str, api_key: str, verify_ssl: bool = True):
        self.api_url = api_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        self.verify_ssl = verify_ssl
    
    def find_model_by_name(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Find model by exact name"""
        print(f"[*] Searching for model: {model_name}")
        
        response = self.session.get(
            f"{self.api_url}/api/v1/models",
            params={'search': model_name, 'limit': 500},
            verify=self.verify_ssl
        )
        
        if response.status_code != 200:
            print(f"[ERROR] Failed to search models: {response.status_code}")
            return None
        
        data = response.json()
        for model in data.get('rows', []):
            if model.get('name', '').strip() == model_name.strip():
                print(f"[OK] Found model ID: {model['id']} - {model['name']}")
                return model
        
        print(f"[WARNING] Model not found: {model_name}")
        return None
    
    def get_assets_by_model(self, model_id: int) -> List[Dict[str, Any]]:
        """Get ALL assets using a specific model - including archived, deleted, all statuses"""
        print(f"[*] Fetching ALL assets for model ID: {model_id}")
        print(f"[*] Searching across all statuses (active, archived, deleted, etc.)...")
        
        all_assets = []
        seen_ids = set()
        
        # Search with different status filters to catch everything
        status_filters = [
            ('all', 'All statuses'),
            ('Deleted', 'Deleted'),
            ('Archived', 'Archived'),
            (None, 'Default (active only)')
        ]
        
        for status_value, status_name in status_filters:
            params = {
                'model_id': model_id,
                'limit': 500,
                'offset': 0
            }
            
            if status_value:
                params['status'] = status_value
            
            while True:
                response = self.session.get(
                    f"{self.api_url}/api/v1/hardware",
                    params=params,
                    verify=self.verify_ssl
                )
                
                if response.status_code != 200:
                    break
                
                data = response.json()
                rows = data.get('rows', [])
                
                # Track unique assets
                for asset in rows:
                    asset_id = asset['id']
                    if asset_id not in seen_ids:
                        seen_ids.add(asset_id)
                        all_assets.append(asset)
                
                total = data.get('total', 0)
                if len(rows) < params['limit'] or params['offset'] + len(rows) >= total:
                    break
                
                params['offset'] += params['limit']
        
        print(f"[OK] Found {len(all_assets)} unique asset(s) using this model")
        return all_assets
    
    def update_asset_model(self, asset_id: int, new_model_id: int, asset_tag: str) -> bool:
        """Update an asset's model"""
        payload = {
            'model_id': new_model_id
        }
        
        response = self.session.patch(
            f"{self.api_url}/api/v1/hardware/{asset_id}",
            json=payload,
            verify=self.verify_ssl
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                return True
        
        print(f"[WARNING] Failed to update asset {asset_tag} (ID: {asset_id}): {response.text[:100]}")
        return False
    
    def migrate_model(self, old_model_name: str, new_model_name: str, dry_run: bool = False) -> None:
        """Migrate all assets from old model to new model"""
        print("\n" + "=" * 70)
        print(f"  Monitor Model Migration")
        print("=" * 70)
        print(f"Old Model: {old_model_name}")
        print(f"New Model: {new_model_name}")
        print(f"Dry Run: {'YES (no changes will be made)' if dry_run else 'NO (will update assets)'}")
        print("=" * 70 + "\n")
        
        # Find old model
        old_model = self.find_model_by_name(old_model_name)
        if not old_model:
            print(f"[ERROR] Old model not found: {old_model_name}")
            return
        
        old_model_id = old_model['id']
        
        # Find new model
        new_model = self.find_model_by_name(new_model_name)
        if not new_model:
            print(f"[ERROR] New model not found: {new_model_name}")
            return
        
        new_model_id = new_model['id']
        
        print()
        
        # Get all assets using old model
        assets = self.get_assets_by_model(old_model_id)
        
        if not assets:
            print("\n[*] No assets to migrate")
            return
        
        print(f"\n[*] Assets to migrate: {len(assets)}")
        print()
        
        # Confirm migration
        if not dry_run:
            response = input(f"Continue with migration of {len(assets)} asset(s)? [y/N]: ")
            if response.lower() != 'y':
                print("[*] Migration cancelled")
                return
            print()
        
        # Migrate each asset
        success_count = 0
        fail_count = 0
        
        for i, asset in enumerate(assets, start=1):
            asset_id = asset['id']
            asset_tag = asset.get('asset_tag', 'N/A')
            asset_name = asset.get('name', 'N/A')
            status = asset.get('status_label', {}).get('name', 'Unknown')
            
            # Check for special states
            status_flags = []
            if asset.get('deleted_at'):
                status_flags.append('DELETED')
            if asset.get('archived'):
                status_flags.append('ARCHIVED')
            
            status_suffix = f" [{', '.join(status_flags)}]" if status_flags else ""
            
            print(f"[{i}/{len(assets)}] Migrating: {asset_tag} - {asset_name} ({status}){status_suffix}")
            
            if dry_run:
                print(f"  [DRY RUN] Would update asset ID {asset_id} to model ID {new_model_id}")
                success_count += 1
            else:
                if self.update_asset_model(asset_id, new_model_id, asset_tag):
                    print(f"  [OK] Updated successfully")
                    success_count += 1
                else:
                    print(f"  [ERROR] Update failed")
                    fail_count += 1
        
        # Summary
        print("\n" + "=" * 70)
        print("  Migration Complete")
        print("=" * 70)
        print(f"Total Assets: {len(assets)}")
        print(f"Successful: {success_count}")
        print(f"Failed: {fail_count}")
        print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Migrate monitors from old model to new model in Snipe-IT',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Dry run (preview changes without making them)
  python migrate_monitor_model.py --old "HP M24fe" --new "HP M24fe FHD" --dry-run
  
  # Actual migration
  python migrate_monitor_model.py --old "HP M24fe" --new "HP M24fe FHD"
  
  # With custom credentials
  python migrate_monitor_model.py --old "HP M24fe" --new "HP M24fe FHD" \\
      --url https://snipeit.server.com --api-key YOUR_KEY
        '''
    )
    
    parser.add_argument(
        '--old',
        required=True,
        help='Old model name (exact match required)'
    )
    
    parser.add_argument(
        '--new',
        required=True,
        help='New model name (exact match required)'
    )
    
    parser.add_argument(
        '--url',
        help='Snipe-IT server URL (or use build-time credentials)'
    )
    
    parser.add_argument(
        '--api-key',
        help='API key (or use build-time credentials)'
    )
    
    parser.add_argument(
        '--ignore-ssl',
        action='store_true',
        help='Ignore SSL certificate verification'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without making them'
    )
    
    args = parser.parse_args()
    
    # Try to use build-time credentials first
    api_url = args.url
    api_key = args.api_key
    verify_ssl = not args.ignore_ssl
    
    if not api_url or not api_key:
        try:
            from core.build_secrets import BUILD_SERVER_URL, BUILD_API_KEY, BUILD_IGNORE_SSL
            api_url = api_url or BUILD_SERVER_URL
            api_key = api_key or BUILD_API_KEY
            if BUILD_IGNORE_SSL:
                verify_ssl = False
            print("[*] Using build-time credentials")
        except (ImportError, AttributeError):
            pass
    
    if not api_url or not api_key:
        print("[ERROR] Missing credentials. Provide --url and --api-key or use build-time credentials")
        return 1
    
    # Create migrator and run
    migrator = SnipeITMigrator(api_url, api_key, verify_ssl)
    migrator.migrate_model(args.old, args.new, args.dry_run)
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
