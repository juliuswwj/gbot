import json
import logging
import re
import os
import asyncio
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

class ToolHandler:
    def __init__(self, brain, config, calendar=None, gmon=None):
        self.brain = brain
        self.config = config
        self.calendar = calendar
        self.gmon = gmon
        self.memory_path = os.path.join(config.home_dir, "memory.json")
        self.memory = self._load_memory()

    async def handle_tool_call(self, response_text):
        """Parse and execute tool calls from LLM response.
        Returns: (tool_name, tool_result) if a call was processed, else None.
        """
        # Match TOOL_CALL: tool_name(arg1="val1", arg2=...)
        match = re.search(r"TOOL_CALL:\s*(\w+)\((.*)\)", response_text)
        if not match:
            return None

        tool_name = match.group(1)
        args_str = match.group(2)
        
        # Robust multi-argument parser
        args = {}
        for arg_match in re.finditer(r'(\w+)\s*=\s*(?:["\']([^"\']*)["\']|(\[.*?\]|\{.*?\}))', args_str):
            key = arg_match.group(1)
            val = arg_match.group(2) or arg_match.group(3)
            if val:
                try:
                    if val.startswith(("[", "{")):
                        args[key] = json.loads(val.replace("'", '"'))
                    else:
                        args[key] = val
                except Exception:
                    args[key] = val
        
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
                    tool_result = "Error: Calendar system not initialized."
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
            
            elif self.gmon:
                try:
                    mcp_res = await self.gmon.call_tool(tool_name, args)
                    tool_result = mcp_res.content[0].text if mcp_res.content else "Success (no output)"
                except Exception as ge:
                    tool_result = f"Error calling gmon tool {tool_name}: {ge}"
            else:
                tool_result = f"Error: Tool {tool_name} not supported."
        
        except Exception as te:
            logger.error(f"Tool {tool_name} execution error: {te}")
            tool_result = f"Error executing tool {tool_name}: {te}"
        
        return tool_name, tool_result

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
            compressed_json = await self.brain.query(prompt, language="en")
            
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

    async def _web_search(self, query):
        """Perform a simple web search."""
        logger.info(f"gbot performing web search for: {query}")
        try:
            url = f"https://duckduckgo.com/html/?q={query}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
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
            
            return "\n".join(formatted) if formatted else "No results found."
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return f"Error during web search: {str(e)}"
