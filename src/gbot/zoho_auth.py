import os
import logging
import requests
import time

logger = logging.getLogger(__name__)

class ZohoAuth:
    def __init__(self, config):
        self.config = config
        self.client_id = config.zoho.get("client_id")
        self.client_secret = config.zoho.get("client_secret")
        self.refresh_token = config.zoho.get("refresh_token")
        self.region = config.zoho.get("region", "com")
        self.accounts_url = f"https://accounts.zoho.{self.region}/oauth/v2/token"
        
        self._access_token = None
        self._expiry = 0

    def get_access_token(self):
        """Get a valid access token, refreshing if necessary."""
        if self._access_token and time.time() < self._expiry:
            return self._access_token

        if not all([self.client_id, self.client_secret, self.refresh_token]):
            logger.error("Zoho OAuth2 credentials missing in config.")
            return None

        try:
            data = {
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token"
            }
            response = requests.post(self.accounts_url, data=data)
            response.raise_for_status()
            res_json = response.json()
            
            if "access_token" in res_json:
                self._access_token = res_json["access_token"]
                # Expires in 1 hour (3600s), we buffer by 60s
                self._expiry = time.time() + res_json.get("expires_in", 3600) - 60
                logger.info("Successfully refreshed Zoho access token.")
                return self._access_token
            else:
                logger.error(f"Failed to refresh Zoho token: {res_json}")
                return None
        except Exception as e:
            logger.error(f"Error refreshing Zoho token: {e}")
            return None
