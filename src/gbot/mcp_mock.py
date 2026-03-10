import asyncio
import logging
import json

logger = logging.getLogger(__name__)

class MockGmonClient:
    def __init__(self, socket_path=None):
        logger.info("Initializing MOCK Gmon Client (Test Mode)")

    async def connect(self):
        logger.info("MOCK: Connected to gmon (simulated)")
        return self

    async def call_tool(self, tool_name, arguments):
        logger.info(f"MOCK: Calling tool '{tool_name}' with {arguments}")
        
        # Simulate basic responses
        if tool_name == "get_host_info":
            return MagicMockContent('[{"mac": "AA:BB:CC:DD:EE:FF", "tag": "xiaoming", "ip": "192.168.1.5", "name": "iPad"}]')
        elif tool_name == "get_host_activity":
            return MagicMockContent('{"roblox.com": {"bytes": 5000000}, "zoom.us": {"bytes": 1000}}')
        elif tool_name == "ping":
            return MagicMockContent("pong: mock")
        
        return MagicMockContent("Success (Mocked)")

    async def call_ping(self, message):
        return f"pong: {message} (mock)"

    async def disconnect(self):
        logger.info("MOCK: Disconnected (simulated)")

class MagicMockContent:
    def __init__(self, text):
        self.content = [MagicMockText(text)]

class MagicMockText:
    def __init__(self, text):
        self.text = text
