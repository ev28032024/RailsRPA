"""
Google Sheets Integration Module
Manages profile configuration and status logging via Google Sheets
"""

import logging
import os
import threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Check if gspread is available
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    logger.warning("gspread not installed. Google Sheets integration disabled.")


class GoogleSheetsManager:
    """Manages Google Sheets integration for profile configuration and logging"""
    
    # Google Sheets API scopes
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.readonly'
    ]
    
    # Default column mapping (can be customized in config)
    DEFAULT_COLUMNS = {
        'profile_id': 'A',      # AdsPower Profile ID
        'username': 'B',        # Discord username (for verification)
        'image_name': 'C',      # Image filename (screen)
        'status': 'D',          # Task status
        'timestamp': 'E',       # Last update timestamp (optional)
        'message': 'F'          # Status message (optional)
    }
    
    # Status values
    STATUS_SUCCESS = "✅ Successful"
    STATUS_FAILED = "❌ Failed"
    STATUS_NOT_AUTH = "⚠️ Not Authenticated"
    STATUS_CHANNEL_UNAVAILABLE = "🚫 Channel Unavailable"
    STATUS_USERNAME_MISMATCH = "❓ Username Mismatch"
    STATUS_PENDING = "⏳ Pending"
    STATUS_IN_PROGRESS = "🔄 In Progress"
    
    def __init__(self, config: Dict):
        """
        Initialize Google Sheets manager
        
        Args:
            config: Google Sheets configuration dictionary
        """
        if not GSPREAD_AVAILABLE:
            raise ImportError("gspread is not installed. Run: pip install gspread google-auth google-auth-oauthlib")
        
        self.enabled = config.get('enabled', False)
        self.credentials_file = config.get('credentials_file', 'credentials.json')
        self.spreadsheet_id = config.get('spreadsheet_id', '')
        self.sheet_name = config.get('sheet_name', 'Sheet1')
        self.header_row = config.get('header_row', 1)
        self.data_start_row = config.get('data_start_row', 2)
        
        # Column mapping (customizable)
        self.columns = config.get('columns', self.DEFAULT_COLUMNS)
        
        # Options
        self.verify_username = config.get('verify_username', True)
        self.log_timestamp = config.get('log_timestamp', True)
        self.log_message = config.get('log_message', True)
        
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        
        # Thread lock for safe concurrent access
        self._lock = threading.Lock()
        
        if self.enabled:
            self._connect()
    
    def _connect(self):
        """Establish connection to Google Sheets"""
        try:
            # Check credentials file exists
            if not os.path.exists(self.credentials_file):
                raise FileNotFoundError(
                    f"Google credentials file not found: {self.credentials_file}\n"
                    f"Please create a service account and download credentials.json\n"
                    f"See: GOOGLE_SHEETS_SETUP.md for instructions"
                )
            
            # Authenticate
            logger.info(f"Connecting to Google Sheets...")
            credentials = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=self.SCOPES
            )
            
            self.client = gspread.authorize(credentials)
            
            # Open spreadsheet
            logger.info(f"Opening spreadsheet: {self.spreadsheet_id}")
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            # Get worksheet
            try:
                self.worksheet = self.spreadsheet.worksheet(self.sheet_name)
            except gspread.WorksheetNotFound:
                logger.warning(f"Worksheet '{self.sheet_name}' not found, using first sheet")
                self.worksheet = self.spreadsheet.sheet1
            
            logger.info(f"✅ Connected to Google Sheets: {self.spreadsheet.title}")
            logger.info(f"   Worksheet: {self.worksheet.title}")
            
        except FileNotFoundError as e:
            logger.error(str(e))
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise
    
    def get_profiles(self) -> List[Dict]:
        """
        Get all profiles from Google Sheets
        
        Returns:
            List of profile dictionaries
        """
        if not self.worksheet:
            return []
        
        try:
            # Get all values
            all_values = self.worksheet.get_all_values()
            
            if len(all_values) < self.data_start_row:
                logger.warning("No data found in spreadsheet")
                return []
            
            profiles = []
            
            # Column indices (0-based)
            col_indices = {
                'profile_id': self._col_to_index(self.columns.get('profile_id', 'A')),
                'username': self._col_to_index(self.columns.get('username', 'B')),
                'image_name': self._col_to_index(self.columns.get('image_name', 'C')),
                'status': self._col_to_index(self.columns.get('status', 'D'))
            }
            
            # Parse rows starting from data_start_row (1-based, so -1 for index)
            for row_idx, row in enumerate(all_values[self.data_start_row - 1:], start=self.data_start_row):
                try:
                    profile_id = row[col_indices['profile_id']] if len(row) > col_indices['profile_id'] else ''
                    username = row[col_indices['username']] if len(row) > col_indices['username'] else ''
                    image_name = row[col_indices['image_name']] if len(row) > col_indices['image_name'] else ''
                    status = row[col_indices['status']] if len(row) > col_indices['status'] else ''
                    
                    # Skip empty rows
                    if not profile_id.strip():
                        continue
                    
                    profiles.append({
                        'profile_id': profile_id.strip(),
                        'username': username.strip(),
                        'image_name': image_name.strip(),
                        'current_status': status.strip(),
                        'row_number': row_idx,
                        'enabled': True  # All rows are enabled by default
                    })
                    
                except IndexError:
                    continue
            
            logger.info(f"Loaded {len(profiles)} profiles from Google Sheets")
            return profiles
            
        except Exception as e:
            logger.error(f"Failed to get profiles from Google Sheets: {e}")
            return []
    
    def update_status(self, row_number: int, status: str, message: str = ""):
        """
        Update status for a profile in Google Sheets (thread-safe)
        
        Args:
            row_number: Row number in the spreadsheet (1-based)
            status: Status string
            message: Optional status message
        """
        if not self.worksheet:
            return
        
        with self._lock:
            try:
                # Status column
                status_col = self.columns.get('status', 'D')
                status_cell = f"{status_col}{row_number}"
                
                # Update status
                self.worksheet.update_acell(status_cell, status)
                logger.debug(f"Updated status at {status_cell}: {status}")
                
                # Update timestamp if enabled
                if self.log_timestamp and 'timestamp' in self.columns:
                    timestamp_col = self.columns.get('timestamp', 'E')
                    timestamp_cell = f"{timestamp_col}{row_number}"
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.worksheet.update_acell(timestamp_cell, timestamp)
                
                # Update message if enabled
                if self.log_message and message and 'message' in self.columns:
                    message_col = self.columns.get('message', 'F')
                    message_cell = f"{message_col}{row_number}"
                    self.worksheet.update_acell(message_cell, message[:100])  # Limit message length
                    
            except Exception as e:
                logger.error(f"Failed to update status in Google Sheets: {e}")
    
    def batch_update_status(self, updates: List[Dict]):
        """
        Batch update multiple statuses (more efficient, thread-safe)
        
        Args:
            updates: List of dicts with 'row_number', 'status', 'message' keys
        """
        if not self.worksheet or not updates:
            return
        
        with self._lock:
            try:
                batch_updates = []
                
                for update in updates:
                    row = update['row_number']
                    status = update.get('status', '')
                    message = update.get('message', '')
                    
                    # Status
                    status_col = self.columns.get('status', 'D')
                    batch_updates.append({
                        'range': f"{status_col}{row}",
                        'values': [[status]]
                    })
                    
                    # Timestamp
                    if self.log_timestamp and 'timestamp' in self.columns:
                        timestamp_col = self.columns.get('timestamp', 'E')
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        batch_updates.append({
                            'range': f"{timestamp_col}{row}",
                            'values': [[timestamp]]
                        })
                    
                    # Message
                    if self.log_message and message and 'message' in self.columns:
                        message_col = self.columns.get('message', 'F')
                        batch_updates.append({
                            'range': f"{message_col}{row}",
                            'values': [[message[:100]]]
                        })
                
                # Perform batch update
                self.worksheet.batch_update(batch_updates)
                logger.debug(f"Batch updated {len(updates)} rows")
                
            except Exception as e:
                logger.error(f"Failed to batch update Google Sheets: {e}")
    
    def set_in_progress(self, row_number: int):
        """Mark profile as in progress"""
        self.update_status(row_number, self.STATUS_IN_PROGRESS, "Processing...")
    
    def set_success(self, row_number: int, message: str = "Image sent successfully"):
        """Mark profile as successful"""
        self.update_status(row_number, self.STATUS_SUCCESS, message)
    
    def set_failed(self, row_number: int, message: str = "Task failed"):
        """Mark profile as failed"""
        self.update_status(row_number, self.STATUS_FAILED, message)
    
    def set_not_authenticated(self, row_number: int, message: str = "Account not authenticated"):
        """Mark profile as not authenticated"""
        self.update_status(row_number, self.STATUS_NOT_AUTH, message)
    
    def set_channel_unavailable(self, row_number: int, message: str = "Channel not accessible"):
        """Mark profile as channel unavailable"""
        self.update_status(row_number, self.STATUS_CHANNEL_UNAVAILABLE, message)
    
    def set_username_mismatch(self, row_number: int, expected: str, actual: str):
        """Mark profile as username mismatch"""
        message = f"Expected: {expected}, Got: {actual}"
        self.update_status(row_number, self.STATUS_USERNAME_MISMATCH, message)
    
    def _col_to_index(self, col: str) -> int:
        """Convert column letter to 0-based index (A=0, B=1, etc.)"""
        col = col.upper()
        result = 0
        for char in col:
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1
    
    def is_enabled(self) -> bool:
        """Check if Google Sheets integration is enabled and connected"""
        return self.enabled and self.worksheet is not None
    
    def get_spreadsheet_url(self) -> str:
        """Get the URL of the connected spreadsheet"""
        if self.spreadsheet:
            return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"
        return ""


def check_gspread_available() -> Tuple[bool, str]:
    """
    Check if gspread is available
    
    Returns:
        Tuple of (is_available, message)
    """
    if GSPREAD_AVAILABLE:
        return True, "gspread is available"
    else:
        return False, "gspread not installed. Run: pip install gspread google-auth google-auth-oauthlib"

