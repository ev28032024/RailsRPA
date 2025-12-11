"""
AdsPower API Integration Module
Handles communication with AdsPower API for profile management
"""

import requests
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class AdsPowerAPI:
    """AdsPower API Client for profile management"""
    
    def __init__(self, api_host: str = "http://local.adspower.net:50325"):
        """
        Initialize AdsPower API client
        
        Args:
            api_host: AdsPower API host URL
        """
        self.api_host = api_host.rstrip('/')
        self.session = requests.Session()
        logger.info(f"AdsPower API initialized with host: {self.api_host}")
    
    def start_profile(self, profile_id: str) -> Tuple[bool, Optional[Dict]]:
        """
        Start an AdsPower profile and get WebDriver connection info
        
        Args:
            profile_id: AdsPower profile ID
            
        Returns:
            Tuple of (success, connection_info)
            connection_info contains 'ws_endpoint' and 'debug_port'
        """
        if not profile_id:
            logger.error("Profile ID is empty")
            return False, None
            
        try:
            url = f"{self.api_host}/api/v1/browser/start"
            params = {
                "user_id": profile_id,
                "open_tabs": "0"  # Don't open default tabs
            }
            
            logger.info(f"Starting AdsPower profile: {profile_id}")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("code") == 0:
                result = data.get("data", {})
                if not result:
                    logger.error(f"Empty data in response for profile {profile_id}")
                    return False, None
                    
                ws_dict = result.get("ws", {})
                ws_endpoint = ws_dict.get("playwright") if ws_dict else None
                debug_port = result.get("debug_port")
                
                if not ws_endpoint:
                    logger.error(f"No WebSocket endpoint in response for profile {profile_id}")
                    return False, None
                
                connection_info = {
                    "ws_endpoint": ws_endpoint,
                    "debug_port": debug_port,
                    "webdriver": result.get("webdriver")
                }
                
                logger.info(f"Profile {profile_id} started successfully")
                logger.debug(f"Connection info: {connection_info}")
                return True, connection_info
            else:
                error_msg = data.get("msg", "Unknown error")
                logger.error(f"Failed to start profile {profile_id}: {error_msg}")
                return False, None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while starting profile {profile_id}: {e}")
            return False, None
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid response format for profile {profile_id}: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error while starting profile {profile_id}: {e}")
            return False, None
    
    def close_profile(self, profile_id: str) -> bool:
        """
        Close an AdsPower profile
        
        Args:
            profile_id: AdsPower profile ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.api_host}/api/v1/browser/stop"
            params = {"user_id": profile_id}
            
            logger.info(f"Closing AdsPower profile: {profile_id}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("code") == 0:
                logger.info(f"Profile {profile_id} closed successfully")
                return True
            else:
                error_msg = data.get("msg", "Unknown error")
                logger.warning(f"Failed to close profile {profile_id}: {error_msg}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while closing profile {profile_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while closing profile {profile_id}: {e}")
            return False
    
    def check_profile_status(self, profile_id: str) -> Optional[str]:
        """
        Check if a profile is running
        
        Args:
            profile_id: AdsPower profile ID
            
        Returns:
            'Active' if running, 'Inactive' if not, None on error
        """
        try:
            url = f"{self.api_host}/api/v1/browser/active"
            params = {"user_id": profile_id}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("code") == 0:
                status = data.get("data", {}).get("status")
                return status
            return None
                
        except Exception as e:
            logger.debug(f"Error checking profile status: {e}")
            return None

