"""
Setup script for AdsPower Discord Automation
"""

import os
import sys
import subprocess
from pathlib import Path


def print_step(step_num, message):
    """Print a step message"""
    print(f"\n{'='*60}")
    print(f"Step {step_num}: {message}")
    print(f"{'='*60}\n")


def main():
    """Run setup"""
    print("\n" + "="*60)
    print("  AdsPower Discord Automation - Setup")
    print("="*60)
    
    try:
        # Step 1: Check Python version
        print_step(1, "Checking Python version")
        python_version = sys.version_info
        print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
            print("❌ Python 3.8 or higher is required!")
            return 1
        
        print("✅ Python version OK")
        
        # Step 2: Install dependencies
        print_step(2, "Installing Python dependencies")
        print("Running: pip install -r requirements.txt\n")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        
        if result.returncode != 0:
            print("\n❌ Failed to install dependencies")
            return 1
        
        print("\n✅ Dependencies installed")
        
        # Step 3: Install Patchright/Playwright browsers
        print_step(3, "Installing Patchright browsers")
        print("Running: patchright install chromium\n")
        
        # Try Patchright first, fallback to Playwright
        result = subprocess.run(["patchright", "install", "chromium"])
        
        if result.returncode != 0:
            print("\n⚠️  Trying playwright install instead...")
            result = subprocess.run(["playwright", "install", "chromium"])
            if result.returncode != 0:
                print("\n⚠️  Browser installation may have failed")
                print("You can try manually: patchright install chromium")
            else:
                print("\n✅ Playwright browsers installed")
        else:
            print("\n✅ Patchright browsers installed (undetected version)")
        
        # Step 4: Create directories
        print_step(4, "Creating directories")
        
        images_dir = Path("images")
        if not images_dir.exists():
            images_dir.mkdir()
            print(f"✅ Created: {images_dir}")
        else:
            print(f"ℹ️  Already exists: {images_dir}")
        
        # Step 5: Create config from example
        print_step(5, "Setting up configuration")
        
        config_file = Path("config.yaml")
        config_example = Path("config.example.yaml")
        
        if not config_file.exists() and config_example.exists():
            import shutil
            shutil.copy(config_example, config_file)
            print(f"✅ Created config.yaml from example")
            print(f"⚠️  Please edit config.yaml with your settings!")
        elif config_file.exists():
            print(f"ℹ️  config.yaml already exists (keeping existing)")
        else:
            print(f"⚠️  config.example.yaml not found, skipping")
        
        # Step 6: Final instructions
        print_step(6, "Setup Complete!")
        
        print("✅ Setup completed successfully!\n")
        print("Next steps:")
        print("  1. Edit config.yaml with your AdsPower profiles and settings")
        print("  2. Add your images to the 'images' folder")
        print("  3. Make sure AdsPower is running")
        print("  4. Run: python main.py")
        print()
        print("For help, see README.md")
        print()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user\n")
        return 130
    except Exception as e:
        print(f"\n❌ Setup error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

