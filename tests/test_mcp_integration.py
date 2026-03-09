import unittest
import asyncio
import os
import sys
from src.gbot.mcp_client import GmonClient

class TestMcpIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_ping_pong(self):
        # Setup: Ensure we can find the gmon script by setting PYTHONPATH
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{os.getcwd()}/src"
        
        client = GmonClient()
        # Override params to include PYTHONPATH so it can import from src/gmon/mcp_server.py
        client.params.env = env
        
        try:
            await client.connect()
            response = await client.call_ping("hello-mcp")
            self.assertEqual(response, "pong: hello-mcp")
        finally:
            await client.disconnect()

if __name__ == '__main__':
    unittest.main()
