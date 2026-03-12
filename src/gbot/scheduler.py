import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GbotScheduler:
    def __init__(self, config, gmon_client, chat_channel):
        self.config = config
        self.gmon = gmon_client
        self.chat = chat_channel
        # { "child_name": {"end_time": datetime, "warned": bool, "devices": [{"mac": str, "ip": str}]} }
        self.active_sessions = {}

    def schedule_child_rest(self, child_name, devices, end_time):
        """Schedule rest time for a specific child and all their devices."""
        child_email = None
        # Always try to find the child's contact email and devices from config
        for child in self.config.get_children():
            if child.get("name") == child_name:
                child_email = child.get("contact")
                if not devices:
                    devices = child.get("devices", [])
                break
        
        self.active_sessions[child_name] = {
            "devices": devices,
            "end_time": end_time,
            "warned": False,
            "email": child_email
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
                try:
                    # Get raw data from gmon
                    report_data = await self.gmon.call_tool("get_history_report", {"date": yesterday})
                    raw_json = report_data.content[0].text
                    
                    # Use brain to generate a human-readable summary in the configured language
                    prompt = f"Please summarize this daily internet usage report for {yesterday}. Be concise and professional:\n{raw_json}"
                    msg = await self.chat.brain_callback(prompt, language=self.config.cron_chat_language)
                    
                    header = "📊 Daily Report" if self.config.cron_chat_language.startswith("en") else "📊 小孩上网日报"
                    await self.chat.send_message(f"{header} ({yesterday}):\n{msg}", recipient=self.config.cron_chat_id)
                except Exception as e:
                    logger.error(f"Failed to generate daily report: {e}")
                await asyncio.sleep(65) # Avoid double triggers

            # 2. Existing session monitoring
            for child, data in list(self.active_sessions.items()):
                end_time = data["end_time"]
                
                # Check if session ended
                if now >= end_time:
                    logger.info(f"Session ended for {child}. Blocking devices.")
                    rules = []
                    for dev in data["devices"]:
                        ip = dev.get("ip") if isinstance(dev, dict) else dev
                        if ip:
                            rules.append({"ip": ip, "action": "block", "mode": "full", "reason": "Rest time over"})
                    
                    if rules:
                        try:
                            await self.gmon.call_tool("set_ip_forwarding", {"rules": rules})
                            msg = f"🛑 {child} 的休息时间到了，网络已断开。"
                            await self.chat.send_message(msg, recipient=self.config.cron_chat_id)
                            if data.get("email"):
                                await self.chat.send_message(msg, recipient=data["email"])
                        except Exception as e:
                            logger.error(f"Failed to block devices for {child}: {e}")
                    
                    del self.active_sessions[child]
                
                # Check if warning needed (5 mins before)
                elif now >= end_time - timedelta(minutes=5) and not data["warned"]:
                    logger.info(f"Sending 5-minute warning for {child}")
                    msg = f"⚠️ 提示: {child}，还有 5 分钟休息。请尽快收尾！"
                    await self.chat.send_message(msg, recipient=self.config.cron_chat_id)
                    if data.get("email"):
                        await self.chat.send_message(msg, recipient=data["email"])
                    self.active_sessions[child]["warned"] = True
            
            await asyncio.sleep(30) # Check every 30 seconds
