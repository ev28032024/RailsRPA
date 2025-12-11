"""
AdsPower Discord Automation RPA
Main entry point for the application
"""

import sys
import os
import logging
from pathlib import Path

from src.logger import setup_logging, print_banner
from src.config_manager import ConfigManager
from src.automation_manager import AutomationManager

logger = logging.getLogger(__name__)


def main():
    """Main application entry point"""
    try:
        # Print banner
        print_banner()
        
        # Load configuration
        config_path = os.environ.get('CONFIG_FILE', 'config.yaml')
        
        if not os.path.exists(config_path):
            print(f"\n❌ Configuration file not found: {config_path}")
            print(f"\nPlease create a configuration file. You can use 'config.example.yaml' as a template:")
            print(f"   copy config.example.yaml {config_path}")
            print(f"\nOr set the CONFIG_FILE environment variable to point to your config file.\n")
            return 1
        
        print(f"📄 Loading configuration from: {config_path}")
        config = ConfigManager(config_path)
        
        if not config.load():
            print(f"\n❌ Failed to load configuration. Please check the file and try again.\n")
            return 1
        
        # Setup logging
        log_file = config.get_log_file()
        log_level = config.get_log_level()
        setup_logging(log_file, log_level)
        
        logger.info("Configuration loaded successfully")
        logger.info(f"Found {config.get_profile_count(enabled_only=True)} enabled profiles")
        
        # Verify images directory
        images_dir = config.get_images_dir()
        if not os.path.exists(images_dir):
            logger.error(f"Images directory does not exist: {images_dir}")
            print(f"\n❌ Images directory not found: {images_dir}")
            print(f"Please create the directory and add your images.\n")
            return 1
        
        logger.info(f"Images directory: {images_dir}")
        
        # Check Patchright/Playwright installation
        try:
            try:
                from patchright.sync_api import sync_playwright
                print("\n✅ Using Patchright (undetected Playwright)")
            except ImportError:
                from playwright.sync_api import sync_playwright
                print("\n⚠️  Using regular Playwright (Patchright recommended)")
                print("   Install Patchright for better anti-detection:")
                print("   pip install patchright")
                print("   patchright install chromium")
        except ImportError:
            print("\n❌ Neither Patchright nor Playwright is installed!")
            print("\nPlease install Patchright (recommended):")
            print("   pip install patchright")
            print("   patchright install chromium")
            print("\nOr install regular Playwright:")
            print("   pip install playwright")
            print("   playwright install chromium")
            print()
            return 1
        
        # Verify profiles have images
        profiles = config.get_enabled_profiles()
        
        if not profiles:
            logger.error("No enabled profiles found in configuration")
            print("\n❌ No enabled profiles found in configuration")
            print("Please enable at least one profile in config.yaml\n")
            return 1
        
        missing_images = []
        
        for profile in profiles:
            image_name = profile.get('image_name')
            profile_id = profile.get('profile_id')
            
            if not image_name:
                logger.warning(f"Profile {profile_id} has no image_name")
                missing_images.append((profile_id, "N/A"))
                continue
                
            image_path = config.get_image_path(image_name)
            if not image_path:
                missing_images.append((profile_id, image_name))
        
        if missing_images:
            print("\n⚠️  Warning: Some images are missing:")
            for profile_id, image_name in missing_images:
                print(f"   Profile {profile_id}: {image_name}")
            
            try:
                response = input("\nDo you want to continue anyway? (y/n): ").strip().lower()
                if response != 'y':
                    print("\nAborted.\n")
                    return 0
            except (KeyboardInterrupt, EOFError):
                print("\n\nAborted.\n")
                return 0
        
        # Create automation manager
        manager = AutomationManager(config)
        
        # Confirm before starting
        print(f"\n{'='*60}")
        print(f"Ready to start automation")
        print(f"{'='*60}")
        print(f"Profiles to process: {len(profiles)}")
        print(f"Discord channel: {config.get_discord_url()}")
        print(f"{'='*60}\n")
        
        try:
            input("Press Enter to start or Ctrl+C to cancel...")
            print()
        except (KeyboardInterrupt, EOFError):
            print("\n\nAborted.\n")
            return 0
        
        # Run automation
        manager.run()
        
        logger.info("Automation completed successfully")
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Automation interrupted by user\n")
        logger.info("Automation interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
