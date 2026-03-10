import logging
import asyncio
import base64
from googleapiclient.discovery import build
from src.gbot.google_auth import get_google_credentials

logger = logging.getLogger(__name__)

class GmailPoller:
    def __init__(self, config, brain_callback):
        self.config = config
        self.brain_callback = brain_callback
        self.parent_emails = [p.get("contact") for p in config.get_parents()]
        self.service = None

    def _get_service(self):
        if self.service: return self.service
        creds = get_google_credentials()
        if creds:
            self.service = build('gmail', 'v1', credentials=creds)
        return self.service

    async def poll_forever(self):
        """Periodically poll Gmail for messages from parents."""
        while True:
            service = self._get_service()
            if not service:
                await asyncio.sleep(60)
                continue

            try:
                # 1. Fetch unread messages
                results = service.users().messages().list(userId='me', q="is:unread").execute()
                messages = results.get('messages', [])

                for msg_ref in messages:
                    msg = service.users().messages().get(userId='me', id=msg_ref['id']).execute()
                    
                    # Get sender
                    headers = msg['payload']['headers']
                    sender = next(h['value'] for h in headers if h['name'] == 'From')
                    
                    # Extract email address between <>
                    if '<' in sender:
                        sender_email = sender.split('<')[1].split('>')[0]
                    else:
                        sender_email = sender

                    if sender_email in self.parent_emails:
                        # Extract body (simplified)
                        body = ""
                        if 'data' in msg['payload']['body']:
                            body = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode()
                        
                        logger.info(f"Accepted command from parent via Gmail: {sender_email}")
                        response = await self.brain_callback(body)
                        await self.send_reply(sender_email, response)
                        
                        # Mark as read
                        service.users().messages().batchModify(userId='me', body={
                            'ids': [msg_ref['id']],
                            'removeLabelIds': ['UNREAD']
                        }).execute()

            except Exception as e:
                logger.error(f"Gmail poll error: {e}")
            
            await asyncio.sleep(60)

    async def send_reply(self, to, text):
        service = self._get_service()
        if not service: return
        
        logger.info(f"Sending Gmail reply to {to}")
        try:
            message = {
                'raw': base64.urlsafe_b64encode(
                    f"To: {to}\nSubject: Re: gbot control\n\n{text}".encode()
                ).decode()
            }
            service.users().messages().send(userId='me', body=message).execute()
        except Exception as e:
            logger.error(f"Failed to send Gmail reply: {e}")
