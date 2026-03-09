import logging
import asyncio

logger = logging.getLogger(__name__)

class GmailPoller:
    def __init__(self, config, brain_callback):
        self.config = config
        self.brain_callback = brain_callback
        self.parent_emails = [p.get("contact") for p in config.get_parents()]

    async def poll_forever(self):
        """Periodically poll Gmail for messages from parents."""
        while True:
            # 1. Fetch unread emails
            # In real: messages = service.users().messages().list(q="is:unread").execute()
            
            # 2. Check sender
            # sender = message['from']
            # if sender in self.parent_emails:
            #    logger.info(f"Received instruction from parent: {sender}")
            #    response = await self.brain_callback(message_text)
            #    await self.send_reply(sender, response)
            # else:
            #    logger.warning(f"Ignoring email from unauthorized sender: {sender}")
            
            await asyncio.sleep(60)

    async def send_reply(self, to, text):
        """Send an email reply (can be sent to anyone)."""
        logger.info(f"Replying to {to}: {text}")
        pass
