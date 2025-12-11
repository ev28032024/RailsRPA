"""
Automation Manager Module
Orchestrates the entire automation workflow
"""

import logging
import time
from typing import Dict, List

try:
    # Try to import Patchright (undetected Playwright)
    from patchright.sync_api import sync_playwright, Browser, BrowserContext, Page
    logger = logging.getLogger(__name__)
    logger.info("🎭 Patchright loaded successfully")
except ImportError:
    # Fallback to regular Playwright
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ Patchright not found, using regular Playwright")

from src.adspower_api import AdsPowerAPI
from src.config_manager import ConfigManager
from src.discord_automation import DiscordAutomation


class AutomationManager:
    """Main automation orchestrator"""
    
    def __init__(self, config: ConfigManager):
        """
        Initialize automation manager
        
        Args:
            config: Configuration manager instance
        """
        self.config = config
        self.adspower = AdsPowerAPI(config.get_adspower_host())
        self.stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'not_authenticated': 0
        }
    
    def run(self):
        """Run the automation for all enabled profiles"""
        profiles = self.config.get_enabled_profiles()
        total_profiles = len(profiles)
        
        logger.info(f"Starting automation for {total_profiles} profiles")
        print(f"\n{'='*60}")
        print(f"Total profiles to process: {total_profiles}")
        print(f"{'='*60}\n")
        
        for idx, profile in enumerate(profiles, 1):
            profile_id = profile['profile_id']
            image_name = profile['image_name']
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing profile {idx}/{total_profiles}: {profile_id}")
            logger.info(f"{'='*60}")
            
            self.stats['total'] += 1
            
            # Process the profile
            success = self._process_profile(profile_id, image_name)
            
            if success:
                self.stats['successful'] += 1
            else:
                self.stats['failed'] += 1
            
            # Delay between profiles
            if idx < total_profiles:
                delay = self.config.get_timeout('between_profiles_delay', 2)
                if delay > 0:
                    logger.info(f"Waiting {delay} seconds before next profile...")
                    time.sleep(delay)
        
        # Print final statistics
        self._print_statistics()
    
    def _process_profile(self, profile_id: str, image_name: str) -> bool:
        """
        Process a single profile
        
        Args:
            profile_id: AdsPower profile ID
            image_name: Image filename to send
            
        Returns:
            True if successful, False otherwise
        """
        browser = None
        context = None
        
        try:
            # Get image path
            image_path = self.config.get_image_path(image_name)
            if not image_path:
                logger.error(f"❌ Image not found: {image_name}")
                self._notify_user(profile_id, "FAILED", f"Image not found: {image_name}")
                return False
            
            logger.info(f"Image found: {image_path}")
            
            # Start AdsPower profile
            logger.info("Starting AdsPower profile...")
            success, connection_info = self.adspower.start_profile(profile_id)
            
            if not success or not connection_info:
                logger.error(f"❌ Failed to start AdsPower profile")
                self._notify_user(profile_id, "FAILED", "Could not start AdsPower profile")
                return False
            
            ws_endpoint = connection_info['ws_endpoint']
            logger.info(f"Profile started successfully")
            logger.debug(f"WebSocket endpoint: {ws_endpoint}")
            
            # Connect to browser via Playwright
            with sync_playwright() as p:
                try:
                    logger.info("Connecting to browser...")
                    browser = p.chromium.connect_over_cdp(ws_endpoint)
                    
                    # Get the default context and page
                    contexts = browser.contexts
                    if not contexts:
                        logger.error("No browser contexts found")
                        return False
                    
                    context = contexts[0]
                    pages = context.pages
                    
                    # Use existing page or create new one
                    if pages:
                        page = pages[0]
                    else:
                        page = context.new_page()
                    
                    logger.info("Connected to browser successfully")
                    
                    # Create Discord automation instance
                    timeouts = {
                        'page_load_timeout': self.config.get_timeout('page_load_timeout', 30),
                        'auth_check_timeout': self.config.get_timeout('auth_check_timeout', 10),
                        'upload_timeout': self.config.get_timeout('upload_timeout', 15)
                    }
                    
                    discord = DiscordAutomation(page, timeouts)
                    
                    # Step 1: Check authentication
                    logger.info("Step 1: Checking Discord authentication...")
                    is_authenticated, auth_message = discord.check_authentication()
                    
                    if not is_authenticated:
                        logger.warning(f"❌ {auth_message}")
                        self._notify_user(profile_id, "NOT AUTHENTICATED", auth_message)
                        self.stats['not_authenticated'] += 1
                        return False
                    
                    logger.info(f"✓ {auth_message}")
                    
                    # Step 2: Navigate to channel
                    logger.info("Step 2: Navigating to Discord channel...")
                    channel_url = self.config.get_discord_url()
                    nav_success, nav_message = discord.navigate_to_channel(channel_url)
                    
                    if not nav_success:
                        logger.error(f"❌ {nav_message}")
                        self._notify_user(profile_id, "FAILED", nav_message)
                        return False
                    
                    logger.info(f"✓ {nav_message}")
                    
                    # Step 3: Upload and send image
                    logger.info("Step 3: Uploading and sending image...")
                    upload_success, upload_message = discord.upload_and_send_image(image_path)
                    
                    if not upload_success:
                        logger.error(f"❌ {upload_message}")
                        self._notify_user(profile_id, "FAILED", upload_message)
                        return False
                    
                    logger.info(f"✓ {upload_message}")
                    
                    # Success!
                    logger.info("✅ Profile processed successfully!")
                    self._notify_user(profile_id, "SUCCESS", "Image sent successfully")
                    
                    return True
                    
                except Exception as e:
                    logger.error(f"Browser automation error: {e}", exc_info=True)
                    self._notify_user(profile_id, "FAILED", f"Automation error: {str(e)}")
                    return False
                finally:
                    # Disconnect from browser but don't close it
                    if browser:
                        try:
                            browser.close()
                        except:
                            pass
            
        except Exception as e:
            logger.error(f"Unexpected error processing profile: {e}", exc_info=True)
            self._notify_user(profile_id, "FAILED", f"Unexpected error: {str(e)}")
            return False
        
        finally:
            # Close AdsPower profile
            try:
                logger.info("Closing AdsPower profile...")
                if profile_id:
                    self.adspower.close_profile(profile_id)
                    time.sleep(1)
            except Exception as e:
                logger.warning(f"Error closing AdsPower profile: {e}")
    
    def _notify_user(self, profile_id: str, status: str, message: str):
        """
        Notify user about profile status
        
        Args:
            profile_id: Profile ID
            status: Status (SUCCESS, FAILED, NOT AUTHENTICATED, etc.)
            message: Status message
        """
        status_colors = {
            'SUCCESS': '\033[92m',      # Green
            'FAILED': '\033[91m',        # Red
            'NOT AUTHENTICATED': '\033[93m',  # Yellow
            'SKIPPED': '\033[94m'        # Blue
        }
        
        color = status_colors.get(status, '\033[0m')
        reset = '\033[0m'
        
        # Fixed: Use parentheses for correct operation order
        indent = ' ' * (len(status) + 3)
        notification = f"\n{color}[{status}]{reset} Profile: {profile_id}\n{indent}Message: {message}\n"
        print(notification)
    
    def _print_statistics(self):
        """Print final statistics"""
        logger.info("\n" + "="*60)
        logger.info("AUTOMATION COMPLETED")
        logger.info("="*60)
        
        print(f"\n{'='*60}")
        print(f"{'FINAL STATISTICS':^60}")
        print(f"{'='*60}")
        print(f"Total profiles processed:  {self.stats['total']}")
        print(f"✅ Successful:              {self.stats['successful']}")
        print(f"❌ Failed:                  {self.stats['failed']}")
        print(f"⚠️  Not authenticated:      {self.stats['not_authenticated']}")
        print(f"{'='*60}\n")
        
        success_rate = 0
        if self.stats['total'] > 0:
            success_rate = (self.stats['successful'] / self.stats['total']) * 100
        
        print(f"Success rate: {success_rate:.1f}%\n")
