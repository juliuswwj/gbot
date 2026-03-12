
import unittest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.gbot.zoho.cliq import ZohoCliqChannel

class TestZohoCliqChannel(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.brain_callback = AsyncMock()
        
        # Create a mock config object
        self.config = MagicMock()
        self.config.zoho = {"region": "com"}
        self.config.system = {"webhook_port": 8080}
        self.config.webhook_token = "test_token"
        self.config.bot_unique_name = "test_bot"
        
        # Default language mock
        self.config.get_user_language.return_value = "zh_cn"
        
        # Mock ZohoAuth to avoid actual auth attempts
        with patch('src.gbot.zoho.cliq.ZohoAuth'):
            self.channel = ZohoCliqChannel(self.config, self.brain_callback)

    async def _simulate_post(self, data):
        """Helper to simulate an aiohttp POST request."""
        mock_request = MagicMock()
        payload = json.dumps(data).encode('utf-8')
        mock_request.json = AsyncMock(return_value=data)
        mock_request.headers = {"Authorization": f"Bearer {self.config.webhook_token}"}
        
        # Mock read() to return the actual JSON payload
        mock_request.read = AsyncMock(return_value=payload)
        
        # Mock _check_auth to always return True for simplicity in this test
        with patch.object(ZohoCliqChannel, '_check_auth', return_value=True):
            response = await self.channel.handle_chat_webhook(mock_request)
            return response

    async def test_handle_chat_webhook_with_literal_newline(self):
        # Zoho sometimes sends literal control characters in JSON strings
        # We simulate this by manually crafting the payload bytes
        payload_with_newline = b'{"handler":"message","message":{"text":"Hello\nWorld"},"chat":{"id":"C1"},"user":{"email":"user@example.com"}}'
        
        mock_request = MagicMock()
        mock_request.read = AsyncMock(return_value=payload_with_newline)
        mock_request.headers = {"Authorization": f"Bearer {self.config.webhook_token}"}
        
        # We need to mock _process_and_reply to avoid background tasks
        with patch.object(ZohoCliqChannel, '_check_auth', return_value=True):
            with patch.object(self.channel, '_process_and_reply', new_callable=AsyncMock) as mock_process:
                response = await self.channel.handle_chat_webhook(mock_request)
                
                self.assertEqual(response.status, 200)
                mock_process.assert_called_once()
                args, kwargs = mock_process.call_args
                self.assertEqual(args[0], "Hello\nWorld")

    @patch('src.gbot.zoho.cliq.logger')
    async def test_send_message_bot_dm(self, mock_logger):
        # When recipient contains @, it should use the /bots endpoint (DM)
        self.channel.auth.get_access_token.return_value = "fake_token"
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_post.return_value.__aenter__.return_value = mock_resp
            
            await self.channel.send_message("hello", recipient="user@example.com")
            
            args, kwargs = mock_post.call_args
            url = args[0]
            self.assertIn("/bots/test_bot/message", url)
            self.assertEqual(kwargs['json'], {"text": "hello", "userids": "user@example.com"})

    @patch('src.gbot.zoho.cliq.logger')
    async def test_send_message_channel(self, mock_logger):
        # When recipient does NOT contain @, it should use the /chats endpoint
        self.channel.auth.get_access_token.return_value = "fake_token"
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_post.return_value.__aenter__.return_value = mock_resp
            
            await self.channel.send_message("hello", recipient="CT_123")
            
            args, kwargs = mock_post.call_args
            url = args[0]
            self.assertIn("/chats/CT_123/message", url)
            self.assertIn("bot_unique_name=test_bot", url)

    @patch('src.gbot.zoho.cliq.logger')
    async def test_webhook_passes_timezone(self, mock_logger):
        # Test that the webhook correctly extracts and passes timezone
        data = {
            'handler': 'message',
            'message': 'ping',
            'user': {
                'email': 'test@example.com', 
                'first_name': 'Test',
                'timezone': 'America/Los_Angeles'
            },
            'chat': {'id': 'CT_123', 'type': 'bot'}
        }
        self.brain_callback.return_value = "pong"
        
        with patch.object(self.channel, '_process_and_reply', new_callable=AsyncMock) as mock_process:
            # We need to mock _check_auth
            with patch.object(ZohoCliqChannel, '_check_auth', return_value=True):
                await self._simulate_post(data)
                # Wait for the task to be created and "run"
                await asyncio.sleep(0.1)
                
                mock_process.assert_called_once()
                kwargs = mock_process.call_args.kwargs
                self.assertEqual(kwargs['timezone'], 'America/Los_Angeles')

    @patch('src.gbot.zoho.cliq.logger')
    async def test_webhook_passes_chat_type(self, mock_logger):
        # Test that the webhook correctly extracts and passes recipient (email for DM)
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
            
            mock_send.assert_called_once_with("pong", recipient='test@example.com')

if __name__ == '__main__':
    unittest.main()
