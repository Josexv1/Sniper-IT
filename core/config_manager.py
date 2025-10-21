"""
Sniper-IT Agent - Configuration Manager
Handles loading, saving, and validating YAML configuration
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from utils.exceptions import ConfigurationError
from core.constants import CONFIG_FILENAME


class ConfigManager:
    """Manages application configuration"""
    
    # Required configuration fields
    REQUIRED_FIELDS = [
        'server.url',
        'server.api_key',
        'defaults.status_id',
        'defaults.company_id',
        'defaults.laptop_category_id',
        'defaults.laptop_fieldset_id',
        'defaults.monitor_category_id',
        'defaults.monitor_fieldset_id'
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config manager
        
        Args:
            config_path: Path to config file (default: config.yaml in current directory)
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Config is in current working directory (where exe runs)
            self.config_path = Path.cwd() / CONFIG_FILENAME
        
        self.config: Optional[Dict[str, Any]] = None
    
    def exists(self) -> bool:
        """Check if configuration file exists"""
        return self.config_path.exists()
    
    def load(self) -> Dict[str, Any]:
        """
        Load and validate configuration from file
        
        Returns:
            Configuration dictionary
            
        Raises:
            ConfigurationError: If file doesn't exist or validation fails
        """
        if not self.exists():
            raise ConfigurationError(
                f"Configuration file not found: {self.config_path}\n"
                f"Run 'Sniper-IT-Agent.exe --setup' to create it."
            )
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML format: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load config: {e}")
        
        # Validate structure
        self.validate(config)
        self.config = config
        return config
    
    def save(self, config: Dict[str, Any]) -> None:
        """
        Save configuration to file
        
        Args:
            config: Configuration dictionary to save
            
        Raises:
            ConfigurationError: If save fails
        """
        try:
            # Validate before saving
            self.validate(config)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(
                    config, 
                    f, 
                    default_flow_style=False, 
                    sort_keys=False,
                    allow_unicode=True,
                    indent=2
                )
            
            self.config = config
        except Exception as e:
            raise ConfigurationError(f"Failed to save config: {e}")
    
    def validate(self, config: Dict[str, Any]) -> None:
        """
        Validate configuration structure
        
        Args:
            config: Configuration to validate
            
        Raises:
            ConfigurationError: If validation fails
        """
        if not isinstance(config, dict):
            raise ConfigurationError("Configuration must be a dictionary")
        
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            value = self._get_nested_value(config, field)
            if value is None:
                raise ConfigurationError(f"Missing required field: {field}")
        
        # Validate server URL
        server_url = config.get('server', {}).get('url', '')
        if not server_url.startswith(('http://', 'https://')):
            raise ConfigurationError("Server URL must start with http:// or https://")
        
        # Validate API key exists and is not empty
        api_key = config.get('server', {}).get('api_key', '')
        if not api_key or api_key.strip() == '':
            raise ConfigurationError("API key cannot be empty")
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """
        Get nested dictionary value using dot notation
        
        Args:
            data: Dictionary to search
            path: Dot-separated path (e.g., 'server.url')
            
        Returns:
            Value at path or None if not found
        """
        keys = path.split('.')
        value = data
        
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        
        return value
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation path
        
        Args:
            path: Dot-separated path (e.g., 'server.url')
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        if not self.config:
            raise ConfigurationError("Configuration not loaded. Call load() first.")
        
        value = self._get_nested_value(self.config, path)
        return value if value is not None else default
    
    def get_server_config(self) -> Dict[str, Any]:
        """Get server configuration section"""
        if not self.config:
            raise ConfigurationError("Configuration not loaded")
        return self.config.get('server', {})
    
    def get_defaults(self) -> Dict[str, Any]:
        """Get defaults configuration section"""
        if not self.config:
            raise ConfigurationError("Configuration not loaded")
        return self.config.get('defaults', {})
    
    def get_custom_fields(self) -> Dict[str, Any]:
        """Get custom fields configuration section"""
        if not self.config:
            raise ConfigurationError("Configuration not loaded")
        return self.config.get('custom_fields', {})


def create_default_config() -> Dict[str, Any]:
    """
    Create a default configuration template
    
    Returns:
        Default configuration dictionary
    """
    return {
        'server': {
            'url': 'https://your-snipeit.com',
            'api_key': 'your_api_key_here',
            'verify_ssl': True
        },
        'defaults': {
            'status_id': 2,
            'company_id': 1,
            'laptop_category_id': 2,
            'laptop_fieldset_id': 1,
            'monitor_category_id': 5,
            'monitor_fieldset_id': 2
        },
        'custom_fields': {
            'basic_system_fields': {
                'operating_system': {
                    'enabled': True,
                    'db_column': '_snipeit_operating_system_3',
                    'display_name': 'Operating System'
                },
                'os_install_date': {
                    'enabled': True,
                    'db_column': '_snipeit_os_install_date_4',
                    'display_name': 'OS Install Date'
                },
                'memory_ram': {
                    'enabled': True,
                    'db_column': '_snipeit_memory_ram_10',
                    'display_name': 'Memory / RAM'
                },
                'ram_usage': {
                    'enabled': True,
                    'db_column': '_snipeit_ram_usage_11',
                    'display_name': 'RAM Usage'
                },
                'bios_release_date': {
                    'enabled': True,
                    'db_column': '_snipeit_bios_release_date_12',
                    'display_name': 'BIOS Release Date'
                },
                'ip_address': {
                    'enabled': True,
                    'db_column': '_snipeit_ip_address_13',
                    'display_name': 'IP Address'
                },
                'processor_cpu': {
                    'enabled': True,
                    'db_column': '_snipeit_processor_cpu_14',
                    'display_name': 'Processor / CPU'
                },
                'username': {
                    'enabled': True,
                    'db_column': '_snipeit_windows_username_15',
                    'display_name': 'Windows Username'
                },
                'mac_address': {
                    'enabled': True,
                    'db_column': '_snipeit_mac_address_1',
                    'display_name': 'MAC Address'
                },
                'total_storage': {
                    'enabled': True,
                    'db_column': '_snipeit_total_storage_6',
                    'display_name': 'Total Storage'
                },
                'storage_information': {
                    'enabled': True,
                    'db_column': '_snipeit_storage_information_7',
                    'display_name': 'Storage Information'
                },
                'disk_space_used': {
                    'enabled': True,
                    'db_column': '_snipeit_disk_space_used_13',
                    'display_name': 'Disk Space Used'
                },
                'agent_version': {
                    'enabled': True,
                    'db_column': '_snipeit_agent_version_14',
                    'display_name': 'Agent Version'
                }
            },
            'optional_fields': {
                'cpu_temperature': {
                    'enabled': True,
                    'db_column': '_snipeit_cpu_temperature_20',
                    'display_name': 'CPU Temperature'
                },
                'system_uptime': {
                    'enabled': True,
                    'db_column': '_snipeit_uptime_21',
                    'display_name': 'Uptime'
                },
                'screen_size': {
                    'enabled': True,
                    'db_column': '_snipeit_screen_size_22',
                    'display_name': 'Screen Size'
                }
            }
        },
        'monitor_custom_fields': {
            'resolution': {
                'enabled': True,
                'db_column': '_snipeit_resolution_30',
                'display_name': 'Resolution'
            },
            'native_resolution': {
                'enabled': True,
                'db_column': '_snipeit_native_resolution_31',
                'display_name': 'Native Resolution'
            },
            'refresh_rate': {
                'enabled': True,
                'db_column': '_snipeit_refresh_rate_32',
                'display_name': 'Refresh Rate'
            },
            'connection_interface': {
                'enabled': True,
                'db_column': '_snipeit_connection_interface_33',
                'display_name': 'Connection Interface'
            },
            'bit_depth': {
                'enabled': True,
                'db_column': '_snipeit_bit_depth_34',
                'display_name': 'Bit Depth'
            },
            'monitor_screen_size': {
                'enabled': True,
                'db_column': '_snipeit_monitor_screen_size_35',
                'display_name': 'Monitor Screen Size'
            }
        },
        'metadata': {
            'app_name': 'Sniper-IT Agent',
            'version': '2.0.0',
            'last_updated': '2025-10-21'
        }
    }
