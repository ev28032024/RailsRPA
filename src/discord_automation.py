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
        
        # Store current username for message verification
        self.current_username = ""
        
        # Initialize stealth manager
        self.stealth = StealthManager(page)
        
        # Apply anti-detection scripts
        try:
            self.stealth.apply_stealth_scripts()
            logger.info("🥷 Stealth mode activated")
        except Exception as e:
            logger.warning(f"Could not activate stealth mode: {e}")
    
    def get_discord_username(self) -> Tuple[bool, str]:
        """
        Get the current Discord username from the page
        
        Returns:
            Tuple of (success, username_or_error)
        """
        try:
            # Multiple selectors for username detection
            username_selectors = [
                # User panel at bottom left
                'div[class*="panelTitle"] > span',
                'section[aria-label*="User area"] div[class*="nameTag"]',
                'div[class*="container"] div[class*="usernameContainer"] div[class*="username"]',
                # User settings area
                'div[class*="userInfo"] span[class*="username"]',
                # Username in panel
                '[class*="panels"] [class*="nameTag"]',
                '[class*="avatarWrapper"] + div span',
                # More specific selectors
                'section[class*="panels"] div[class*="nameTag"] div:first-child',
                'div[aria-label="User area"] span[class*="username"]'
            ]
            
            logger.debug("Attempting to get Discord username...")
            
            for selector in username_selectors:
                try:
                    element = self.page.locator(selector).first
                    if element.count() > 0:
                        # Wait a bit for element to be stable
                        element.wait_for(state="visible", timeout=3000)
                        username = element.text_content(timeout=2000)
                        
                        if username and username.strip():
                            username = username.strip()
                            # Clean username (remove discriminator if present)
                            if '#' in username:
                                username = username.split('#')[0]
                            logger.info(f"Found Discord username: {username}")
                            return True, username
                except:
                    continue
            
            # Alternative: Try to get username from user settings
            try:
                # Click on user settings to reveal username
                user_area = self.page.locator('section[aria-label*="User area"], [class*="panels"]').first
                if user_area.count() > 0:
                    # Try to read any text that looks like a username
                    text = user_area.text_content(timeout=3000)
                    if text:
                        # Parse potential username from text
                        lines = [l.strip() for l in text.split('\n') if l.strip()]
                        if lines:
                            potential_username = lines[0]
                            # Validate it looks like a username
                            if len(potential_username) >= 2 and len(potential_username) <= 32:
                                logger.info(f"Found potential Discord username: {potential_username}")
                                return True, potential_username
            except:
                pass
            
            logger.warning("Could not find Discord username")
            return False, "Username not found"
            
        except Exception as e:
            logger.error(f"Error getting Discord username: {e}")
            return False, f"Error: {str(e)}"
    
    def verify_username(self, expected_username: str) -> Tuple[bool, str, str]:
        """
        Verify that the logged-in account matches expected username
        
        Discord may show combined text like "DisplayNameusernameOnline"
        So we check if expected username is CONTAINED in the detected text
        
        Args:
            expected_username: Expected Discord username from config
            
        Returns:
            Tuple of (match, actual_username, message)
        """
        try:
            if not expected_username or expected_username.strip() == "":
                logger.debug("No expected username provided, skipping verification")
                return True, "", "Username verification skipped (no expected username)"
            
            success, actual_username = self.get_discord_username()
            
            if not success:
                logger.warning(f"Could not get current username for verification")
                # Don't fail on this - just warn
                return True, "", "Username verification skipped (could not detect username)"
            
            # Normalize both usernames for comparison
            expected_clean = expected_username.lower().strip()
            actual_clean = actual_username.lower().strip()
            
            # Remove potential discriminator
            if '#' in expected_clean:
                expected_clean = expected_clean.split('#')[0]
            if '#' in actual_clean:
                actual_clean = actual_clean.split('#')[0]
            
            # Check for match using multiple strategies:
            # 1. Exact match
            # 2. Expected username is contained in actual (Discord may show "DisplayNameusernameStatus")
            # 3. Actual is contained in expected (for partial detection)
            
            is_match = (
                expected_clean == actual_clean or           # Exact match
                expected_clean in actual_clean or           # Expected contained in actual
                actual_clean in expected_clean              # Actual contained in expected
            )
            
            if is_match:
                logger.info(f"✅ Username verified: '{expected_username}' found in '{actual_username}'")
                return True, actual_username, f"Username verified: {expected_username}"
            else:
                logger.warning(f"❌ Username mismatch! Expected: {expected_username}, Got: {actual_username}")
                return False, actual_username, f"Username mismatch: expected '{expected_username}', got '{actual_username}'"
                
        except Exception as e:
            logger.error(f"Error verifying username: {e}")
            # Don't fail the whole process on verification error
            return True, "", f"Username verification error: {str(e)}"
    
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
    
    def _check_channel_access(self) -> Tuple[bool, str]:
        """
        Check if the channel is accessible (no access errors)
        
        Returns:
            Tuple of (is_accessible, error_message)
        """
        try:
            # Error indicators that Discord shows for inaccessible channels
            error_selectors = [
                # No access to channel
                'div:has-text("You don\'t have access")',
                'div:has-text("У вас нет доступа")',
                'div:has-text("No tienes acceso")',
                
                # Channel not found / doesn't exist
                'div:has-text("This channel doesn\'t exist")',
                'div:has-text("Этот канал не существует")',
                
                # Server errors
                'div:has-text("This server is unavailable")',
                'div:has-text("Сервер недоступен")',
                
                # Banned from server
                'div:has-text("You\'ve been banned")',
                'div:has-text("Вы были забанены")',
                
                # No permission to view
                'div:has-text("You do not have permission")',
                'div:has-text("У вас нет прав")',
                'div:has-text("Missing Access")',
                
                # Generic error page elements
                'div[class*="errorPage"]',
                'div[class*="notFound"]',
                'div[class*="noAccess"]',
                'h1:has-text("404")',
                'div:has-text("NOT FOUND")'
            ]
            
            # Quick check for error elements
            for selector in error_selectors:
                try:
                    error_element = self.page.locator(selector).first
                    if error_element.count() > 0 and error_element.is_visible(timeout=1000):
                        # Get the error text
                        try:
                            error_text = error_element.text_content(timeout=2000)
                            logger.warning(f"Channel access error detected: {error_text[:100]}")
                            return False, f"Channel unavailable: {error_text[:100]}"
                        except:
                            return False, "Channel is not accessible on this profile"
                except:
                    continue
            
            # Check if we're on a valid channel page by looking at URL
            current_url = self.page.url
            
            # If redirected to DMs (home) - server/channel not accessible
            if current_url.endswith('/channels/@me') or current_url.endswith('/channels/@me/'):
                logger.warning("Redirected to DMs - channel not accessible")
                return False, "Channel not accessible - redirected to DMs"
            
            # Check for invite-only or restricted channel modal
            restricted_selectors = [
                'div[class*="modal"]:has-text("This channel is restricted")',
                'div[class*="modal"]:has-text("NSFW")',
                'div[class*="modal"]:has-text("age-restricted")',
                'button:has-text("I understand")',  # Age verification
                'button:has-text("Я понимаю")'
            ]
            
            for selector in restricted_selectors:
                try:
                    modal = self.page.locator(selector).first
                    if modal.count() > 0 and modal.is_visible(timeout=1000):
                        logger.warning("Restricted channel modal detected")
                        # Try to click through if it's an age gate
                        try:
                            confirm_btn = self.page.locator('button:has-text("I understand"), button:has-text("Continue")').first
                            if confirm_btn.is_visible(timeout=1000):
                                confirm_btn.click()
                                time.sleep(1)
                                logger.info("Clicked through age restriction modal")
                        except:
                            pass
                except:
                    continue
            
            # No errors found - channel is accessible
            return True, "Channel is accessible"
            
        except Exception as e:
            logger.debug(f"Error checking channel access: {e}")
            # If we can't check, assume it's accessible and let other checks handle it
            return True, "Access check completed"
    
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
                
                # Try to get and store current username for later verification
                try:
                    success, username = self.get_discord_username()
                    if success and username:
                        self.current_username = username
                        logger.debug(f"Stored current username: {self.current_username}")
                except Exception as e:
                    logger.debug(f"Could not get username during auth check: {e}")
                
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
            
            # Check for channel access errors FIRST
            logger.debug("Checking for channel access errors...")
            channel_accessible, access_message = self._check_channel_access()
            
            if not channel_accessible:
                logger.error(f"Channel access error: {access_message}")
                return False, access_message
            
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
                # Double-check for access errors
                channel_accessible, access_message = self._check_channel_access()
                if not channel_accessible:
                    return False, access_message
                    
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
            logger.info("Looking for send button...")
            
            # Simulate thinking/reviewing before sending
            self.stealth.random_delay(0.5, 1.5)
            
            # Multiple send button selectors for different Discord versions and languages
            # Ordered by likelihood (most common first)
            send_button_selectors = [
                'button[type="submit"]',  # Generic submit button (most common)
                'button:has-text("Upload")',  # Upload button in modal
                'button:has-text("Send")',
                'button:has-text("Отправить")',  # Russian
                'button[aria-label*="Send"]',
                'form button[type="submit"]'
            ]
            
            button_clicked = False
            
            # Try to find and click send button (with short timeouts)
            for selector in send_button_selectors:
                try:
                    send_button = self.page.locator(selector).first
                    
                    # Quick check if button exists (short timeout)
                    if send_button.count() > 0:
                        try:
                            # Wait for button to be ready (short timeout)
                            send_button.wait_for(state="visible", timeout=2000)
                            
                            # Ensure button is enabled
                            if not send_button.is_disabled():
                                logger.info(f"Found send button: {selector}")
                                
                                # Use human-like click with mouse movement
                                self.stealth.human_like_click(send_button, move_mouse=True)
                                
                                button_clicked = True
                                logger.info("Send button clicked successfully")
                                break
                            else:
                                logger.debug(f"Button found but disabled: {selector}")
                        except PlaywrightTimeout:
                            logger.debug(f"Button not visible: {selector}")
                            continue
                except PlaywrightTimeout:
                    continue
                except Exception as e:
                    logger.debug(f"Error with button selector {selector}: {e}")
                    continue
            
            # Fallback: Press Enter key
            if not button_clicked:
                logger.info("Send button not found, trying Enter key...")
                
                try:
                    # Try to focus on message input first
                    message_input = self.page.locator('[role="textbox"]').first
                    if message_input.count() > 0:
                        message_input.focus(timeout=1000)
                        time.sleep(0.3)
                        self.page.keyboard.press("Enter")
                        logger.info("Pressed Enter on message input")
                    else:
                        # Global Enter press
                        self.page.keyboard.press("Enter")
                        logger.info("Pressed Enter globally")
                except Exception as e:
                    logger.warning(f"Error pressing Enter: {e}")
                    # Last resort
                    self.page.keyboard.press("Enter")
                    logger.info("Pressed Enter (fallback)")
            
            # Step 5: Verify message was sent successfully
            logger.info("Waiting for message to appear...")
            
            # Wait for Discord to process and message to appear
            time.sleep(3.0)
            
            # FIRST: Try to find our message in chat (most reliable check)
            # If message is there = SUCCESS, regardless of any slowmode warning
            logger.info("Looking for our message in chat...")
            
            message_verified, verify_message = self._verify_message_sent()
            
            if message_verified:
                logger.info("✅ Image uploaded and verified in chat!")
                return True, "Image sent and verified successfully"
            
            # Message not found on first try - wait and try again
            time.sleep(2.0)
            message_verified, verify_message = self._verify_message_sent()
            
            if message_verified:
                logger.info("✅ Image uploaded and verified in chat!")
                return True, "Image sent and verified successfully"
            
            # Message still not found - NOW check for errors
            logger.info("Message not found, checking for errors...")
            error_detected, error_message = self._check_send_errors()
            
            if error_detected:
                logger.error(f"❌ Discord error: {error_message}")
                return False, error_message
            
            # No message found, no errors - inconclusive but likely sent
            logger.info("✅ No errors detected - message likely sent")
            return True, "Image sent (no errors detected)"
            # Don't fail completely - message might have sent but verification failed
            logger.info("✅ Image upload completed (delivery unverified)")
            return True, "Image sent (delivery verification inconclusive)"
            
        except PlaywrightTimeout as e:
            logger.error(f"Timeout during image upload: {e}")
            return False, "Upload timeout - operation took too long"
        except PlaywrightError as e:
            logger.error(f"Playwright error during image upload: {e}")
            return False, f"Upload error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during image upload: {e}", exc_info=True)
            return False, f"Unexpected error: {str(e)}"
    
    def _check_send_errors(self) -> Tuple[bool, str]:
        """
        Check for Discord error messages that prevent sending
        
        Returns:
            Tuple of (error_found, error_message)
        """
        try:
            # Error selectors and their meanings
            error_checks = [
                # Rate limit / Slowmode
                {
                    'selectors': [
                        'div[class*="slowModeIcon"]',
                        'span:has-text("Slowmode is enabled")',
                        'div:has-text("You are being rate limited")',
                        'div:has-text("rate limited")',
                        'span[class*="slowmode"]'
                    ],
                    'message': 'Slowmode active - cannot send message yet'
                },
                # Muted / Cannot send
                {
                    'selectors': [
                        'div:has-text("You do not have permission")',
                        'div:has-text("cannot send messages")',
                        'div:has-text("You cannot send")',
                        'div:has-text("не можете отправлять")',  # Russian
                        'span:has-text("Muted")'
                    ],
                    'message': 'Cannot send messages - muted or no permission'
                },
                # Message failed
                {
                    'selectors': [
                        'div:has-text("Message could not be delivered")',
                        'div:has-text("Failed to send")',
                        'div:has-text("не удалось отправить")',  # Russian
                        'div[class*="errorMessage"]',
                        'div[class*="messageError"]'
                    ],
                    'message': 'Message delivery failed'
                },
                # File too large
                {
                    'selectors': [
                        'div:has-text("file is too large")',
                        'div:has-text("файл слишком")',  # Russian
                        'div:has-text("exceeds the")',
                        'span:has-text("8 MB")',
                        'span:has-text("25 MB")'
                    ],
                    'message': 'File is too large to upload'
                },
                # Upload failed
                {
                    'selectors': [
                        'div:has-text("Upload Failed")',
                        'div:has-text("Could not upload")',
                        'div:has-text("ошибка загрузки")',  # Russian
                        'div[class*="uploadError"]'
                    ],
                    'message': 'File upload failed'
                },
                # Generic error toast/notification
                {
                    'selectors': [
                        'div[class*="toast"][class*="error"]',
                        'div[class*="notice"][class*="error"]',
                        'div[class*="errorToast"]'
                    ],
                    'message': 'Discord error notification detected'
                }
            ]
            
            for error_check in error_checks:
                for selector in error_check['selectors']:
                    try:
                        element = self.page.locator(selector).first
                        if element.count() > 0 and element.is_visible(timeout=500):
                            # Try to get actual error text
                            try:
                                error_text = element.inner_text(timeout=1000)
                                if error_text and len(error_text) < 200:
                                    return True, f"{error_check['message']}: {error_text}"
                            except:
                                pass
                            return True, error_check['message']
                    except:
                        continue
            
            # Check for slowmode timer specifically
            try:
                slowmode_timer = self.page.locator('div[class*="slowMode"] span, span[class*="countdown"]').first
                if slowmode_timer.count() > 0 and slowmode_timer.is_visible(timeout=500):
                    try:
                        timer_text = slowmode_timer.inner_text(timeout=1000)
                        return True, f"Slowmode active: wait {timer_text}"
                    except:
                        return True, "Slowmode active - please wait"
            except:
                pass
            
            return False, ""
            
        except Exception as e:
            logger.debug(f"Error checking for send errors: {e}")
            return False, ""
    
    def _verify_message_sent(self) -> Tuple[bool, str]:
        """
        Verify that the message with image was actually sent by current user
        Searches ONLY in chat area, ONLY last few messages
        
        Returns:
            Tuple of (verified, message)
        """
        try:
            # Get current username for comparison
            current_user = self.current_username.lower().strip() if self.current_username else ""
            
            # Clean username - extract just the username part
            if current_user:
                import re
                username_match = re.search(r'([a-z0-9_.]{2,32})', current_user)
                if username_match:
                    current_user = username_match.group(1)
            
            logger.debug(f"Looking for messages from: '{current_user}'")
            
            # Find chat container first (limit search scope)
            chat_container = self._get_chat_container()
            
            if not chat_container:
                logger.debug("Chat container not found")
                return False, "Chat container not found"
            
            # Search for our message with image in last messages
            found = self._find_user_message_with_image(chat_container, current_user)
            
            if found:
                return True, "Image from current user found in chat"
            
            # Fallback: if no username, just check last message has image
            if not current_user:
                if self._last_message_has_image(chat_container):
                    return True, "Image found in last message"
            
            return False, "Message not found in chat"
            
        except Exception as e:
            logger.debug(f"Verification error: {e}")
            return False, f"Verification error: {str(e)}"
    
    def _get_chat_container(self):
        """Get the chat messages container element"""
        container_selectors = [
            '[data-list-id="chat-messages"]',
            'ol[class*="scrollerInner"]',
            'div[class*="messagesWrapper"]'
        ]
        
        for selector in container_selectors:
            try:
                container = self.page.locator(selector).first
                if container.count() > 0:
                    return container
            except:
                continue
        return None
    
    def _find_user_message_with_image(self, chat_container, username: str) -> bool:
        """
        Find message with image from specific user in last 5 messages
        """
        try:
            # Get messages WITHIN chat container only
            messages = chat_container.locator('[data-list-item-id*="chat-messages"], [role="article"]')
            count = messages.count()
            
            if count == 0:
                logger.debug("No messages found in chat")
                return False
            
            # Check ONLY last 5 messages (newest first)
            check_count = min(5, count)
            logger.debug(f"Found {count} messages, checking last {check_count}")
            
            for i in range(count - 1, count - check_count - 1, -1):
                try:
                    msg = messages.nth(i)
                    
                    # Get author from data-text attribute (fast)
                    author = ""
                    try:
                        username_elem = msg.locator('span[class*="username"][data-text]').first
                        if username_elem.count() > 0:
                            author = username_elem.get_attribute('data-text', timeout=200) or ""
                    except:
                        pass
                    
                    # Fallback: get inner text
                    if not author:
                        try:
                            username_elem = msg.locator('span[class*="username"]').first
                            if username_elem.count() > 0:
                                author = username_elem.inner_text(timeout=200)
                        except:
                            continue
                    
                    if not author:
                        continue
                    
                    author_lower = author.lower().strip()
                    logger.debug(f"Message {i}: author='{author}'")
                    
                    # Check for image FIRST (don't filter by username if no username provided)
                    has_image = msg.locator('img[class*="lazyImg"], div[class*="imageContent"], img[src*="cdn.discordapp"]').count() > 0
                    
                    if has_image:
                        logger.debug(f"Message {i} has image, author='{author}'")
                        
                        # If no username to match, any image is success
                        if not username:
                            logger.info(f"✓ Found image (no username filter)")
                            return True
                        
                        # Check if author matches
                        if username in author_lower or author_lower in username:
                            logger.info(f"✓ Found image from '{author}'")
                            return True
                        else:
                            logger.debug(f"Image found but author '{author}' != '{username}'")
                            
                except Exception as e:
                    logger.debug(f"Error checking message {i}: {e}")
                    continue
            
            logger.debug(f"No matching message found")
            return False
            
        except Exception as e:
            logger.debug(f"Error finding user message: {e}")
            return False
    
    def _last_message_has_image(self, chat_container) -> bool:
        """Check if the very last message has an image"""
        try:
            last_msg = chat_container.locator('[data-list-item-id*="chat-messages"]:last-child, [role="article"]:last-child').first
            if last_msg.count() > 0:
                return last_msg.locator('img[class*="lazyImg"], div[class*="imageContent"]').count() > 0
        except:
            pass
        return False
    
    
    def close(self):
        """Close the page"""
        try:
            if self.page and not self.page.is_closed():
                self.page.close()
        except Exception as e:
            logger.debug(f"Error closing page: {e}")

