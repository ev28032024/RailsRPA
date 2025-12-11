"""
Logging Configuration Module
Sets up logging for the application
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }
    
    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"
        return super().format(record)


def setup_logging(log_file: Optional[str] = None, log_level: str = "INFO"):
    """
    Setup logging configuration
    
    Args:
        log_file: Path to log file (optional)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatters
    console_formatter = ColoredFormatter(
        '%(levelname)s | %(message)s'
    )
    
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if log_file specified)
    if log_file:
        try:
            # Create log directory if it doesn't exist
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
            
            logging.info(f"Logging to file: {log_file}")
        except Exception as e:
            logging.error(f"Failed to setup file logging: {e}")
    
    # Suppress overly verbose loggers
    logging.getLogger('playwright').setLevel(logging.WARNING)
    logging.getLogger('patchright').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    # Suppress asyncio errors that occur during browser cleanup
    # These are harmless warnings about tasks being destroyed
    logging.getLogger('asyncio').setLevel(logging.CRITICAL)


def print_banner():
    """Print application banner"""
    banner = f"""Automated Discord Image Sender"""
    print(banner)