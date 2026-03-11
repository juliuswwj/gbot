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

    def get_access_token(self, return_full_response=False):
        """Get a valid access token, refreshing if necessary."""
        if not return_full_response and self._access_token and time.time() < self._expiry:
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
                return res_json if return_full_response else self._access_token
            else:
                logger.error(f"Failed to refresh Zoho token: {res_json}")
                return None
        except Exception as e:
            logger.error(f"Error refreshing Zoho token: {e}")
            return None

    def show_current_scopes(self):
        """Refresh token and print the scopes returned by Zoho."""
        print(f"Checking current Zoho token scopes...")
        res = self.get_access_token(return_full_response=True)
        if res and "scope" in res:
            scopes = res["scope"].replace(",", "\n  - ")
            print(f"\n✅ Your current refresh_token has these scopes:")
            print(f"  - {scopes}")
        else:
            print(f"\n❌ Could not retrieve scopes. Please check your credentials.")
            if res:
                print(f"Response: {res}")

    def generate_refresh_token(self, code):
        """Exchange authorization code for a refresh token and save it to config."""
        try:
            data = {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "authorization_code"
            }
            # redirect_uri might be required depending on Zoho app configuration
            redirect_uri = self.config.zoho.get("redirect_uri")
            if redirect_uri:
                data["redirect_uri"] = redirect_uri
            
            logger.info(f"Requesting refresh_token from Zoho...")
            response = requests.post(self.accounts_url, data=data)
            response.raise_for_status()
            res_json = response.json()
            
            if "refresh_token" in res_json:
                refresh_token = res_json["refresh_token"]
                self.refresh_token = refresh_token
                self._update_config_file(refresh_token)
                print(f"\n✅ Success: New refresh_token has been saved to your configuration.")
                return refresh_token
            else:
                print(f"\n❌ Error: Zoho did not return a refresh_token.")
                print(f"Response: {res_json}")
                return None
        except Exception as e:
            print(f"\n❌ Error during token exchange: {e}")
            return None

    def _update_config_file(self, refresh_token):
        """Update the refresh_token in the YAML config file."""
        import yaml
        from gbot.config import DEFAULT_CONFIG_PATH
        
        path = os.getenv("GBOT_CONFIG_PATH", DEFAULT_CONFIG_PATH)
        if not os.path.exists(path):
            # Final fallback check
            path = "/etc/gbot/config.yml"

        if not os.path.exists(path):
            logger.error(f"Could not find config file to update at {path}")
            return

        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}

            if "zoho" not in data:
                data["zoho"] = {}
            data["zoho"]["refresh_token"] = refresh_token

            with open(path, "w") as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"Successfully updated {path}")
        except Exception as e:
            logger.error(f"Failed to write to config file: {e}")

if __name__ == "__main__":
    import argparse
    from gbot.config import load_config
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    parser = argparse.ArgumentParser(description="Zoho OAuth2 Token Utility")
    parser.add_argument("code", nargs="?", help="Optional: Authorization code to generate a NEW refresh_token")
    args = parser.parse_args()
    
    config = load_config()
    auth = ZohoAuth(config)
    
    if args.code:
        auth.generate_refresh_token(args.code)
    else:
        auth.show_current_scopes()
