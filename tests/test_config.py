import unittest
import os
import tempfile
import yaml
from gbot.config import load_config, GbotConfig

class TestConfig(unittest.TestCase):
    def test_load_valid_config(self):
        config_data = {
            "system": {
                "interface": "wlan0",
                "dnsmasq_conf": "/etc/dnsmasq.conf"
            },
            "users": [
                {"name": "Xiao Ming", "role": "child", "tag": "xiaoming"},
                {"name": "Dad", "role": "parent", "contact": "dad@gmail.com"}
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            config = load_config(config_path)
            self.assertEqual(config.interface, "wlan0")
            self.assertEqual(len(config.get_children()), 1)
            self.assertEqual(config.get_children()[0]["name"], "Xiao Ming")
            self.assertEqual(len(config.get_parents()), 1)
        finally:
            if os.path.exists(config_path):
                os.remove(config_path)

    def test_default_values(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump({}, f)
            config_path = f.name
            
        try:
            config = load_config(config_path)
            self.assertEqual(config.interface, "eth0")
            self.assertEqual(len(config.get_children()), 0)
        finally:
            if os.path.exists(config_path):
                os.remove(config_path)

    def test_new_config_structure(self):
        config_data = {
            "gemini": {
                "api_key": "test_key",
                "model": "test_model"
            },
            "zoho": {
                "webhook_token": "test_bearer_token"
            }
        }
        config = GbotConfig(config_data)
        self.assertEqual(config.gemini_api_key, "test_key")
        self.assertEqual(config.gemini_model, "test_model")
        self.assertEqual(config.webhook_token, "test_bearer_token")

    def test_language_config(self):
        config_data = {
            "zoho": {
                "cron_chat_language": "fr_fr"
            },
            "users": [
                {"name": "Dad", "role": "parent", "contact": "dad@gmail.com", "language": "ja_jp"},
                {"name": "Mom", "role": "parent", "contact": "mom@gmail.com"}
            ]
        }
        config = GbotConfig(config_data)
        # Default cron chat language is en_us if not provided, but here it's fr_fr
        self.assertEqual(config.cron_chat_language, "fr_fr")
        # Default for empty config is en_us
        self.assertEqual(GbotConfig({}).cron_chat_language, "en_us")
        
        # User ja_jp
        self.assertEqual(config.get_user_language("dad@gmail.com"), "ja_jp")
        # User default zh_cn
        self.assertEqual(config.get_user_language("mom@gmail.com"), "zh_cn")
        # Unknown user default zh_cn
        self.assertEqual(config.get_user_language("unknown@gmail.com"), "zh_cn")

if __name__ == '__main__':
    unittest.main()
