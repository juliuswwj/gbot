import aiohttp
import logging
import json

logger = logging.getLogger(__name__)

class GoogleChatInterface:
    def __init__(self, config, brain_callback):
        self.webhook_url = config.google_api.get("chat_webhook_url")
        self.brain_callback = brain_callback
        # List of parent's chat identities (from config)
        self.parent_identities = [p.get("name") for p in config.get_parents()]

    async def handle_incoming_message(self, message_data):
        """Handle messages coming from Google Chat Webhook/API."""
        sender_name = message_data.get("sender", {}).get("displayName")
        message_text = message_data.get("text")
        
        if sender_name in self.parent_identities:
            logger.info(f"Accepted command from Parent: {sender_name}")
            response = await self.brain_callback(message_text)
            await self.send_message(f"@{sender_name} {response}")
        else:
            logger.warning(f"Ignored message from {sender_name} (Unauthorized)")

    async def send_message(self, text):
        """Send a message to the chat space (broadcast or reply)."""
        if not self.webhook_url:
            logger.info(f"Broadcast Message: {text}")
            return

        payload = {"text": text}
        async with aiohttp.ClientSession() as session:
            async with session.post(self.webhook_url, json=payload) as resp:
                if resp.status != 200:
                    logger.error("Failed to send Chat message")
