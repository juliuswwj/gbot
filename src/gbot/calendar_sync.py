import asyncio
import logging
import requests
from datetime import datetime, timezone
from gbot.zoho_auth import ZohoAuth

logger = logging.getLogger(__name__)

class CalendarSync:
    def __init__(self, config, scheduler, auth=None):
        self.config = config
        self.scheduler = scheduler
        self.auth = auth or ZohoAuth(config)
        self.region = config.zoho.get("region", "com")
        self.base_url = f"https://calendar.zoho.{self.region}/api/v1"

    async def sync_now(self):
        """Sync Zoho Calendar events for all children."""
        access_token = self.auth.get_access_token()
        if not access_token:
            return

        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }

        # Current time in UTC for comparison
        now = datetime.now(timezone.utc)
        
        for child in self.config.get_children():
            # In Zoho, calendar ID is needed. 
            # We assume it's the primary one if not specified or specific ID provided.
            cal_id = child.get("calendar_id")
            if not cal_id:
                # To get primary, one might first list_calendars, but we expect an ID or use 'primary'
                # Note: Zoho API uses actual hex IDs usually.
                continue
            
            try:
                # Fetch events for the next 24 hours
                # Zoho filter example: /calendars/{uid}/events
                # We need to filter by time. Zoho API documentation might require specific query params.
                # Assuming simple list first for integration.
                url = f"{self.base_url}/calendars/{cal_id}/events"
                params = {
                    "startdate": now.strftime("%Y-%m-%dT%H:%M:%SZ")
                }
                
                # Using run_in_executor for blocking requests call
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, 
                    lambda: requests.get(url, headers=headers, params=params))
                
                if response.status_code != 200:
                    logger.error(f"Zoho Calendar API error: {response.status_code} {response.text}")
                    continue
                
                events_data = response.json()
                events = events_data.get('events', [])
                
                for event in events:
                    summary = event.get('title', '').lower() # Zoho uses 'title'
                    # Zoho uses 'start' and 'end' as dictionaries
                    start_info = event.get('start', {})
                    end_info = event.get('end', {})
                    
                    start_str = start_info.get('date_time') or start_info.get('date')
                    end_str = end_info.get('date_time') or end_info.get('date')
                    
                    if not start_str or not end_str:
                        continue

                    # Logic to identify Rest or Class sessions
                    if any(kw in summary for kw in ["rest", "sleep", "class", "study", "homework"]):
                        # Parse time (Zoho format might vary, usually ISO-ish)
                        try:
                            # Handle potential Z or timezone offsets
                            end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                            
                            if end_time > now:
                                logger.info(f"Scheduled rest for {child['name']} until {end_time} based on: {summary}")
                                self.scheduler.schedule_child_rest(child['name'], [], end_time)
                        except Exception as parse_err:
                            logger.error(f"Failed to parse Zoho event time: {end_str}, error: {parse_err}")
                        
            except Exception as e:
                logger.error(f"Error syncing Zoho cal {cal_id} for {child['name']}: {e}")

    async def run_loop(self):
        logger.info("Starting Zoho Calendar sync loop.")
        while True:
            await self.sync_now()
            await asyncio.sleep(900) # Sync every 15 mins
