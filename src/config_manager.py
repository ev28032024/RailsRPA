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
            
            if not self.profiles:
                logger.error("No profiles defined in configuration")
                return False
            
            logger.info(f"Loaded {len(self.profiles)} profiles from configuration")
            
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
            # Validate profiles
            for idx, profile in enumerate(self.profiles):
                if 'profile_id' not in profile:
                    logger.error(f"Profile at index {idx} missing 'profile_id'")
                    return False
                
                if 'image_name' not in profile:
                    logger.error(f"Profile {profile.get('profile_id')} missing 'image_name'")
                    return False
            
            # Check for duplicate profile IDs
            profile_ids = [p['profile_id'] for p in self.profiles]
            if len(profile_ids) != len(set(profile_ids)):
                logger.error("Duplicate profile IDs found in configuration")
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

