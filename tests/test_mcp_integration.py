import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from src.gbot.mcp_client import GmonClient

class TestMcpIntegration(unittest.IsolatedAsyncioTestCase):
    @patch("asyncio.open_unix_connection")
    async def test_ping_pong(self, mock_open_connection):
        # Setup mocks
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_open_connection.return_value = (mock_reader, mock_writer)
        
        # We need to mock the ClientSession that connect() creates internally
        # but since we want to test GmonClient, we'll patch ClientSession class
        with patch("src.gbot.mcp_client.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session.initialize = AsyncMock()
            
            # mock_session.call_tool should return a result with content[0].text
            mock_result = MagicMock()
            mock_text_content = MagicMock()
            mock_text_content.text = "pong: hello"
            mock_result.content = [mock_text_content]
            mock_session.call_tool.return_value = mock_result
            
            # When ClientSession(...) is called, return our mock_session
            mock_session_class.return_value = mock_session
            
            # ClientSession is used as an async context manager in connect()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            
            client = GmonClient(socket_path="/fake/socket")
            
            try:
                # Mock connect's enter_async_context
                # Actually, connect uses contextlib.AsyncExitStack
                await client.connect()
                response = await client.call_ping("hello")
                self.assertEqual(response, "pong: hello")
            finally:
                await client.disconnect()

if __name__ == "__main__":
    unittest.main()
