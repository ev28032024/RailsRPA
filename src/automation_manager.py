"""
Automation Manager Module
Orchestrates the entire automation workflow with multi-threading support
"""

import logging
import time
import threading
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    # Try to import Patchright (undetected Playwright)
    from patchright.sync_api import sync_playwright, Browser, BrowserContext, Page
except ImportError:
    # Fallback to regular Playwright
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from src.adspower_api import AdsPowerAPI
from src.config_manager import ConfigManager
from src.discord_automation import DiscordAutomation

logger = logging.getLogger(__name__)


class AutomationManager:
    """Main automation orchestrator with multi-threading support"""
    
    def __init__(self, config: ConfigManager):
        """
        Initialize automation manager
        
        Args:
            config: Configuration manager instance
        """
        self.config = config
        self.adspower = AdsPowerAPI(config.get_adspower_host())
        
        # Thread-safe statistics
        self._stats_lock = threading.Lock()
        self.stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'not_authenticated': 0,
            'channel_unavailable': 0
        }
        
        # Multi-threading settings
        self.max_workers = config.settings.get('max_workers', 1)
        self.use_threading = self.max_workers > 1
        
        if self.use_threading:
            logger.info(f"🧵 Multi-threading enabled: {self.max_workers} workers")
        else:
            logger.info("Sequential mode (single-threaded)")
    
    def _update_stats(self, key: str, value: int = 1):
        """Thread-safe statistics update"""
        with self._stats_lock:
            self.stats[key] += value
    
    def run(self):
        """Run the automation for all enabled profiles"""
        profiles = self.config.get_enabled_profiles()
        total_profiles = len(profiles)
        
        logger.info(f"Starting automation for {total_profiles} profiles")
        print(f"\n{'='*60}")
        print(f"Total profiles to process: {total_profiles}")
        if self.use_threading:
            print(f"Mode: Multi-threaded ({self.max_workers} workers)")
        else:
            print(f"Mode: Sequential (single-threaded)")
        print(f"{'='*60}\n")
        
        if self.use_threading:
            self._run_threaded(profiles)
        else:
            self._run_sequential(profiles)
        
        # Print final statistics
        self._print_statistics()
    
    def _run_sequential(self, profiles: List[Dict]):
        """Run profiles sequentially (original behavior)"""
        total_profiles = len(profiles)
        
        for idx, profile in enumerate(profiles, 1):
            profile_id = profile['profile_id']
            image_name = profile['image_name']
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing profile {idx}/{total_profiles}: {profile_id}")
            logger.info(f"{'='*60}")
            
            self._update_stats('total')
            
            # Process the profile
            result = self._process_profile(profile_id, image_name, idx, total_profiles)
            
            self._handle_result(profile_id, result)
            
            # Delay between profiles
            if idx < total_profiles:
                delay = self.config.get_timeout('between_profiles_delay', 2)
                if delay > 0:
                    logger.info(f"Waiting {delay} seconds before next profile...")
                    time.sleep(delay)
    
    def _run_threaded(self, profiles: List[Dict]):
        """Run profiles in parallel using ThreadPoolExecutor"""
        total_profiles = len(profiles)
        
        # Create profile tasks with index
        tasks = [(profile, idx, total_profiles) for idx, profile in enumerate(profiles, 1)]
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_profile = {
                executor.submit(
                    self._process_profile_wrapper, 
                    task[0]['profile_id'], 
                    task[0]['image_name'],
                    task[1],
                    task[2]
                ): task[0] 
                for task in tasks
            }
            
            # Process completed tasks
            for future in as_completed(future_to_profile):
                profile = future_to_profile[future]
                profile_id = profile['profile_id']
                
                try:
                    result = future.result()
                    self._handle_result(profile_id, result)
                except Exception as e:
                    logger.error(f"Thread error for profile {profile_id}: {e}")
                    self._update_stats('failed')
                    self._notify_user(profile_id, "FAILED", f"Thread error: {str(e)}")
    
    def _process_profile_wrapper(self, profile_id: str, image_name: str, idx: int, total: int) -> Dict:
        """Wrapper for thread execution"""
        self._update_stats('total')
        
        logger.info(f"\n{'='*60}")
        logger.info(f"[Thread] Processing profile {idx}/{total}: {profile_id}")
        logger.info(f"{'='*60}")
        
        return self._process_profile(profile_id, image_name, idx, total)
    
    def _handle_result(self, profile_id: str, result: Dict):
        """Handle processing result and update statistics"""
        status = result.get('status', 'FAILED')
        message = result.get('message', 'Unknown error')
        
        if status == 'SUCCESS':
            self._update_stats('successful')
        elif status == 'NOT_AUTHENTICATED':
            self._update_stats('not_authenticated')
            self._update_stats('failed')
        elif status == 'CHANNEL_UNAVAILABLE':
            self._update_stats('channel_unavailable')
            self._update_stats('failed')
        else:
            self._update_stats('failed')
        
        self._notify_user(profile_id, status, message)
    
    def _process_profile(self, profile_id: str, image_name: str, idx: int = 0, total: int = 0) -> Dict:
        """
        Process a single profile
        
        Args:
            profile_id: AdsPower profile ID
            image_name: Image filename to send
            idx: Current profile index
            total: Total profiles count
            
        Returns:
            Dict with 'status' and 'message' keys
        """
        browser = None
        
        try:
            # Get image path
            image_path = self.config.get_image_path(image_name)
            if not image_path:
                logger.error(f"❌ Image not found: {image_name}")
                return {'status': 'FAILED', 'message': f"Image not found: {image_name}"}
            
            logger.info(f"Image found: {image_path}")
            
            # Start AdsPower profile
            logger.info("Starting AdsPower profile...")
            success, connection_info = self.adspower.start_profile(profile_id)
            
            if not success or not connection_info:
                logger.error(f"❌ Failed to start AdsPower profile")
                return {'status': 'FAILED', 'message': "Could not start AdsPower profile"}
            
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
                        return {'status': 'FAILED', 'message': "No browser contexts found"}
                    
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
                        return {'status': 'NOT_AUTHENTICATED', 'message': auth_message}
                    
                    logger.info(f"✓ {auth_message}")
                    
                    # Step 2: Navigate to channel
                    logger.info("Step 2: Navigating to Discord channel...")
                    channel_url = self.config.get_discord_url()
                    nav_success, nav_message = discord.navigate_to_channel(channel_url)
                    
                    if not nav_success:
                        logger.error(f"❌ {nav_message}")
                        # Check if it's a channel access issue
                        if "access" in nav_message.lower() or "unavailable" in nav_message.lower():
                            return {'status': 'CHANNEL_UNAVAILABLE', 'message': nav_message}
                        return {'status': 'FAILED', 'message': nav_message}
                    
                    logger.info(f"✓ {nav_message}")
                    
                    # Step 3: Upload and send image
                    logger.info("Step 3: Uploading and sending image...")
                    upload_success, upload_message = discord.upload_and_send_image(image_path)
                    
                    if not upload_success:
                        logger.error(f"❌ {upload_message}")
                        return {'status': 'FAILED', 'message': upload_message}
                    
                    logger.info(f"✓ {upload_message}")
                    
                    # Success!
                    logger.info("✅ Profile processed successfully!")
                    return {'status': 'SUCCESS', 'message': "Image sent successfully"}
                    
                except Exception as e:
                    logger.error(f"Browser automation error: {e}", exc_info=True)
                    return {'status': 'FAILED', 'message': f"Automation error: {str(e)}"}
                finally:
                    # Disconnect from browser but don't close it
                    if browser:
                        try:
                            browser.close()
                        except:
                            pass
            
        except Exception as e:
            logger.error(f"Unexpected error processing profile: {e}", exc_info=True)
            return {'status': 'FAILED', 'message': f"Unexpected error: {str(e)}"}
        
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
            status: Status (SUCCESS, FAILED, NOT_AUTHENTICATED, etc.)
            message: Status message
        """
        status_colors = {
            'SUCCESS': '\033[92m',           # Green
            'FAILED': '\033[91m',            # Red
            'NOT_AUTHENTICATED': '\033[93m', # Yellow
            'CHANNEL_UNAVAILABLE': '\033[95m', # Magenta
            'SKIPPED': '\033[94m'            # Blue
        }
        
        color = status_colors.get(status, '\033[0m')
        reset = '\033[0m'
        
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
        print(f"🚫 Channel unavailable:     {self.stats['channel_unavailable']}")
        print(f"{'='*60}\n")
        
        success_rate = 0
        if self.stats['total'] > 0:
            success_rate = (self.stats['successful'] / self.stats['total']) * 100
        
        print(f"Success rate: {success_rate:.1f}%\n")
