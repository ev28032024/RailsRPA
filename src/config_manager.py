"""
Configuration Management Module
Handles loading and validation of configuration files
"""

import yaml
import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """Configuration manager for the automation system"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration manager
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = config_path
        self.config = None
        self.profiles = []
        self.settings = {}
        
    def load(self) -> bool:
        """
        Load configuration from YAML file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(self.config_path):
                logger.error(f"Configuration file not found: {self.config_path}")
                return False
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            if not self.config:
                logger.error("Configuration file is empty")
                return False
            
            self.profiles = self.config.get('profiles', [])
            self.settings = self.config.get('settings', {})
            
            # Check if Google Sheets is enabled - if so, profiles can be empty
            google_sheets_enabled = self.settings.get('google_sheets', {}).get('enabled', False)
            
            if not self.profiles and not google_sheets_enabled:
                logger.error("No profiles defined in configuration (and Google Sheets is not enabled)")
                return False
            
            if self.profiles:
                logger.info(f"Loaded {len(self.profiles)} profiles from configuration")
            elif google_sheets_enabled:
                logger.info("Using Google Sheets for profile management")
            
            # Validate configuration
            if not self._validate():
                return False
            
            return True
            
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False
    
    def _validate(self) -> bool:
        """
        Validate configuration data
        
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check if Google Sheets is enabled
            google_sheets_enabled = self.settings.get('google_sheets', {}).get('enabled', False)
            
            # Validate profiles (only if not using Google Sheets exclusively)
            if self.profiles:
                for idx, profile in enumerate(self.profiles):
                    # Must have either profile_id or serial_number
                    has_profile_id = 'profile_id' in profile and profile['profile_id']
                    has_serial_number = 'serial_number' in profile and profile['serial_number'] is not None
                    
                    if not has_profile_id and not has_serial_number:
                        logger.error(f"Profile at index {idx} missing both 'profile_id' and 'serial_number'")
                        return False
                    
                    if 'image_name' not in profile:
                        identifier = profile.get('profile_id') or f"serial #{profile.get('serial_number')}"
                        logger.error(f"Profile {identifier} missing 'image_name'")
                        return False
                
                # Check for duplicate profile IDs
                profile_ids = [p.get('profile_id') for p in self.profiles if p.get('profile_id')]
                if len(profile_ids) != len(set(profile_ids)):
                    logger.error("Duplicate profile IDs found in configuration")
                    return False
                
                # Check for duplicate serial numbers
                serial_numbers = [p.get('serial_number') for p in self.profiles if p.get('serial_number') is not None]
                if len(serial_numbers) != len(set(serial_numbers)):
                    logger.error("Duplicate serial numbers found in configuration")
                    return False
            
            # Validate required settings
            required_settings = ['adspower_api_host', 'discord_channel_url', 'images_dir']
            for setting in required_settings:
                if setting not in self.settings:
                    logger.error(f"Required setting '{setting}' not found in configuration")
                    return False
            
            # Validate images directory
            images_dir = self.get_images_dir()
            if not os.path.exists(images_dir):
                logger.error(f"Images directory does not exist: {images_dir}")
                return False
            
            # Validate Google Sheets config if enabled
            if google_sheets_enabled:
                gs_config = self.settings.get('google_sheets', {})
                if not gs_config.get('spreadsheet_id'):
                    logger.error("Google Sheets enabled but 'spreadsheet_id' is not set")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating configuration: {e}")
            return False
    
    def get_enabled_profiles(self) -> List[Dict[str, Any]]:
        """
        Get list of enabled profiles
        
        Returns:
            List of enabled profile configurations
        """
        return [p for p in self.profiles if p.get('enabled', True)]
    
    def get_profile_count(self, enabled_only: bool = True) -> int:
        """
        Get count of profiles
        
        Args:
            enabled_only: If True, count only enabled profiles
            
        Returns:
            Number of profiles
        """
        if enabled_only:
            return len(self.get_enabled_profiles())
        return len(self.profiles)
    
    def get_image_path(self, image_name: str) -> Optional[str]:
        """
        Get full path to an image file
        
        Args:
            image_name: Image filename (with or without extension)
            
        Returns:
            Full path to image file, or None if not found
        """
        if not image_name:
            logger.error("Image name is empty")
            return None
            
        images_dir = self.get_images_dir()
        
        # Check if images directory exists
        if not os.path.exists(images_dir):
            logger.error(f"Images directory does not exist: {images_dir}")
            return None
        
        # Try with common image extensions
        extensions = ['', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']
        
        for ext in extensions:
            if image_name.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
                # Already has extension
                image_path = os.path.join(images_dir, image_name)
                if os.path.exists(image_path) and os.path.isfile(image_path):
                    return os.path.abspath(image_path)
                # If has extension, don't try other extensions
                break
            else:
                # Try adding extension
                image_path = os.path.join(images_dir, f"{image_name}{ext}")
                if os.path.exists(image_path) and os.path.isfile(image_path):
                    return os.path.abspath(image_path)
        
        logger.debug(f"Image not found: {image_name} in {images_dir}")
        return None
    
    def get_images_dir(self) -> str:
        """Get images directory path"""
        return os.path.abspath(self.settings.get('images_dir', './images'))
    
    def get_adspower_host(self) -> str:
        """Get AdsPower API host"""
        return self.settings.get('adspower_api_host', 'http://local.adspower.net:50325')
    
    def get_discord_url(self) -> str:
        """Get Discord channel URL"""
        return self.settings.get('discord_channel_url', '')
    
    def get_timeout(self, timeout_name: str, default: int = 30) -> int:
        """Get timeout value in seconds"""
        return self.settings.get(timeout_name, default)
    
    def get_log_file(self) -> Optional[str]:
        """Get log file path"""
        return self.settings.get('log_file')
    
    def get_log_level(self) -> str:
        """Get log level"""
        return self.settings.get('log_level', 'INFO')

