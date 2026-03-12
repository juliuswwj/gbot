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
        
        self.app = web.Application()
        self.app.router.add_post('/bot/mail', self.handle_webhook)
        self.app.router.add_post('/bot/chat', self.handle_chat_webhook)
        self.runner = None
        self._test_mode_processed = False

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

        body = await request.read()

        try:
            data = json.loads(body.decode('utf-8', errors='replace'), strict=False)
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

            # 2. Process command via Brain
            response = await self.brain_callback(f"{subject}\n{content}")
            
            # 3. Send result back to Zoho Cliq (DM to sender)
            await self.send_message(f"Processed mail from {sender_email}:\n{response}", recipient=sender_email)
            
            self._test_mode_processed = True
            return web.Response(text="OK")
        except Exception as e:
            logger.exception(f"Error processing mail webhook {data}")
            return web.Response(status=500, text=str(e))

    async def handle_chat_webhook(self, request):
        """Receive content from Zoho Cliq Chat via Webhook (Bot/Outgoing)."""
        if not await self._check_auth(request):
            return web.Response(status=401, text="Unauthorized")

        body = await request.read()
        

        try:
            data = json.loads(body.decode('utf-8', errors='replace'), strict=False)
            # Zoho Cliq Structure: {chat: {id}, user: {first_name, email}, message: {text}, handler: "message"}
            
            chat_info = data.get('chat', {})
            user_info = data.get('user', {})
            msg_info = data.get('message', {})
            handler = data.get('handler', 'message')
            
            chat_id = chat_info.get('id')
            chat_type = chat_info.get('type') # 'bot' or 'channel'
            email = user_info.get('email', '').lower()
            user_name = user_info.get('first_name', 'User')
            timezone = user_info.get('timezone')
            # Zoho might put recent_messages at top level or inside 'chat'
            recent_msgs = data.get('recent_messages') or chat_info.get('recent_messages') or []
            
            # Format history for LLM (last 5 messages)
            history_str = ""
            for m in recent_msgs[-5:]:
                sender = m.get('sender', {}).get('name', 'Unknown')
                text = m.get('text', '')
                history_str += f"[{sender}]: {text}\n"

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
            
            if not text:
                return web.Response(text="No text provided")

            # Process command via Brain in background
            asyncio.create_task(self._process_and_reply(text, chat_id, chat_type=chat_type, email=email, timezone=timezone, history=history_str))
            
            # Return immediate response
            return web.json_response({
                "text": "⏳ 收到，正在处理中..."
            })
        except Exception as e:
            logger.exception(f"Error processing chat webhook {body}")
            return web.Response(status=500, text=str(e))

    async def _process_and_reply(self, text, chat_id, chat_type=None, email=None, timezone=None, history=None):
        """Process command via Brain and send reply back to chat."""
        try:
            language = self.config.get_user_language(email) if email else "zh_cn"
            response = await self.brain_callback(text, language=language, timezone=timezone, history=history)
            recipient = email if chat_type == 'bot' and email else chat_id
            await self.send_message(response, recipient=recipient)
        except Exception as e:
            logger.exception(f"Error in background processing for chat {chat_id}")
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

    async def send_message(self, content, recipient=None):
        """Send a message to Zoho Cliq. Handles both Chat/Channel IDs and User DMs (recipient)."""
        if not recipient:
            logger.info(f"Zoho Cliq (No Recipient, logging only): {content}")
            return

        access_token = self.auth.get_access_token()
        if not access_token:
            logger.error("Failed to get Zoho access token for sending message.")
            return

        bot_name = self.config.bot_unique_name

        try:
            if isinstance(content, dict):
                payload = content
            else:
                payload = {"text": str(content)}

            headers = {
                "Authorization": f"Zoho-oauthtoken {access_token}",
                "Content-Type": "application/json"
            }

            # If recipient contains @, it is an email (DM), otherwise it is a chat_id (Channel)
            is_dm = "@" in recipient

            if is_dm:
                # Endpoint for sending to user(s) from bot directly
                if not bot_name:
                    logger.error("bot_unique_name missing in config, cannot send DM.")
                    return
                url = f"{self.base_url}/bots/{bot_name}/message"
                payload["userids"] = recipient
            else:
                # Endpoint for specific chat (Channel/Group via chat_id)
                url = f"{self.base_url}/chats/{recipient}/message"
                if bot_name:
                    url += f"?bot_unique_name={bot_name}"

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status in [200, 204]:
                        logger.info(f"Successfully sent message to {url}")
                    else:
                        logger.error(f"Failed to send to {url}: {resp.status} {await resp.text()}")
        except Exception as e:
            logger.error(f"Zoho Cliq send error: {e}")
