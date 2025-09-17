# settings.py

import configparser
import os

from utils.common import resolve_path

class GlobalSettings:
    def __init__(self):
        self.config = self.get_config()
    
    def get_config(self):
        config_path = resolve_path('config.ini')
        
        if not os.path.exists(config_path):
            raise Exception(f"config.ini not found. Please create it at: {config_path}")

        config = configparser.ConfigParser()
        config.read(config_path)
        
        # Convert to dictionary format
        parsed_config = {}
        for section in config.sections():
            parsed_config[section] = dict(config[section])

        return parsed_config
