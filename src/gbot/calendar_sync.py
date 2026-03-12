import asyncio
import logging
import requests
import json
from datetime import datetime, timezone, timedelta
from gbot.zoho_auth import ZohoAuth

logger = logging.getLogger(__name__)

class CalendarSync:
    def __init__(self, config, scheduler, auth=None):
        self.config = config
        self.scheduler = scheduler
        self.auth = auth or ZohoAuth(config)
        self.region = config.zoho.get("region", "com")
        self.base_url = f"https://calendar.zoho.{self.region}/api/v1"

    async def _make_request(self, method, url, params=None, data=None):
        """Helper to perform Zoho API requests."""
        access_token = self.auth.get_access_token()
        if not access_token:
            return "Error: Failed to obtain Zoho access token."

        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }

        loop = asyncio.get_event_loop()
        try:
            def _req():
                return requests.request(method, url, headers=headers, params=params, json=data, timeout=15)
            
            response = await loop.run_in_executor(None, _req)
            if response.status_code not in [200, 201, 204]:
                err_msg = f"Error: Zoho Calendar API {response.status_code} - {response.text}"
                logger.error(err_msg)
                return err_msg
            
            if response.status_code == 204:
                return {"status": "success"}
            
            try:
                return response.json()
            except Exception:
                return {"status": "success", "text": response.text}
        except Exception as e:
            err_msg = f"Error: Zoho Calendar request failed - {str(e)}"
            logger.error(err_msg)
            return err_msg

    def _get_calendar_id(self, user_name):
        """Find calendar_id for a user by name in config."""
        for u in self.config.users:
            if u.get("name").lower() == user_name.lower():
                return u.get("calendar_id")
        return None

    async def list_events(self, user_name, date_str=None):
        """List events for a user. date_str: YYYY-MM-DD."""
        cal_id = self._get_calendar_id(user_name)
        if not cal_id:
            return f"Error: No calendar found for user {user_name}"

        url = f"{self.base_url}/calendars/{cal_id}/events"
        
        # Zoho expects range={"start":"YYYYMMDD", "end":"YYYYMMDD"}
        if date_str:
            # Format: YYYYMMDD
            clean_date = date_str.replace("-", "")
            range_param = {"start": clean_date, "end": clean_date}
        else:
            # Default to next 7 days
            now = datetime.now()
            later = now + timedelta(days=7)
            range_param = {
                "start": now.strftime("%Y%m%d"),
                "end": later.strftime("%Y%m%d")
            }

        params = {"range": json.dumps(range_param)}

        result = await self._make_request("GET", url, params=params)
        if isinstance(result, str) and result.startswith("Error"):
            return result
        
        events = result.get("events", [])
        if not events:
            return f"No events found for {user_name} on {date_str if date_str else 'this week'}."
        
        formatted = []
        for e in events:
            eid = e.get("uid")
            title = e.get("title")
            start = e.get("start", {}).get("date_time", "N/A")
            end = e.get("end", {}).get("date_time", "N/A")
            formatted.append(f"- [{eid}] {title}: {start} to {end}")
        
        return "\n".join(formatted)

    async def add_event(self, user_name, title, start_time, end_time, description=None):
        """Add a new Zoho calendar event. times in ISO format (YYYY-MM-DDTHH:MM:SSZ)."""
        cal_id = self._get_calendar_id(user_name)
        if not cal_id:
            return f"Error: No calendar found for user {user_name}"

        url = f"{self.base_url}/calendars/{cal_id}/events"
        data = {
            "eventdata": {
                "title": title,
                "start": {"date_time": start_time},
                "end": {"date_time": end_time}
            }
        }
        if description:
            data["eventdata"]["description"] = description

        result = await self._make_request("POST", url, data=data)
        if isinstance(result, str) and result.startswith("Error"):
            return result
        return f"Successfully added event '{title}' for {user_name}."

    async def update_event(self, user_name, event_id, title=None, start_time=None, end_time=None):
        """Update an existing event."""
        cal_id = self._get_calendar_id(user_name)
        if not cal_id:
            return f"Error: No calendar found for user {user_name}"

        url = f"{self.base_url}/calendars/{cal_id}/events/{event_id}"
        event_data = {}
        if title: event_data["title"] = title
        if start_time: event_data["start"] = {"date_time": start_time}
        if end_time: event_data["end"] = {"date_time": end_time}

        if not event_data:
            return "No updates provided."

        result = await self._make_request("PUT", url, data={"eventdata": event_data})
        if isinstance(result, str) and result.startswith("Error"):
            return result
        return f"Successfully updated event {event_id} for {user_name}."

    async def delete_event(self, user_name, event_id):
        """Delete an event."""
        cal_id = self._get_calendar_id(user_name)
        if not cal_id:
            return f"Error: No calendar found for user {user_name}"

        url = f"{self.base_url}/calendars/{cal_id}/events/{event_id}"
        result = await self._make_request("DELETE", url)
        if isinstance(result, str) and result.startswith("Error"):
            return result
        return f"Successfully deleted event {event_id} for {user_name}."

    async def sync_now(self):
        """Sync Zoho Calendar events for all children (existing logic)."""
        now = datetime.now()
        later = now + timedelta(days=1)
        
        range_param = {
            "start": now.strftime("%Y%m%d"),
            "end": later.strftime("%Y%m%d")
        }
        params = {"range": json.dumps(range_param)}

        for child in self.config.get_children():
            cal_id = child.get("calendar_id")
            if not cal_id: continue
            
            url = f"{self.base_url}/calendars/{cal_id}/events"
            result = await self._make_request("GET", url, params=params)
            if not isinstance(result, dict): continue
                
            events = result.get('events', [])
            for event in events:
                summary = event.get('title', '').lower()
                start_info = event.get('start', {})
                end_info = event.get('end', {})
                
                start_str = start_info.get('date_time') or start_info.get('date')
                end_str = end_info.get('date_time') or end_info.get('date')
                
                if not start_str or not end_str: continue

                if any(kw in summary for kw in ["rest", "sleep", "class", "study", "homework"]):
                    try:
                        # end_time comparison uses naive now vs naive parsed
                        end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00')).replace(tzinfo=None)
                        if end_time > now:
                            logger.info(f"Scheduled rest for {child['name']} until {end_time} based on: {summary}")
                            self.scheduler.schedule_child_rest(child['name'], [], end_time)
                    except Exception as parse_err:
                        logger.error(f"Failed to parse Zoho event time: {end_str}, error: {parse_err}")

    async def run_loop(self):
        logger.info("Starting Zoho Calendar sync loop.")
        while True:
            await self.sync_now()
            await asyncio.sleep(900) # Sync every 15 mins

    async def mock_loop(self):
        """A no-op loop for test mode."""
        while True:
            await asyncio.sleep(3600)
