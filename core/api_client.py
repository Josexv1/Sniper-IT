"""
Sniper-IT Agent - Snipe-IT API Client
Centralized API wrapper for all Snipe-IT operations
"""

import requests
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin

from utils.exceptions import APIError
from cli.formatters import print_error, print_warning, print_info


class SnipeITClient:
    """
    Unified Snipe-IT API client
    Handles all HTTP requests, authentication, and error handling
    """
    
    def __init__(self, base_url: str, api_key: str, verify_ssl: bool = True):
        """
        Initialize Snipe-IT API client
        
        Args:
            base_url: Snipe-IT server URL (e.g., https://snipeit.company.com)
            api_key: API Bearer token
            verify_ssl: Whether to verify SSL certificates
        """
        # Clean up base URL
        self.base_url = base_url.rstrip('/')
        if '/api/v1' in self.base_url:
            self.base_url = self.base_url.replace('/api/v1', '')
        
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        
        # Standard headers for all requests
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json"
        }
    
    def _build_url(self, endpoint: str) -> str:
        """Build full API URL from endpoint"""
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'
        # Use simple concatenation instead of urljoin to avoid path issues
        return f"{self.base_url}/api/v1{endpoint}"
    
    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make HTTP request with error handling
        
        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            endpoint: API endpoint
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object
            
        Raises:
            APIError: If request fails
        """
        url = self._build_url(endpoint)
        
        # Add headers and SSL verification
        kwargs.setdefault('headers', self.headers)
        kwargs.setdefault('verify', self.verify_ssl)
        kwargs.setdefault('timeout', 30)
        
        try:
            response = requests.request(method, url, **kwargs)
            
            # Handle specific error codes
            if response.status_code == 401:
                raise APIError("Authentication failed - check your API key")
            elif response.status_code == 403:
                raise APIError("Permission denied - insufficient API permissions")
            elif response.status_code == 404:
                raise APIError(f"Endpoint not found: {endpoint}")
            elif response.status_code == 429:
                raise APIError("Rate limit exceeded - please try again later")
            elif response.status_code >= 500:
                raise APIError(f"Server error ({response.status_code}): {response.text}")
            
            return response
            
        except requests.exceptions.SSLError:
            raise APIError("SSL verification failed - use --issl to ignore SSL certificates")
        except requests.exceptions.ConnectionError:
            raise APIError(f"Connection failed - cannot reach {self.base_url}")
        except requests.exceptions.Timeout:
            raise APIError("Request timed out - server is not responding")
        except requests.exceptions.RequestException as e:
            raise APIError(f"Request failed: {e}")
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test API connection and return server info
        
        Returns:
            Dictionary with connection status and server info
        """
        try:
            response = self._request('GET', '/hardware', params={'limit': 1})
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'connected': True,
                    'total_assets': data.get('total', 0),
                    'server_url': self.base_url
                }
            else:
                return {
                    'connected': False,
                    'error': f"Status code: {response.status_code}"
                }
        except APIError as e:
            return {
                'connected': False,
                'error': str(e)
            }
    
    # ==================== HARDWARE (ASSETS) ====================
    
    def get_hardware(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get hardware assets list"""
        response = self._request('GET', '/hardware', params=params)
        return response.json()
    
    def get_hardware_by_id(self, asset_id: int) -> Dict[str, Any]:
        """Get specific hardware asset by ID"""
        response = self._request('GET', f'/hardware/{asset_id}')
        return response.json()
    
    def search_hardware(self, search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search for hardware assets
        
        Args:
            search_term: Search query
            limit: Maximum results
            
        Returns:
            List of matching assets
        """
        params = {
            'search': search_term,
            'limit': limit
        }
        data = self.get_hardware(params)
        return data.get('rows', [])
    
    def find_hardware_by_hostname(self, hostname: str) -> Optional[int]:
        """
        Find hardware asset by exact hostname match
        
        Args:
            hostname: Computer hostname
            
        Returns:
            Asset ID if found, None otherwise
        """
        assets = self.search_hardware(hostname, limit=50)
        
        for asset in assets:
            if asset.get('name', '').lower() == hostname.lower():
                return asset['id']
        
        return None
    
    def create_hardware(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create new hardware asset"""
        response = self._request('POST', '/hardware', json=payload)
        return response.json()
    
    def update_hardware(self, asset_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing hardware asset"""
        response = self._request('PATCH', f'/hardware/{asset_id}', json=payload)
        return response.json()
    
    def delete_hardware(self, asset_id: int) -> Dict[str, Any]:
        """Delete hardware asset"""
        response = self._request('DELETE', f'/hardware/{asset_id}')
        return response.json()
    
    def checkout_hardware(self, asset_id: int, checkout_to_type: str, 
                         assigned_id: int, status_id: int,
                         note: Optional[str] = None) -> Dict[str, Any]:
        """
        Checkout hardware asset to a user, location, or another asset
        
        Args:
            asset_id: Asset ID to checkout
            checkout_to_type: Type of checkout - 'user', 'asset', or 'location'
            assigned_id: ID of user, asset, or location to checkout to
            status_id: Status ID for the checkout
            note: Optional checkout note
            
        Returns:
            API response dictionary
        """
        payload = {
            'checkout_to_type': checkout_to_type,
            'status_id': status_id
        }
        
        # Add the appropriate assignment field based on type
        if checkout_to_type == 'user':
            payload['assigned_user'] = assigned_id
        elif checkout_to_type == 'asset':
            payload['assigned_asset'] = assigned_id
        elif checkout_to_type == 'location':
            payload['assigned_location'] = assigned_id
        
        if note:
            payload['note'] = note
        
        response = self._request('POST', f'/hardware/{asset_id}/checkout', json=payload)
        return response.json()
    
    def checkin_hardware(self, asset_id: int, status_id: Optional[int] = None, 
                        note: Optional[str] = None) -> Dict[str, Any]:
        """
        Check in hardware asset
        
        Args:
            asset_id: Asset ID to check in
            status_id: Optional status ID for the checkin
            note: Optional checkin note
            
        Returns:
            API response dictionary
        """
        payload = {}
        
        if status_id:
            payload['status_id'] = status_id
        if note:
            payload['note'] = note
        
        response = self._request('POST', f'/hardware/{asset_id}/checkin', json=payload)
        return response.json()
    
    # ==================== MANUFACTURERS ====================
    
    def get_manufacturers(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get manufacturers list"""
        response = self._request('GET', '/manufacturers', params=params)
        return response.json()
    
    def search_manufacturers(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for manufacturers"""
        params = {'search': search_term, 'limit': 50}
        data = self.get_manufacturers(params)
        return data.get('rows', [])
    
    def find_manufacturer_by_name(self, name: str) -> Optional[int]:
        """Find manufacturer by exact name match"""
        manufacturers = self.search_manufacturers(name)
        
        for mfg in manufacturers:
            if mfg.get('name', '').lower() == name.lower():
                return mfg['id']
        
        return None
    
    def create_manufacturer(self, name: str) -> Dict[str, Any]:
        """Create new manufacturer"""
        payload = {'name': name}
        response = self._request('POST', '/manufacturers', json=payload)
        return response.json()
    
    def find_or_create_manufacturer(self, name: str) -> int:
        """
        Find existing manufacturer or create new one
        
        Args:
            name: Manufacturer name
            
        Returns:
            Manufacturer ID
            
        Raises:
            APIError: If operation fails
        """
        # Try to find existing
        existing_id = self.find_manufacturer_by_name(name)
        if existing_id:
            return existing_id
        
        # Create new
        result = self.create_manufacturer(name)
        if result.get('status') == 'success':
            return result['payload']['id']
        else:
            raise APIError(f"Failed to create manufacturer: {result.get('messages', 'Unknown error')}")
    
    # ==================== MODELS ====================
    
    def get_models(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get models list"""
        response = self._request('GET', '/models', params=params)
        return response.json()
    
    def search_models(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for models"""
        params = {'search': search_term, 'limit': 50}
        data = self.get_models(params)
        return data.get('rows', [])
    
    def find_model_by_name(self, name: str, manufacturer_id: int) -> Optional[int]:
        """Find model by exact name match and manufacturer"""
        models = self.search_models(name)
        
        for model in models:
            if (model.get('name', '').lower() == name.lower() and
                model.get('manufacturer', {}).get('id') == manufacturer_id):
                return model['id']
        
        return None
    
    def create_model(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create new model"""
        response = self._request('POST', '/models', json=payload)
        return response.json()
    
    def update_model(self, model_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing model"""
        response = self._request('PATCH', f'/models/{model_id}', json=payload)
        return response.json()
    
    def get_model_by_id(self, model_id: int) -> Dict[str, Any]:
        """Get model details by ID"""
        response = self._request('GET', f'/models/{model_id}')
        return response.json()
    
    def find_or_create_model(self, name: str, model_number: str, 
                            manufacturer_id: int, category_id: int, 
                            fieldset_id: int) -> int:
        """
        Find existing model or create new one.
        If model exists but has wrong category, updates the category.
        This handles cases where a machine changes type (laptop→server).
        
        Args:
            name: Model name
            model_number: Model number/SKU
            manufacturer_id: Manufacturer ID
            category_id: Category ID
            fieldset_id: Fieldset ID
            
        Returns:
            Model ID
            
        Raises:
            APIError: If operation fails
        """
        # Try to find existing
        existing_id = self.find_model_by_name(name, manufacturer_id)
        if existing_id:
            # Check if category matches and update if needed
            try:
                model_data = self.get_model_by_id(existing_id)
                existing_category_id = model_data.get('category', {}).get('id')
                existing_category_name = model_data.get('category', {}).get('name', 'Unknown')
                
                # If category doesn't match, update it
                if existing_category_id != category_id:
                    update_payload = {
                        'category_id': category_id,
                        'fieldset_id': fieldset_id  # Update fieldset too in case it changed
                    }
                    result = self.update_model(existing_id, update_payload)
                    if result.get('status') != 'success':
                        raise APIError(f"Failed to update model category: {result.get('messages', 'Unknown error')}")
            except APIError:
                raise
            except Exception:
                # If we can't check/update, just return the existing ID
                pass
            
            return existing_id
        
        # Create new
        payload = {
            'name': name,
            'model_number': model_number,
            'manufacturer_id': manufacturer_id,
            'category_id': category_id,
            'fieldset_id': fieldset_id
        }
        
        result = self.create_model(payload)
        if result.get('status') == 'success':
            return result['payload']['id']
        else:
            raise APIError(f"Failed to create model: {result.get('messages', 'Unknown error')}")
    
    # ==================== CATEGORIES ====================
    
    def get_categories(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get categories list"""
        response = self._request('GET', '/categories', params=params)
        return response.json()
    
    # ==================== FIELDSETS ====================
    
    def get_fieldsets(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get fieldsets list"""
        response = self._request('GET', '/fieldsets', params=params)
        return response.json()
    
    # ==================== CUSTOM FIELDS ====================
    
    def get_fields(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get custom fields list"""
        response = self._request('GET', '/fields', params=params)
        return response.json()
    
    def create_field(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create new custom field"""
        response = self._request('POST', '/fields', json=payload)
        return response.json()
    
    # ==================== COMPANIES ====================
    
    def get_companies(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get companies list"""
        response = self._request('GET', '/companies', params=params)
        return response.json()
    
    # ==================== STATUS LABELS ====================
    
    def get_statuslabels(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get status labels list"""
        response = self._request('GET', '/statuslabels', params=params)
        return response.json()
