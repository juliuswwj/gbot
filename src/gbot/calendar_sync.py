import asyncio
import logging
from datetime import datetime, timedelta
from src.gbot.google_auth import get_google_credentials

logger = logging.getLogger(__name__)

class CalendarSync:
    def __init__(self, config, scheduler):
        self.config = config
        self.scheduler = scheduler
        self.service = None

    def _get_service(self):
        if self.service: return self.service
        try:
            creds = get_google_credentials()
            if not creds:
                return None
            self.service = build('calendar', 'v3', credentials=creds)
            return self.service
        except Exception as e:
            logger.error(f"Failed to init Google Calendar: {e}")
            return None

    async def sync_now(self):
        service = self._get_service()
        if not service: return

        now = datetime.utcnow().isoformat() + 'Z'
        for child in self.config.get_children():
            cal_id = child.get("calendar_id")
            if not cal_id: continue
            
            try:
                events_result = service.events().list(calendarId=cal_id, timeMin=now,
                                                    maxResults=5, singleEvents=True,
                                                    orderBy='startTime').execute()
                events = events_result.get('items', [])
                
                for event in events:
                    summary = event.get('summary', '').lower()
                    start_str = event['start'].get('dateTime') or event['start'].get('date')
                    end_str = event['end'].get('dateTime') or event['end'].get('date')
                    
                    # Logic to identify Rest or Class sessions
                    if "rest" in summary or "sleep" in summary or "class" in summary or "study" in summary:
                        end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                        # Add to scheduler
                        self.scheduler.schedule_child_rest(child['name'], [], end_time)
                        
            except Exception as e:
                logger.error(f"Error syncing cal {cal_id}: {e}")

    async def run_loop(self):
        while True:
            await self.sync_now()
            await asyncio.sleep(900) # Sync every 15 mins
