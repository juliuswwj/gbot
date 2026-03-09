import yaml
import os
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_path="/etc/gbot/config.yml"):
        self.config_path = config_path

    def update_user_devices(self, user_name, devices):
        """
        Update the devices list for a specific user in config.yml.
        devices: list of {"mac": "...", "name": "..."}
        """
        try:
            if not os.path.exists(self.config_path):
                return False, "Config file not found."

            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f) or {}

            users = config.get("users", [])
            found = False
            for user in users:
                if user.get("name") == user_name:
                    user["devices"] = devices
                    found = True
                    break
            
            if not found:
                return False, f"User '{user_name}' not found in config."

            with open(self.config_path, "w") as f:
                yaml.safe_dump(config, f, default_flow_style=False)
            
            logger.info(f"Updated devices for {user_name}")
            return True, f"Successfully updated devices for {user_name}."
        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return False, str(e)
