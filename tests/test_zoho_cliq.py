
import unittest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.gbot.channels.zoho_cliq import ZohoCliqChannel

class TestZohoCliqChannel(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.brain_callback = AsyncMock()
        
        # Create a mock config object
        self.config = MagicMock()
        self.config.zoho = {"region": "com"}
        self.config.system = {"webhook_port": 8080}
        self.config.webhook_token = "test_token"
        self.config.user_chat_db = "/tmp/user_chats.json"
        self.config.bot_unique_name = "test_bot"
        
        # Default language mock
        self.config.get_user_language.return_value = "zh_cn"
        
        # Mock ZohoAuth to avoid actual auth attempts
        with patch('src.gbot.channels.zoho_cliq.ZohoAuth'):
            self.channel = ZohoCliqChannel(self.config, self.brain_callback)
        
        # Mock _save_user_chats and _load_user_chats
        self.channel._save_user_chats = MagicMock()
        self.channel.user_chat_map = {}

    async def _simulate_post(self, data):
        """Helper to simulate an aiohttp POST request."""
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value=data)
        mock_request.headers = {"Authorization": f"Bearer {self.config.webhook_token}"}
        
        # Mock read() for _check_auth
        mock_request.read = AsyncMock(return_value=b"")
        
        # Mock _check_auth to always return True for simplicity in this test
        with patch.object(ZohoCliqChannel, '_check_auth', return_value=True):
            response = await self.channel.handle_chat_webhook(mock_request)
            return response

    @patch('src.gbot.channels.zoho_cliq.logger')
    async def test_send_message_bot_dm(self, mock_logger):
        # When chat_type is 'bot', it should use the /bots endpoint even if chat_id starts with CT_
        self.channel.auth.get_access_token.return_value = "fake_token"
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_post.return_value.__aenter__.return_value = mock_resp
            
            await self.channel.send_message("hello", chat_id="CT_123", chat_type="bot")
            
            args, kwargs = mock_post.call_args
            url = args[0]
            self.assertIn("/bots/test_bot/message", url)
            self.assertEqual(kwargs['json'], {"text": "hello", "userids": "CT_123"})

    @patch('src.gbot.channels.zoho_cliq.logger')
    async def test_send_message_channel(self, mock_logger):
        # When chat_type is 'channel', it should use the /chats endpoint
        self.channel.auth.get_access_token.return_value = "fake_token"
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_post.return_value.__aenter__.return_value = mock_resp
            
            await self.channel.send_message("hello", chat_id="CT_123", chat_type="channel")
            
            args, kwargs = mock_post.call_args
            url = args[0]
            self.assertIn("/chats/CT_123/message", url)
            self.assertIn("bot_unique_name=test_bot", url)

    @patch('src.gbot.channels.zoho_cliq.logger')
    async def test_webhook_passes_chat_type(self, mock_logger):
        # Test that the webhook correctly extracts and passes chat_type
        data = {
            'handler': 'message',
            'message': 'ping',
            'user': {'email': 'test@example.com', 'first_name': 'Test'},
            'chat': {'id': 'CT_123', 'type': 'bot'}
        }
        self.brain_callback.return_value = "pong"
        
        with patch.object(self.channel, 'send_message', new_callable=AsyncMock) as mock_send:
            await self._simulate_post(data)
            await asyncio.sleep(0.1)
            
            mock_send.assert_called_once_with("pong", chat_id='CT_123', chat_type='bot')

if __name__ == '__main__':
    unittest.main()
