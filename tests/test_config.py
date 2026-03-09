import unittest
import os
import tempfile
import yaml
from src.gbot.config import load_config, GbotConfig

class TestConfig(unittest.TestCase):
    def test_load_valid_config(self):
        config_data = {
            "system": {
                "interface": "wlan0",
                "drop_privileges_to": "gbot_user",
                "dnsmasq_conf": "/etc/dnsmasq.conf"
            },
            "mcp": {
                "gmon_path": "/usr/bin/gmon"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            config = load_config(config_path)
            self.assertEqual(config.interface, "wlan0")
            self.assertEqual(config.drop_to_user, "gbot_user")
            self.assertEqual(config.gmon_path, "/usr/bin/gmon")
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
            self.assertEqual(config.drop_to_user, "nobody")
        finally:
            if os.path.exists(config_path):
                os.remove(config_path)

if __name__ == '__main__':
    unittest.main()
