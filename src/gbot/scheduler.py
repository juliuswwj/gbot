import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GbotScheduler:
    def __init__(self, gmon_client, chat_channel):
        self.gmon = gmon_client
        self.chat = chat_channel
        # { "child_name": {"end_time": datetime, "warned": bool, "devices": [{"mac": str, "ip": str}]} }
        self.active_sessions = {}

    def schedule_child_rest(self, child_name, devices, end_time):
        """Schedule rest time for a specific child and all their devices."""
        self.active_sessions[child_name] = {
            "devices": devices,
            "end_time": end_time,
            "warned": False
        }
        logger.info(f"Scheduled rest session for {child_name} until {end_time}")

    def extend_rest(self, child_name, minutes):
        """Add extra time for a child's session."""
        if child_name in self.active_sessions:
            self.active_sessions[child_name]["end_time"] += timedelta(minutes=minutes)
            self.active_sessions[child_name]["warned"] = False
            return True
        return False

    async def run_loop(self):
        while True:
            now = datetime.now()
            
            # 1. Midnight Daily Report Trigger
            if now.hour == 0 and now.minute == 0:
                logger.info("Midnight reached. Generating daily report...")
                yesterday = str((now - timedelta(days=1)).date())
                # Trigger brain to generate a human-readable report
                report_data = await self.gmon.call_tool("get_history_report", {"date": yesterday})
                msg = f"📊 小孩上网日报 ({yesterday}):\n{report_data.content[0].text}"
                await self.chat.send_message(msg)
                await asyncio.sleep(65) # Avoid double triggers

            # 2. Existing session monitoring ...
            for child, data in list(self.active_sessions.items()):
                # ... (previous logic)
