
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
    async def test_handler_message_updates_map(self, mock_logger):
        data = {
            'handler': 'message',
            'message': 'ping',
            'user': {'email': 'test@example.com', 'first_name': 'Test'},
            'chat': {'id': 'chat_123'}
        }
        self.brain_callback.return_value = "pong"
        
        with patch.object(self.channel, 'send_message', new_callable=AsyncMock):
            await self._simulate_post(data)
            await asyncio.sleep(0.1)
            
            self.assertEqual(self.channel.user_chat_map.get('test@example.com'), 'chat_123')
            self.channel._save_user_chats.assert_called_once()
            self.brain_callback.assert_called_once_with('ping', language='zh_cn')

    @patch('src.gbot.channels.zoho_cliq.logger')
    async def test_handler_mention_does_not_update_map(self, mock_logger):
        data = {
            'handler': 'mention',
            'message': 'ping @bot',
            'user': {'email': 'test@example.com', 'first_name': 'Test'},
            'chat': {'id': 'channel_123'}
        }
        self.brain_callback.return_value = "pong"
        
        with patch.object(self.channel, 'send_message', new_callable=AsyncMock):
            await self._simulate_post(data)
            await asyncio.sleep(0.1)
            
            self.assertIsNone(self.channel.user_chat_map.get('test@example.com'))
            self.channel._save_user_chats.assert_not_called()
            self.brain_callback.assert_called_once_with('ping @bot', language='zh_cn')

    @patch('src.gbot.channels.zoho_cliq.logger')
    async def test_handler_function_extracts_action_key(self, mock_logger):
        data = {
            'handler': 'function',
            'action': {'data': {'action_key': 'approve'}},
            'user': {'email': 'test@example.com', 'first_name': 'Test'},
            'chat': {'id': 'chat_123'}
        }
        self.brain_callback.return_value = "Approved!"
        self.config.get_user_language.return_value = "en_us"
        
        with patch.object(self.channel, 'send_message', new_callable=AsyncMock) as mock_send:
            await self._simulate_post(data)
            await asyncio.sleep(0.1)
            
            self.brain_callback.assert_called_once_with('approve', language='en_us')
            mock_send.assert_called_once_with("Approved!", chat_id='chat_123')
            self.assertIsNone(self.channel.user_chat_map.get('test@example.com'))

    @patch('src.gbot.channels.zoho_cliq.logger')
    async def test_send_message_dict_payload(self, mock_logger):
        complex_payload = {
            "text": "Choose:",
            "buttons": [{"label": "Yes", "type": "plus"}]
        }
        self.channel.auth.get_access_token.return_value = "fake_token"
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_post.return_value.__aenter__.return_value = mock_resp
            
            await self.channel.send_message(complex_payload, chat_id="chat_123")
            kwargs = mock_post.call_args[1]
            self.assertEqual(kwargs['json'], complex_payload)

if __name__ == '__main__':
    unittest.main()
