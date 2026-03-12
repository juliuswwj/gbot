import yaml
import os

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.gbot/config.yml")
if not os.path.exists(DEFAULT_CONFIG_PATH):
    DEFAULT_CONFIG_PATH = "/etc/gbot/config.yml"

class GbotConfig:
    def __init__(self, config_data):
        self.home_dir = os.path.dirname(os.getenv("GBOT_CONFIG_PATH", DEFAULT_CONFIG_PATH))
        self.system = config_data.get("system", {})
        self.zoho = config_data.get("zoho", {})
        self.gemini = config_data.get("gemini", {})
        self.users = config_data.get("users", [])

    def get_path(self, key, default_rel_path):
        """Helper to resolve paths relative to config dir if not absolute."""
        val = self.zoho.get(key) or self.system.get(key)
        if not val:
            return os.path.join(self.home_dir, default_rel_path)
        if os.path.isabs(val):
            return val
        return os.path.join(self.home_dir, val)

    @property
    def gemini_api_key(self):
        return self.gemini.get("api_key")

    @property
    def gemini_model(self):
        return self.gemini.get("model", "gemini-3.1-flash-lite-preview")

    @property
    def webhook_token(self):
        return self.zoho.get("webhook_token")

    @property
    def interface(self):
        return self.system.get("interface", "eth0")

    @property
    def cron_chat_id(self):
        return self.zoho.get("cron_chat_id")

    @property
    def cron_chat_language(self):
        return self.zoho.get("cron_chat_language", "en_us")

    @property
    def bot_unique_name(self):
        return self.zoho.get("bot_unique_name")

    def get_user_language(self, email):
        """Get the preferred language for a user by email, default to zh_cn."""
        user = self.get_parent_by_email(email)
        if user:
            return user.get("language", "zh_cn")
        return "zh_cn"

    def get_children(self):
        """Return a list of users with the 'child' role."""
        return [u for u in self.users if u.get("role") == "child"]

    def get_parents(self):
        """Return a list of users with the 'parent' role."""
        return [u for u in self.users if u.get("role") == "parent"]

    def get_parent_by_email(self, email):
        """Find a parent user by their contact email."""
        for u in self.get_parents():
            if u.get("contact") == email:
                return u
        return None

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
