import os
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

# The scopes required for gbot functionality
SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]

def get_google_credentials(config_dir="/etc/gbot"):
    """
    Load or create Google OAuth2 credentials.
    Looks for token.json for existing grants, and credentials.json for initial setup.
    """
    token_path = os.path.join(config_dir, "token.json")
    creds_path = os.path.join(config_dir, "google_secret.json")
    
    creds = None
    
    # 1. Try loading existing token
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logger.info("Loaded existing Google OAuth2 token.")
        except Exception as e:
            logger.warning(f"Failed to load existing token: {e}")

    # 2. If no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Google OAuth2 token...")
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Refresh failed: {e}. Re-authentication required.")
                creds = None
        
        if not creds:
            if not os.path.exists(creds_path):
                logger.error(f"Google credentials file not found at {creds_path}. Cannot authenticate.")
                return None
            
            logger.info("Starting new Google OAuth2 flow...")
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            # In a CLI environment like RPi, we use run_local_server
            creds = flow.run_local_server(port=0)
            
        # 3. Save the token for the next run
        try:
            with open(token_path, "w") as token:
                token.write(creds.to_json())
            logger.info(f"Saved new Google OAuth2 token to {token_path}")
        except Exception as e:
            logger.error(f"Failed to save token: {e}")

    return creds
