"""
Discord Automation Module
Handles Discord-specific automation tasks using Playwright
"""

import logging
import time
import random
from typing import Optional, Tuple, List

try:
    # Try to import Patchright (undetected Playwright)
    from patchright.sync_api import Page, Browser, Error as PlaywrightError, TimeoutError as PlaywrightTimeout
    USING_PATCHRIGHT = True
except ImportError:
    # Fallback to regular Playwright
    from playwright.sync_api import Page, Browser, Error as PlaywrightError, TimeoutError as PlaywrightTimeout
    USING_PATCHRIGHT = False

from src.stealth import StealthManager

logger = logging.getLogger(__name__)

# Log which library is being used
if USING_PATCHRIGHT:
    logger.info("🎭 Using Patchright (undetected Playwright)")
else:
    logger.warning("⚠️ Using regular Playwright (Patchright not installed)")


class DiscordAutomation:
    """Discord automation handler"""
    
    def __init__(self, page: Page, timeouts: dict):
        """
        Initialize Discord automation
        
        Args:
            page: Playwright page object
            timeouts: Dictionary with timeout values
        """
        self.page = page
        self.timeouts = timeouts
        self.page_load_timeout = timeouts.get('page_load_timeout', 30) * 1000
        self.auth_check_timeout = timeouts.get('auth_check_timeout', 10) * 1000
        self.upload_timeout = timeouts.get('upload_timeout', 15) * 1000
        
        # Set default navigation timeout
        self.page.set_default_navigation_timeout(self.page_load_timeout)
        self.page.set_default_timeout(self.page_load_timeout)
        
        # Initialize stealth manager
        self.stealth = StealthManager(page)
        
        # Apply anti-detection scripts
        try:
            self.stealth.apply_stealth_scripts()
            logger.info("🥷 Stealth mode activated")
        except Exception as e:
            logger.warning(f"Could not activate stealth mode: {e}")
    
    def _wait_for_page_load(self, timeout: int = 10000) -> bool:
        """
        Wait for page to fully load (including network activity)
        
        Args:
            timeout: Timeout in milliseconds
            
        Returns:
            True if page loaded successfully
        """
        try:
            # Wait for document to be ready
            self.page.wait_for_load_state("load", timeout=timeout)
            logger.debug("Page load state: load")
            
            # Wait for DOM content to be loaded
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            logger.debug("Page load state: domcontentloaded")
            
            # Wait for network to be idle (important for Discord's dynamic content)
            try:
                self.page.wait_for_load_state("networkidle", timeout=timeout)
                logger.debug("Page load state: networkidle")
            except PlaywrightTimeout:
                # NetworkIdle might timeout on Discord due to websockets, that's okay
                logger.debug("NetworkIdle timeout (expected for Discord), continuing...")
            
            # Additional wait for JavaScript execution
            time.sleep(1)
            
            return True
            
        except Exception as e:
            logger.warning(f"Error waiting for page load: {e}")
            return False
    
    def _wait_for_element(self, selectors: List[str], timeout: int = 10000, visible: bool = True) -> Optional[str]:
        """
        Wait for one of multiple selectors to appear
        
        Args:
            selectors: List of CSS selectors to try
            timeout: Timeout in milliseconds
            visible: Wait for element to be visible (not just present in DOM)
            
        Returns:
            The selector that was found, or None if none found
        """
        for selector in selectors:
            try:
                logger.debug(f"Waiting for element: {selector}")
                if visible:
                    self.page.wait_for_selector(selector, state="visible", timeout=timeout)
                else:
                    self.page.wait_for_selector(selector, state="attached", timeout=timeout)
                logger.debug(f"Element found: {selector}")
                return selector
            except PlaywrightTimeout:
                logger.debug(f"Element not found: {selector}")
                continue
            except Exception as e:
                logger.debug(f"Error checking element {selector}: {e}")
                continue
        
        return None
    
    def _retry_action(self, action_func, max_retries: int = 3, delay: float = 2.0):
        """
        Retry an action multiple times on failure
        
        Args:
            action_func: Function to execute
            max_retries: Maximum number of retry attempts
            delay: Delay between retries in seconds
            
        Returns:
            Result of action_func
            
        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return action_func()
            except Exception as e:
                last_exception = e
                logger.warning(f"Action failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.debug(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
        
        raise last_exception
    
    def check_authentication(self) -> Tuple[bool, str]:
        """
        Check if Discord account is authenticated
        
        Returns:
            Tuple of (is_authenticated, message)
        """
        try:
            logger.info("Checking Discord authentication status...")
            
            # Simulate human behavior before navigation
            self.stealth.simulate_human_behavior_before_action("navigation")
            
            # Navigate to Discord with multiple wait strategies
            logger.debug("Navigating to Discord...")
            self.page.goto("https://discord.com/channels/@me", 
                          wait_until="load",
                          timeout=self.page_load_timeout)
            
            # Wait for page to fully load
            logger.debug("Waiting for page to fully load...")
            self._wait_for_page_load(timeout=15000)
            
            # Simulate reading/looking at the page
            self.stealth.simulate_reading(min_seconds=1.0, max_seconds=2.5)
            
            # Check current URL
            current_url = self.page.url
            logger.debug(f"Current URL: {current_url}")
            
            # Check if redirected to login page
            if "/login" in current_url or "/register" in current_url:
                logger.warning("Account is not authenticated (redirected to login page)")
                return False, "Account is not authenticated - login required"
            
            # Check for login form elements (might be shown even without redirect)
            login_form_selectors = [
                'form[action="/login"]',
                'input[name="email"]',
                'input[name="password"]',
                'button[type="submit"]:has-text("Log In")',
                'button[type="submit"]:has-text("Войти")'
            ]
            
            login_element = self._wait_for_element(login_form_selectors, timeout=3000, visible=True)
            if login_element:
                logger.warning(f"Account is not authenticated (login form detected: {login_element})")
                return False, "Account is not authenticated - login form detected"
            
            # Wait for and check authenticated elements
            logger.debug("Looking for authenticated indicators...")
            authenticated_indicators = [
                'div[aria-label="Direct Messages"]',
                'nav[aria-label="Servers sidebar"]',
                'button[aria-label="User Settings"]',
                '[data-list-id="guildsnav"]',
                '[class*="sidebar"]',
                '[class*="panels"]',
                'div[class*="guilds"]'
            ]
            
            # Wait for at least one authenticated element to appear
            found_element = self._wait_for_element(authenticated_indicators, timeout=10000, visible=True)
            
            if found_element:
                logger.info(f"Account is authenticated (found element: {found_element})")
                
                # Additional verification - wait a bit more to ensure stability
                time.sleep(1)
                
                return True, "Account is authenticated"
            else:
                logger.warning("Could not confirm authentication - no authenticated indicators found")
                return False, "Could not confirm authentication status"
            
        except PlaywrightTimeout as e:
            logger.error(f"Timeout during authentication check: {e}")
            return False, "Page load timeout - check your internet connection"
        except PlaywrightError as e:
            logger.error(f"Playwright error during authentication check: {e}")
            return False, f"Page load error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during authentication check: {e}")
            return False, f"Unexpected error: {str(e)}"
    
    def navigate_to_channel(self, channel_url: str) -> Tuple[bool, str]:
        """
        Navigate to specific Discord channel
        
        Args:
            channel_url: Full URL to Discord channel
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Navigating to channel: {channel_url}")
            
            # Simulate human behavior before navigation
            self.stealth.simulate_human_behavior_before_action("navigation")
            
            # Navigate to channel with proper waiting
            logger.debug("Loading channel page...")
            self.page.goto(channel_url, 
                          wait_until="load",
                          timeout=self.page_load_timeout)
            
            # Wait for page to fully load
            logger.debug("Waiting for channel page to fully load...")
            self._wait_for_page_load(timeout=15000)
            
            # Simulate reading/observing the channel
            self.stealth.simulate_reading(min_seconds=1.5, max_seconds=3.0)
            
            # Verify URL (allow for Discord's URL variations)
            current_url = self.page.url
            logger.debug(f"Current URL: {current_url}")
            
            # Extract channel and server IDs from URLs for comparison
            try:
                expected_parts = channel_url.split('/')[-2:]  # Get last two parts (server_id, channel_id)
                current_parts = current_url.split('/')[-2:] if '/' in current_url else []
                
                if expected_parts != current_parts:
                    logger.warning(f"URL mismatch. Expected parts: {expected_parts}, Got: {current_parts}")
                    # Don't fail immediately, check if we can still find channel elements
            except:
                pass
            
            # Wait for channel to be ready - look for key elements
            logger.debug("Waiting for channel elements to load...")
            channel_indicators = [
                '[role="textbox"][data-slate-editor="true"]',  # Message input
                'div[class*="chatContent"]',  # Chat content area
                'main[class*="chat"]',  # Main chat area
                'div[aria-label*="Message"]',  # Message area
                '[class*="messagesWrapper"]',  # Messages wrapper
                'form[class*="form"]',  # Message form
                'div[class*="channelTextArea"]'  # Text area
            ]
            
            found_indicator = self._wait_for_element(channel_indicators, timeout=15000, visible=True)
            
            if not found_indicator:
                logger.error("Channel elements not found after waiting")
                return False, "Channel did not load - elements not found"
            
            logger.debug(f"Channel element found: {found_indicator}")
            
            # Verify message input is actually ready for interaction
            try:
                message_input = self.page.locator('[role="textbox"]').first
                
                # Wait for element to be both visible and enabled
                message_input.wait_for(state="visible", timeout=5000)
                
                # Try to focus on it to ensure it's interactive
                message_input.focus(timeout=3000)
                
                logger.info("Successfully navigated to channel - all elements loaded")
                
                # Final wait for stability
                time.sleep(1)
                
                return True, "Channel loaded successfully"
                
            except PlaywrightTimeout:
                logger.warning("Message input not ready for interaction")
                # Still return success if we found other channel indicators
                if found_indicator:
                    logger.info("Channel loaded (message input not interactive yet)")
                    return True, "Channel loaded (limited functionality)"
                return False, "Channel did not load properly"
            except Exception as e:
                logger.warning(f"Error verifying message input: {e}")
                # Still return success if we found other channel indicators
                if found_indicator:
                    return True, "Channel loaded successfully"
                return False, f"Channel verification error: {str(e)}"
            
        except PlaywrightTimeout as e:
            logger.error(f"Timeout during channel navigation: {e}")
            return False, "Navigation timeout - channel took too long to load"
        except PlaywrightError as e:
            logger.error(f"Playwright error during channel navigation: {e}")
            return False, f"Navigation error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during channel navigation: {e}")
            return False, f"Unexpected error: {str(e)}"
    
    def upload_and_send_image(self, image_path: str) -> Tuple[bool, str]:
        """
        Upload and send an image in the current Discord channel
        
        Args:
            image_path: Full path to the image file
            
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Uploading image: {image_path}")
            
            # Simulate human behavior before upload
            self.stealth.simulate_human_behavior_before_action("upload")
            
            # Step 1: Find and wait for file upload input
            logger.debug("Looking for file upload input...")
            file_input_selectors = [
                'input[type="file"]',
                'input[type="file"][multiple]',
                'form input[type="file"]'
            ]
            
            # Wait for file input to be present
            file_input_selector = self._wait_for_element(file_input_selectors, timeout=10000, visible=False)
            
            if not file_input_selector:
                logger.error("Could not find file upload input")
                return False, "File upload input not found"
            
            file_input = self.page.locator(file_input_selector).first
            logger.debug(f"File input found: {file_input_selector}")
            
            # Human-like pause before upload
            self.stealth.random_delay(0.5, 1.5)
            
            # Step 2: Upload the file with retry logic
            def upload_file():
                logger.debug("Setting file to upload...")
                file_input.set_input_files(image_path, timeout=10000)
                logger.debug("File set successfully")
            
            try:
                self._retry_action(upload_file, max_retries=3, delay=1.0)
            except Exception as e:
                logger.error(f"Failed to set file after retries: {e}")
                return False, f"Failed to upload file: {str(e)}"
            
            # Step 3: Wait for upload modal/preview to appear
            logger.debug("Waiting for upload preview to load...")
            
            # Simulate observing the upload preview
            self.stealth.random_delay(2.0, 3.5)
            
            # Wait for upload to be processed
            upload_indicators = [
                'div[class*="uploadModal"]',
                'div[class*="uploadArea"]',
                'div[role="dialog"]',  # Upload modal
                'img[class*="imageWrapper"]',  # Image preview
                'div[class*="imageWrapper"]'
            ]
            
            upload_ready = self._wait_for_element(upload_indicators, timeout=10000, visible=True)
            if upload_ready:
                logger.debug(f"Upload preview loaded: {upload_ready}")
                # Give it time to fully render
                time.sleep(1.5)
            else:
                logger.warning("Upload preview not detected, continuing anyway...")
            
            # Step 4: Find and click send button with multiple strategies
            logger.debug("Looking for send button...")
            
            # Simulate thinking/reviewing before sending
            self.stealth.random_delay(1.0, 2.5)
            
            # Multiple send button selectors for different Discord versions and languages
            send_button_selectors = [
                'button[type="submit"]',  # Generic submit button
                'button[type="button"]:has-text("Send")',
                'button:has-text("Send")',
                'button:has-text("Отправить")',  # Russian
                'button:has-text("Enviar")',  # Spanish/Portuguese
                'button:has-text("Envoyer")',  # French
                'button[aria-label*="Send"]',
                'button[class*="sendButton"]',
                'div[class*="attachButton"] + button',  # Button next to attach
                'form button[type="submit"]'
            ]
            
            button_clicked = False
            
            # Try to find and click send button
            for selector in send_button_selectors:
                try:
                    send_button = self.page.locator(selector).first
                    
                    # Check if button exists and is visible
                    if send_button.count() > 0:
                        # Wait for button to be ready
                        send_button.wait_for(state="visible", timeout=5000)
                        
                        # Scroll button into view if needed
                        send_button.scroll_into_view_if_needed(timeout=2000)
                        
                        # Ensure button is enabled
                        if not send_button.is_disabled():
                            logger.debug(f"Clicking send button: {selector}")
                            
                            # Use human-like click with mouse movement
                            self.stealth.human_like_click(send_button, move_mouse=True)
                            
                            button_clicked = True
                            logger.debug("Send button clicked successfully")
                            break
                        else:
                            logger.debug(f"Button found but disabled: {selector}")
                except PlaywrightTimeout:
                    logger.debug(f"Timeout waiting for button: {selector}")
                    continue
                except Exception as e:
                    logger.debug(f"Error with button selector {selector}: {e}")
                    continue
            
            # Fallback: Press Enter key
            if not button_clicked:
                logger.debug("Send button not found, trying Enter key as fallback...")
                
                # Human-like delay before fallback
                self.stealth.random_delay(0.3, 0.8)
                
                try:
                    # Try to focus on message input first
                    message_input = self.page.locator('[role="textbox"]').first
                    if message_input.count() > 0:
                        message_input.focus(timeout=2000)
                        self.stealth.random_delay(0.2, 0.5)
                        self.page.keyboard.press("Enter")
                        logger.debug("Pressed Enter on message input")
                    else:
                        # Global Enter press
                        self.page.keyboard.press("Enter")
                        logger.debug("Pressed Enter globally")
                except Exception as e:
                    logger.warning(f"Error pressing Enter: {e}")
                    # Last resort
                    self.page.keyboard.press("Enter")
            
            # Step 5: Wait for message to be sent
            logger.debug("Waiting for message to be sent...")
            
            # Simulate waiting to see message appear
            self.stealth.random_delay(2.5, 4.0)
            
            # Optional: Verify message was sent by checking for upload modal to disappear
            try:
                # If modal is still visible after delay, it might indicate an error
                modal_selectors = ['div[role="dialog"]', 'div[class*="uploadModal"]']
                
                for modal_selector in modal_selectors:
                    modal = self.page.locator(modal_selector).first
                    if modal.count() > 0:
                        try:
                            # Wait for modal to disappear (indicates successful send)
                            modal.wait_for(state="hidden", timeout=5000)
                            logger.debug("Upload modal closed - message sent")
                        except PlaywrightTimeout:
                            logger.warning("Upload modal still visible - message may not have sent")
                            # Don't fail, just warn
                            pass
            except Exception as e:
                logger.debug(f"Could not verify modal state: {e}")
            
            # Final wait for stability
            time.sleep(1)
            
            logger.info("✅ Image uploaded and sent successfully")
            return True, "Image sent successfully"
            
        except PlaywrightTimeout as e:
            logger.error(f"Timeout during image upload: {e}")
            return False, "Upload timeout - operation took too long"
        except PlaywrightError as e:
            logger.error(f"Playwright error during image upload: {e}")
            return False, f"Upload error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during image upload: {e}", exc_info=True)
            return False, f"Unexpected error: {str(e)}"
    
    def close(self):
        """Close the page"""
        try:
            if self.page and not self.page.is_closed():
                self.page.close()
        except Exception as e:
            logger.debug(f"Error closing page: {e}")

