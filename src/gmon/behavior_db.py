import json
import os
import logging

logger = logging.getLogger(__name__)

class BehaviorDB:
    def __init__(self, db_path="/var/lib/gbot/behavior_map.json"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.mapping = self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {
            "roblox.com": "gaming",
            "zoom.us": "study",
            "youtube.com": "streaming/study"
        }

    def save_behavior(self, domain, category):
        """Save a learned behavior category for a domain."""
        self.mapping[domain] = category
        try:
            with open(self.db_path, "w") as f:
                json.dump(self.mapping, f, indent=2)
            logger.info(f"Learned: {domain} is {category}")
            return True
        except Exception as e:
            logger.error(f"Failed to save behavior: {e}")
            return False

    def get_category(self, domain):
        return self.mapping.get(domain, "unknown")

    def get_all(self):
        return self.mapping
