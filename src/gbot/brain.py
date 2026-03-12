import subprocess
import json
import logging
import os
import requests
import asyncio
import re
from datetime import datetime
from gbot.brain_prompt import STATIC_SYSTEM_PROMPT, DYNAMIC_SYSTEM_PROMPT
from gbot.tools import ToolHandler

logger = logging.getLogger(__name__)

class GeminiBrain:
    def __init__(self, config, socket_path=None):
        self.config = config
        self.scheduler = None # Will be set after initialization
        self.calendar = None  # Will be set after initialization
        self.gmon = None      # Will be set after initialization
        self.tools = ToolHandler(self, config)
        
        if socket_path is None:
            # Try ~/.gbot/gmon.sock first, fallback to /run/gbot/gmon.sock
            socket_path = os.path.expanduser("~/.gbot/gmon.sock")
            if not os.path.exists(socket_path):
                socket_path = "/run/gbot/gmon.sock"
        self.socket_path = socket_path
        
        # Configure Google AI Studio if API key is present
        self.api_key = config.gemini_api_key
        self.model_name = config.gemini_model

    def _get_family_info(self):
        """Format family member information for the prompt."""
        info = []
        for user in self.config.users:
            name = user.get("name", "Unknown")
            role = user.get("role", "Unknown")
            tags = ", ".join(user.get("tags", []))
            info.append(f"- {name} ({role}), Tags: [{tags}]")
        return "\n".join(info) if info else "No family information configured."

    def _get_memory_info(self):
        """Format stored facts for the prompt."""
        if not self.tools.memory:
            return "No long-term facts stored yet."
        return "\n".join([f"- {fact}" for f in self.tools.memory])

    def _get_schedule_info(self):
        """Format active/upcoming sessions for the prompt."""
        if not self.scheduler or not self.scheduler.active_sessions:
            return "No active rest or study sessions currently scheduled."
        
        info = []
        now = datetime.now()
        for child, data in self.scheduler.active_sessions.items():
            end_time = data["end_time"]
            remaining = end_time - now
            mins = int(remaining.total_seconds() / 60)
            if mins > 0:
                info.append(f"- {child}: Active session until {end_time.strftime('%H:%M')} ({mins} mins remaining).")
            else:
                info.append(f"- {child}: Session ending now.")
        return "\n".join(info)

    async def query(self, user_input, language="zh_cn", timezone=None, history=None):
        """Invoke Gemini via API first, fallback to gemini-cli. Use loop for tool calling."""
        
        family_info = self._get_family_info()
        history_info = history if history else "No recent history."
        
        # Determine current time based on provided timezone
        now = datetime.now()
        tz_name = "System Local"
        if timezone:
            try:
                import pytz
                user_tz = pytz.timezone(timezone)
                now = datetime.now(user_tz)
                tz_name = timezone
            except Exception as e:
                logger.warning(f"Failed to use timezone {timezone}: {e}")
        
        current_time_str = f"{now.strftime('%Y-%m-%d %A %H:%M:%S')} ({tz_name})"
        
        # STATIC part of prompt: calculated once
        static_prompt = STATIC_SYSTEM_PROMPT.format(
            current_time=current_time_str,
            family_info=family_info,
            history_info=history_info
        )
        
        current_user_input = user_input
        iteration = 0
        max_iterations = 3

        while iteration <= max_iterations:
            # DYNAMIC part of prompt: may change after tool calls
            schedule_info = self._get_schedule_info()
            memory_info = self._get_memory_info()
            
            dynamic_prompt = DYNAMIC_SYSTEM_PROMPT.format(
                schedule_info=schedule_info,
                memory_info=memory_info
            )
            
            system_prompt = static_prompt + dynamic_prompt
            full_prompt = f"{system_prompt}\n\n[IMPORTANT] Response Language: {language}\n\nUser Message: {current_user_input}"
            
            # 1. Try Google AI Studio API via requests
            response_text = ""
            if self.api_key:
                try:
                    loop = asyncio.get_event_loop()
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
                    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
                    
                    def _call_api():
                        resp = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
                        resp.raise_for_status()
                        return resp.json()

                    result = await loop.run_in_executor(None, _call_api)
                    if "candidates" in result and result["candidates"]:
                        response_text = result["candidates"][0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                except Exception as e:
                    logger.warning(f"Google AI Studio API failed: {e}")

            # 2. Fallback to gemini-cli
            if not response_text:
                try:
                    process = subprocess.run(
                        ["gemini", "--approval-mode", "plan", "-p", full_prompt],
                        capture_output=True, text=True, env=os.environ
                    )
                    if process.returncode == 0:
                        response_text = process.stdout.strip()
                    else:
                        return f"Error: Brain is currently offline. ({process.stderr})"
                except Exception as e:
                    return f"Error: Failed to connect to the brain: {e}"

            # 3. Check for TOOL_CALL
            if "TOOL_CALL:" in response_text:
                self.tools.calendar = self.calendar
                self.tools.gmon = self.gmon
                
                res = await self.tools.handle_tool_call(response_text)
                if res:
                    tool_name, tool_result = res
                    logger.info(f"Tool {tool_name} executed in loop (iteration {iteration}). Result: {tool_result}")
                    
                    # Prepare input for next iteration
                    current_user_input = f"{user_input}\n\n[TOOL RESULT: {tool_name}]\n{tool_result}"
                    iteration += 1
                    continue # Loop back for next response
            
            # If no tool call or parsing failed, return final response
            return response_text

        return "Error: Maximum tool-calling iterations reached."
