"""
Stealth Module - Anti-detection techniques
Masks automation to appear as regular human browser usage
"""

import random
import time
import logging
from typing import Tuple, Optional

try:
    from patchright.sync_api import Page, BrowserContext
except ImportError:
    from playwright.sync_api import Page, BrowserContext

logger = logging.getLogger(__name__)


class StealthManager:
    """Manages stealth techniques to avoid detection"""
    
    def __init__(self, page: Page):
        """
        Initialize stealth manager
        
        Args:
            page: Playwright page object
        """
        self.page = page
    
    def apply_stealth_scripts(self):
        """
        Apply JavaScript to mask automation detection
        Overrides common bot detection methods
        """
        try:
            logger.debug("Applying stealth scripts...")
            
            # Anti-detection script
            stealth_js = """
            // Webdriver detection bypass
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Chrome detection
            window.chrome = {
                runtime: {}
            };
            
            // Permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Plugin length
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Hardware concurrency (CPU cores)
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });
            
            // Device memory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });
            
            // Platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });
            
            // Vendor
            Object.defineProperty(navigator, 'vendor', {
                get: () => 'Google Inc.'
            });
            
            // Console debug protection
            const originalLog = console.log;
            console.log = (...args) => {
                if (!args.join(' ').includes('Webdriver')) {
                    originalLog(...args);
                }
            };
            
            // Remove automation indicators
            delete navigator.__proto__.webdriver;
            
            // Override automation flags
            Object.defineProperty(document, 'hidden', { get: () => false });
            Object.defineProperty(document, 'visibilityState', { get: () => 'visible' });
            """
            
            self.page.add_init_script(stealth_js)
            logger.debug("✓ Stealth scripts applied")
            
        except Exception as e:
            logger.warning(f"Could not apply stealth scripts: {e}")
    
    def random_delay(self, min_seconds: float = 0.5, max_seconds: float = 2.0):
        """
        Random delay to simulate human behavior
        
        Args:
            min_seconds: Minimum delay in seconds
            max_seconds: Maximum delay in seconds
        """
        delay = random.uniform(min_seconds, max_seconds)
        logger.debug(f"Human-like delay: {delay:.2f}s")
        time.sleep(delay)
    
    def human_like_typing(self, text: str, element_selector: str = None, element = None):
        """
        Type text with human-like delays between keystrokes
        
        Args:
            text: Text to type
            element_selector: CSS selector of element to type into
            element: Or direct element locator
        """
        try:
            if element is None and element_selector:
                element = self.page.locator(element_selector).first
            
            if element:
                element.focus()
                self.random_delay(0.2, 0.5)
                
                for char in text:
                    element.type(char)
                    # Random delay between keystrokes (50-150ms)
                    delay = random.uniform(0.05, 0.15)
                    time.sleep(delay)
                
                logger.debug(f"Typed text with human-like timing")
            
        except Exception as e:
            logger.warning(f"Error in human_like_typing: {e}")
    
    def random_mouse_movement(self):
        """
        Perform random mouse movements to simulate human activity
        """
        try:
            # Get viewport size
            viewport = self.page.viewport_size
            if not viewport:
                return
            
            width = viewport['width']
            height = viewport['height']
            
            # Random movements (2-4 moves)
            num_moves = random.randint(2, 4)
            
            for _ in range(num_moves):
                x = random.randint(100, width - 100)
                y = random.randint(100, height - 100)
                
                # Move mouse to random position
                self.page.mouse.move(x, y)
                self.random_delay(0.1, 0.3)
            
            logger.debug(f"Performed {num_moves} random mouse movements")
            
        except Exception as e:
            logger.debug(f"Could not perform mouse movements: {e}")
    
    def random_scroll(self):
        """
        Perform random scrolling to simulate reading
        """
        try:
            # Random scroll distance
            scroll_distance = random.randint(100, 500)
            
            # Scroll down
            self.page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            self.random_delay(0.5, 1.5)
            
            # Sometimes scroll back up a bit
            if random.random() > 0.5:
                scroll_back = random.randint(50, 200)
                self.page.evaluate(f"window.scrollBy(0, -{scroll_back})")
                self.random_delay(0.3, 0.8)
            
            logger.debug("Performed human-like scrolling")
            
        except Exception as e:
            logger.debug(f"Could not perform scrolling: {e}")
    
    def human_like_click(self, element, move_mouse: bool = True):
        """
        Click element with human-like behavior
        
        Args:
            element: Element to click
            move_mouse: Whether to move mouse to element first
        """
        try:
            if move_mouse:
                # Get element position
                box = element.bounding_box()
                if box:
                    # Ensure we don't go outside element bounds
                    min_x = max(5, 0)
                    max_x = max(box['width'] - 5, min_x + 1)
                    min_y = max(5, 0)
                    max_y = max(box['height'] - 5, min_y + 1)
                    
                    # Move to random point within element
                    x = box['x'] + random.uniform(min_x, max_x)
                    y = box['y'] + random.uniform(min_y, max_y)
                    
                    # Move mouse
                    self.page.mouse.move(x, y)
                    self.random_delay(0.1, 0.3)
            
            # Small delay before click
            self.random_delay(0.05, 0.15)
            
            # Click
            element.click()
            
            # Small delay after click
            self.random_delay(0.1, 0.3)
            
            logger.debug("Performed human-like click")
            
        except Exception as e:
            logger.warning(f"Error in human_like_click: {e}")
            # Fallback to regular click
            try:
                element.click()
            except Exception as click_error:
                logger.error(f"Failed to click element: {click_error}")
                raise
    
    def simulate_reading(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """
        Simulate user reading the page
        
        Args:
            min_seconds: Minimum reading time
            max_seconds: Maximum reading time
        """
        reading_time = random.uniform(min_seconds, max_seconds)
        logger.debug(f"Simulating reading for {reading_time:.2f}s")
        
        # During "reading", perform some activities
        start_time = time.time()
        
        while time.time() - start_time < reading_time:
            action = random.choice(['wait', 'mouse', 'scroll'])
            
            if action == 'mouse':
                self.random_mouse_movement()
            elif action == 'scroll':
                self.random_scroll()
            else:
                self.random_delay(0.5, 1.0)
    
    def add_random_pauses(self):
        """
        Add random micro-pauses to simulate human hesitation
        """
        if random.random() > 0.7:  # 30% chance
            pause = random.uniform(0.5, 2.0)
            logger.debug(f"Random pause: {pause:.2f}s")
            time.sleep(pause)
    
    def get_random_typing_speed(self) -> Tuple[float, float]:
        """
        Get random typing speed range for current "session"
        Simulates different users typing at different speeds
        
        Returns:
            Tuple of (min_delay, max_delay) between keystrokes
        """
        # Different typing speed profiles
        profiles = [
            (0.08, 0.15),  # Fast typer
            (0.10, 0.20),  # Average typer
            (0.15, 0.30),  # Slow typer
        ]
        
        return random.choice(profiles)
    
    def simulate_human_behavior_before_action(self, action_type: str = "general"):
        """
        Simulate realistic human behavior before performing an action
        
        Args:
            action_type: Type of action (general, click, type, upload)
        """
        logger.debug(f"Simulating human behavior before: {action_type}")
        
        # Small chance of mouse movement
        if random.random() > 0.6:
            self.random_mouse_movement()
        
        # Small chance of scroll
        if random.random() > 0.7:
            self.random_scroll()
        
        # Always add a small random delay
        self.random_delay(0.3, 1.0)
        
        # Occasional longer pause (hesitation)
        if random.random() > 0.85:
            self.random_delay(1.0, 2.5)


def configure_stealth_context(context: BrowserContext):
    """
    Configure browser context with stealth settings
    Note: AdsPower already provides a configured context,
    but we can add extra settings
    
    Args:
        context: Browser context to configure
    """
    try:
        logger.debug("Configuring stealth context settings...")
        
        # Add extra headers to appear more human
        extra_headers = {
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        context.set_extra_http_headers(extra_headers)
        logger.debug("✓ Extra HTTP headers configured")
        
    except Exception as e:
        logger.debug(f"Could not configure context: {e}")


def get_random_viewport() -> dict:
    """
    Get random but realistic viewport size
    
    Returns:
        Dictionary with width and height
    """
    # Common desktop resolutions
    viewports = [
        {'width': 1920, 'height': 1080},
        {'width': 1366, 'height': 768},
        {'width': 1536, 'height': 864},
        {'width': 1440, 'height': 900},
        {'width': 1280, 'height': 720},
    ]
    
    return random.choice(viewports)

