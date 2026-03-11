import logging
import asyncio
import json
import os
from aiohttp import web
import aiohttp
from gbot.zoho_auth import ZohoAuth

logger = logging.getLogger(__name__)

class ZohoCliqChannel:
    def __init__(self, config, brain_callback, auth=None):
        self.config = config
        self.brain_callback = brain_callback
        self.auth = auth or ZohoAuth(config)
        self.region = config.zoho.get("region", "com")
        self.base_url = f"https://cliq.zoho.{self.region}/api/v2"
        # For receiving commands via Zoho Webhook
        self.port = config.system.get("webhook_port", 8080)
        self.webhook_token = config.webhook_token
        
        self.user_chat_db = config.user_chat_db
        self.user_chat_map = self._load_user_chats()
        
        self.app = web.Application()
        self.app.router.add_post('/bot/mail', self.handle_webhook)
        self.app.router.add_post('/bot/chat', self.handle_chat_webhook)
        self.runner = None
        self._test_mode_processed = False

    def _load_user_chats(self):
        """Load email to chat_id mapping from file."""
        if os.path.exists(self.user_chat_db):
            try:
                with open(self.user_chat_db, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load user chat DB: {e}")
        return {}

    def _save_user_chats(self):
        """Save current mapping to file."""
        try:
            os.makedirs(os.path.dirname(self.user_chat_db), exist_ok=True)
            with open(self.user_chat_db, 'w') as f:
                json.dump(self.user_chat_map, f)
        except Exception as e:
            logger.error(f"Failed to save user chat DB: {e}")

    async def _check_auth(self, request):
        """Validate Bearer Token if configured."""
        if not self.webhook_token:
            return True
        auth_header = request.headers.get("Authorization")
        expected = f"Bearer {self.webhook_token}"
        if auth_header != expected:
            logger.warning(f"Unauthorized webhook attempt from {request.remote}")
            return False
        return True

    async def handle_webhook(self, request):
        """Receive content from Zoho Mail via Webhook with Bearer Token auth."""
        if not await self._check_auth(request):
            return web.Response(status=401, text="Unauthorized")

        try:
            data = await request.json()
            # Zoho Webhook JSON (Mail): {from, subject, content, id}
            sender_email = data.get('from', '').lower()
            subject = data.get('subject', '')
            content = data.get('content', '')
            msg_id = data.get('id', 'N/A')
            
            logger.info(f"Received Mail Webhook from {sender_email} (ID: {msg_id})")
            
            # 1. Validate sender is a parent
            parent = self.config.get_parent_by_email(sender_email)
            if not parent:
                logger.warning(f"Ignoring mail from non-parent sender: {sender_email}")
                return web.Response(text="Sender not authorized")

            # 2. Lookup chat_id
            chat_id = self.user_chat_map.get(sender_email)
            if not chat_id:
                logger.warning(f"No Cliq chat_id found for parent {sender_email}. Please chat with the bot once.")
            
            # 3. Process command via Brain
            response = await self.brain_callback(f"{subject}\n{content}")
            
            # 4. Send result back to Zoho Cliq if chat_id is known
            if chat_id:
                await self.send_message(f"Processed mail from {sender_email}:\n{response}", chat_id=chat_id)
            else:
                logger.info(f"LLM Response (No chat_id): {response}")
            
            self._test_mode_processed = True
            return web.Response(text="OK")
        except Exception as e:
            logger.exception(f"Error processing mail webhook")
            return web.Response(status=500, text=str(e))

    async def handle_chat_webhook(self, request):
        """Receive content from Zoho Cliq Chat via Webhook (Bot/Outgoing)."""
        if not await self._check_auth(request):
            return web.Response(status=401, text="Unauthorized")

        body = await request.read()
        

        try:
            data = await request.json()
            # Zoho Cliq Structure: {chat: {id}, user: {first_name, email}, message: {text}, handler: "message"}
            
            logger.info(f"Received Zoho Cliq Webhook: {data}")
            chat_info = data.get('chat', {})
            user_info = data.get('user', {})
            msg_info = data.get('message', {})
            handler = data.get('handler', 'message')
            
            chat_id = chat_info.get('id')
            email = user_info.get('email', '').lower()
            user_name = user_info.get('first_name', 'User')

            if handler == 'function':
                # For buttons/cards, extract from action data
                action_info = data.get('action', {})
                action_data = action_info.get('data', {})
                text = action_data.get('action_key', '')
            elif isinstance(msg_info, str):
                text = msg_info
            else:
                text = msg_info.get('text', '')
            
            logger.info(f"Received {handler} from {user_name} ({email}) in chat {chat_id}")
            
            # Update mapping ONLY for DM messages (not mentions or functions)
            if handler == 'message' and email and chat_id:
                if self.user_chat_map.get(email) != chat_id:
                    self.user_chat_map[email] = chat_id
                    self._save_user_chats()
            
            if not text:
                return web.Response(text="No text provided")

            # Process command via Brain in background
            asyncio.create_task(self._process_and_reply(text, chat_id, email=email))
            
            # Return immediate response
            return web.json_response({
                "text": "⏳ 收到，正在处理中..."
            })
        except Exception as e:
            logger.exception(f"Error processing chat webhook")
            return web.Response(status=500, text=str(e))

    async def _process_and_reply(self, text, chat_id, email=None):
        """Process command via Brain and send reply back to chat."""
        try:
            language = self.config.get_user_language(email) if email else "zh_cn"
            response = await self.brain_callback(text, language=language)
            await self.send_message(response, chat_id=chat_id)
        except Exception as e:
            logger.error(f"Error in background processing for chat {chat_id}: {e}")
        finally:
            self._test_mode_processed = True

    async def run_server(self, run_once=False):
        """Start the HTTP server to listen for webhooks."""
        logger.info(f"Starting Zoho Webhook server on port {self.port}...")
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()
        
        if run_once:
            # In test mode, we'll keep the server up until one request is handled 
            # or it's cancelled by the main loop timeout (60s).
            logger.info("Test mode: Webhook server is ready for ONE request.")
            while not self._test_mode_processed:
                await asyncio.sleep(0.5)
            logger.info("Test mode: Webhook processed. Shutting down server...")
        else:
            # Production: Keep running forever
            while True:
                await asyncio.sleep(3600)

    async def send_message(self, content, chat_id=None):
        """Send a message to Zoho Cliq via v2 API using OAuth."""
        if not chat_id:
            logger.info(f"Zoho Cliq (No Chat ID, logging only): {content}")
            return

        access_token = self.auth.get_access_token()
        if not access_token:
            logger.error("Failed to get Zoho access token for sending message.")
            return

        try:
            if isinstance(content, dict):
                payload = content
            else:
                payload = {"text": str(content)}
                
            headers = {
                "Authorization": f"Zoho-oauthtoken {access_token}",
                "Content-Type": "application/json"
            }
            url = f"{self.base_url}/chats/{chat_id}/message"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200 or resp.status == 204:
                        logger.info(f"Successfully sent message to Zoho Cliq chat {chat_id}.")
                    else:
                        logger.error(f"Failed to send to Zoho Cliq: {resp.status} {await resp.text()}")
        except Exception as e:
            logger.error(f"Zoho Cliq send error: {e}")
