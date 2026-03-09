import yaml
import os

DEFAULT_CONFIG_PATH = "/etc/gbot/config.yml"

class GbotConfig:
    def __init__(self, config_data):
        self.system = config_data.get("system", {})
        self.google_api = config_data.get("google_api", {})
        self.users = config_data.get("users", [])

    @property
    def interface(self):
        return self.system.get("interface", "eth0")

    def get_children(self):
        """Return a list of users with the 'child' role."""
        return [u for u in self.users if u.get("role") == "child"]

    def get_parents(self):
        """Return a list of users with the 'parent' role."""
        return [u for u in self.users if u.get("role") == "parent"]

    def get_user_by_device(self, mac_or_ip):
        """Find which user owns a specific device."""
        for user in self.users:
            devices = user.get("devices", [])
            for dev in devices:
                if isinstance(dev, dict):
                    if dev.get("mac") == mac_or_ip or dev.get("ip") == mac_or_ip:
                        return user
                elif dev == mac_or_ip:
                    return user
        return None

def load_config(path=None):
    if path is None:
        path = os.getenv("GBOT_CONFIG_PATH", DEFAULT_CONFIG_PATH)
    if not os.path.exists(path):
        # Fallback for testing
        return GbotConfig({})
    with open(path, "r") as f:
        data = yaml.safe_load(f)
        return GbotConfig(data or {})
