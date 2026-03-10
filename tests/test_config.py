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

if __name__ == '__main__':
    unittest.main()
