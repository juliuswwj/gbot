import unittest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from gbot.brain import GeminiBrain
from gbot.config import GbotConfig

class TestBrainPrompt(unittest.TestCase):
    def setUp(self):
        self.config = GbotConfig({
            "users": [
                {"name": "Alice", "role": "parent", "tags": ["admin"]},
                {"name": "Bob", "role": "child", "tags": ["xiaoming"]}
            ]
        })
        self.brain = GeminiBrain(self.config)
        self.scheduler = MagicMock()
        self.brain.scheduler = self.scheduler

    def test_get_family_info(self):
        info = self.brain._get_family_info()
        self.assertIn("Alice (parent)", info)
        self.assertIn("Bob (child)", info)
        self.assertIn("Tags: [admin]", info)
        self.assertIn("Tags: [xiaoming]", info)

    def test_get_schedule_info_empty(self):
        self.scheduler.active_sessions = {}
        info = self.brain._get_schedule_info()
        self.assertEqual(info, "No active rest or study sessions currently scheduled.")

    def test_get_schedule_info_active(self):
        now = datetime.now()
        end_time = now + timedelta(minutes=30)
        self.scheduler.active_sessions = {
            "Bob": {"end_time": end_time}
        }
        info = self.brain._get_schedule_info()
        self.assertIn("Bob: Active session until", info)
        self.assertIn("mins remaining", info)

if __name__ == '__main__':
    unittest.main()
