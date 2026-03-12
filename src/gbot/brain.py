import subprocess
import json
import logging
import os
import requests
import asyncio
import re
from datetime import datetime
from gbot.brain_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class GeminiBrain:
    def __init__(self, config, socket_path=None):
        self.config = config
        self.scheduler = None # Will be set after initialization
        self.calendar = None  # Will be set after initialization
        self.gmon = None      # Will be set after initialization
        self.memory_path = os.path.join(config.home_dir, "memory.json")
        self.memory = self._load_memory()
        
        if socket_path is None:
            # Try ~/.gbot/gmon.sock first, fallback to /run/gbot/gmon.sock
            socket_path = os.path.expanduser("~/.gbot/gmon.sock")
            if not os.path.exists(socket_path):
                socket_path = "/run/gbot/gmon.sock"
        self.socket_path = socket_path
        
        # Configure Google AI Studio if API key is present
        self.api_key = config.gemini_api_key
        self.model_name = config.gemini_model

    def _load_memory(self):
        """Load long-term facts from memory.json."""
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load memory: {e}")
        return []

    def _save_memory(self):
        """Persist memory to disk."""
        try:
            with open(self.memory_path, 'w') as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")

    def add_memory(self, fact):
        """Add a new fact to long-term memory."""
        if fact not in self.memory:
            self.memory.append(fact)
            self._save_memory()
            
            # Compress memory if it grows too large (e.g., > 20 items)
            if len(self.memory) > 20:
                asyncio.create_task(self._compress_memory())
            return True
        return False

    async def _compress_memory(self):
        """Use LLM to compress and deduplicate long-term memory."""
        logger.info("Compressing long-term memory...")
        try:
            current_mem = "\n".join([f"- {f}" for f in self.memory])
            prompt = (
                f"Please summarize and deduplicate the following list of household facts. "
                f"Merge related information and keep only the most important context. "
                f"Return ONLY a JSON list of strings (e.g., [\"fact1\", \"fact2\"]):\n{current_mem}"
            )
            
            # Use a simple query for compression to avoid full system prompt
            compressed_json = await self.query(prompt, language="en")
            
            # Basic cleanup of LLM output to extract JSON
            if "```json" in compressed_json:
                compressed_json = compressed_json.split("```json")[1].split("```")[0].strip()
            elif "```" in compressed_json:
                compressed_json = compressed_json.split("```")[1].split("```")[0].strip()
            
            new_memory = json.loads(compressed_json)
            if isinstance(new_memory, list):
                self.memory = new_memory
                self._save_memory()
                logger.info(f"Memory compressed to {len(self.memory)} items.")
        except Exception as e:
            logger.error(f"Failed to compress memory: {e}")

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
        if not self.memory:
            return "No long-term facts stored yet."
        return "\n".join([f"- {fact}" for fact in self.memory])

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

    async def _web_search(self, query):
        """Perform a simple web search (using DuckDuckGo HTML as fallback)."""
        logger.info(f"gbot performing web search for: {query}")
        try:
            # Simple DDG HTML search
            url = f"https://duckduckgo.com/html/?q={query}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            import asyncio
            loop = asyncio.get_event_loop()
            def _get():
                return requests.get(url, headers=headers, timeout=10)
            
            resp = await loop.run_in_executor(None, _get)
            resp.raise_for_status()
            
            from re import findall
            results = findall(r'<a class="result__a" rel="noopener" href="([^"]+)">([^<]+)</a>', resp.text)
            
            formatted = []
            for link, title in results[:5]:
                formatted.append(f"- {title.strip()}: {link}")
            
            if not formatted:
                return "No results found."
            return "\n".join(formatted)
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return f"Error during web search: {str(e)}"

    async def query(self, user_input, language="zh_cn", timezone=None, history=None, depth=0):
        """Invoke Gemini via API first, fallback to gemini-cli."""
        if depth > 3: # Prevent infinite recursion
            return "Error: Maximum tool-calling depth reached."

        family_info = self._get_family_info()
        schedule_info = self._get_schedule_info()
        memory_info = self._get_memory_info()
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
        
        system_prompt = SYSTEM_PROMPT.format(
            current_time=current_time_str,
            family_info=family_info,
            schedule_info=schedule_info,
            memory_info=memory_info,
            history_info=history_info
        )
        
        full_prompt = f"{system_prompt}\n\n[IMPORTANT] Response Language: {language}\n\nUser Message: {user_input}"
        
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

        # 3. Handle internal tool calls
        if "TOOL_CALL:" in response_text:
            logger.info(f"Brain detected potential tool call: {response_text}")
            # Match TOOL_CALL: add_memory(fact="...") or list_calendar_events(user_name="...", date="...")
            match = re.search(r"TOOL_CALL:\s*(\w+)\((.*)\)", response_text)
            if match:
                tool_name = match.group(1)
                args_str = match.group(2)
                
                # Robust multi-argument parser
                args = {}
                # Try to extract key="value" or key=JSON
                for arg_match in re.finditer(r'(\w+)\s*=\s*(?:["\']([^"\']*)["\']|(\[.*?\]|\{.*?\}))', args_str):
                    key = arg_match.group(1)
                    val = arg_match.group(2) or arg_match.group(3)
                    if val:
                        try:
                            # If it looks like JSON, parse it
                            if val.startswith(("[", "{")):
                                args[key] = json.loads(val.replace("'", '"'))
                            else:
                                args[key] = val
                        except Exception:
                            args[key] = val
                
                # Identify and execute tool
                tool_result = f"Error: Tool {tool_name} not found or failed."
                
                try:
                    if tool_name == "add_memory":
                        fact = args.get("fact")
                        if fact:
                            self.add_memory(fact)
                            tool_result = f"Stored fact in memory: {fact}"
                        else:
                            tool_result = "Error: 'fact' argument missing for add_memory."
                    elif tool_name == "google_web_search":
                        query = args.get("query")
                        if query: 
                            tool_result = await self._web_search(query)
                        else:
                            tool_result = "Error: 'query' argument missing for google_web_search."
                    elif tool_name in ["list_calendar_events", "add_calendar_event", "update_calendar_event", "delete_calendar_event"]:
                        if not self.calendar:
                            tool_result = "Error: Calendar system not initialized in brain."
                        else:
                            user_name = args.get("user_name")
                            if not user_name:
                                tool_result = f"Error: 'user_name' argument missing for {tool_name}."
                            elif tool_name == "list_calendar_events":
                                tool_result = await self.calendar.list_events(user_name, args.get("date"))
                            elif tool_name == "add_calendar_event":
                                tool_result = await self.calendar.add_event(
                                    user_name, args.get("title"), args.get("start_time"), 
                                    args.get("end_time"), args.get("description")
                                )
                            elif tool_name == "update_calendar_event":
                                tool_result = await self.calendar.update_event(
                                    user_name, args.get("event_id"), args.get("title"), 
                                    args.get("start_time"), args.get("end_time")
                                )
                            elif tool_name == "delete_calendar_event":
                                tool_result = await self.calendar.delete_event(user_name, args.get("event_id"))
                            
                            logger.info(f"Calendar tool {tool_name} for {user_name} returned: {tool_result}")
                    elif self.gmon:
                        # Fallback to gmon tools
                        try:
                            mcp_res = await self.gmon.call_tool(tool_name, args)
                            tool_result = mcp_res.content[0].text if mcp_res.content else "Success (no output)"
                        except Exception as ge:
                            tool_result = f"Error calling gmon tool {tool_name}: {ge}"
                    else:
                        tool_result = f"Error: Tool {tool_name} not supported and no backend (gmon/calendar) available."
                except Exception as te:
                    logger.error(f"Tool {tool_name} execution error: {te}")
                    tool_result = f"Error executing tool {tool_name}: {te}"
                
                # Final safety check: if tool_result is somehow still None or empty
                if tool_result is None:
                    tool_result = f"Error: Tool {tool_name} returned no data."
                
                logger.info(f"Tool {tool_name} result: {tool_result}")
                # Recurse with tool result to let LLM provide final answer
                new_input = f"{user_input}\n\n[TOOL RESULT: {tool_name}]\n{tool_result}"
                return await self.query(new_input, language=language, timezone=timezone, history=history, depth=depth+1)
            else:
                logger.warning(f"Failed to parse TOOL_CALL from response: {response_text}")

        return response_text
