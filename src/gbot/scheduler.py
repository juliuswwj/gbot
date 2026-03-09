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
            for child, data in list(self.active_sessions.items()):
                remaining = (data["end_time"] - now).total_seconds()

                if 0 < remaining <= 300 and not data["warned"]:
                    msg = f"⚠️ 提醒：{child} 的网络将在 5 分钟后断开，请准备休息。"
                    await self.chat.send_message(msg)
                    data["warned"] = True

                elif remaining <= 0:
                    logger.info(f"Time up for {child}. Blocking all devices...")
                    rules = []
                    for dev in data["devices"]:
                        # If we have MAC but not IP, we'd look it up via gmon tool
                        # Here assuming IP is available in the device dict
                        if "ip" in dev:
                            rules.append({"ip": dev["ip"], "action": "block", "reason": f"End of scheduled time for {child}"})
                    
                    if rules:
                        await self.gmon.call_tool("set_ip_forwarding", {"rules": rules})
                    
                    await self.chat.send_message(f"🚫 {child} 的时间到，网络已断开。")
                    del self.active_sessions[child]

            await asyncio.sleep(30)
