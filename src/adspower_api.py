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
                    logger.debug(f"Full response: {data}")
                    return False, None
                    
                ws_dict = result.get("ws", {})
                ws_endpoint = ws_dict.get("playwright") if ws_dict else None
                debug_port = result.get("debug_port")
                
                if not ws_endpoint:
                    logger.debug(f"No 'playwright' WebSocket endpoint, trying alternatives...")
                    logger.debug(f"Response data: {result}")
                    logger.debug(f"WS dict: {ws_dict}")
                    
                    # Check for alternative WebSocket endpoints
                    if ws_dict:
                        # Try selenium or webdriver endpoints as fallback
                        ws_endpoint = (ws_dict.get("selenium") or 
                                     ws_dict.get("puppeteer") or
                                     ws_dict.get("webdriver"))
                        
                        if ws_endpoint:
                            logger.info(f"Using WebSocket endpoint: {ws_endpoint}")
                        else:
                            logger.error(f"No valid WebSocket endpoint found. Available keys: {list(ws_dict.keys())}")
                            return False, None
                    else:
                        logger.error(f"No WebSocket endpoints available in API response")
                        return False, None
                
                # Ensure WebSocket endpoint has correct format
                ws_endpoint = self._format_ws_endpoint(ws_endpoint, debug_port)
                
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
    
    def _format_ws_endpoint(self, endpoint: str, debug_port: Optional[int] = None) -> str:
        """
        Format WebSocket endpoint to correct URL format for Playwright/Patchright
        
        Args:
            endpoint: Raw endpoint from AdsPower API (may be just host:port or full URL)
            debug_port: Debug port from API response
            
        Returns:
            Properly formatted WebSocket URL
        """
        if not endpoint:
            return endpoint
            
        # If already has protocol, return as-is
        if endpoint.startswith(('ws://', 'wss://', 'http://', 'https://')):
            logger.debug(f"Endpoint already formatted: {endpoint}")
            return endpoint
        
        # Format: "host:port" -> need to construct proper CDP URL
        # Try to get debug port URL for CDP connection
        try:
            # Parse host and port from endpoint
            if ':' in endpoint:
                host, port = endpoint.rsplit(':', 1)
                port = int(port)
            else:
                host = endpoint
                port = debug_port or 9222  # Default Chrome DevTools port
            
            # First try to get browser WebSocket URL from /json/version endpoint
            cdp_url = f"http://{host}:{port}"
            logger.debug(f"Trying to get WebSocket URL from CDP: {cdp_url}")
            
            try:
                response = self.session.get(f"{cdp_url}/json/version", timeout=5)
                if response.status_code == 200:
                    version_data = response.json()
                    ws_url = version_data.get("webSocketDebuggerUrl")
                    if ws_url:
                        logger.info(f"Got WebSocket URL from CDP: {ws_url}")
                        return ws_url
            except Exception as e:
                logger.debug(f"Could not get WebSocket URL from /json/version: {e}")
            
            # Fallback: construct WebSocket URL directly
            # For CDP, we use http:// URL and let Playwright handle the conversion
            formatted = f"http://{host}:{port}"
            logger.info(f"Using HTTP endpoint for CDP: {formatted}")
            return formatted
            
        except Exception as e:
            logger.warning(f"Error formatting endpoint '{endpoint}': {e}")
            # Return original if formatting fails
            return endpoint
