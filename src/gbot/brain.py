import subprocess
import json
import logging
import os
import requests
from gbot.brain_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class GeminiBrain:
    def __init__(self, config, socket_path=None):
        self.config = config
        if socket_path is None:
            # Try ~/.gbot/gmon.sock first, fallback to /run/gbot/gmon.sock
            socket_path = os.path.expanduser("~/.gbot/gmon.sock")
            if not os.path.exists(socket_path):
                socket_path = "/run/gbot/gmon.sock"
        self.socket_path = socket_path
        
        # Configure Google AI Studio if API key is present
        self.api_key = config.gemini_api_key
        self.model_name = config.gemini_model

    async def query(self, user_input, language="zh_cn"):
        """Invoke Gemini via API first, fallback to gemini-cli."""
        full_prompt = f"{SYSTEM_PROMPT}\n\n[IMPORTANT] Response Language: {language}\n\nUser Message: {user_input}"
        
        # 1. Try Google AI Studio API via requests
        if self.api_key:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{
                        "parts": [{"text": full_prompt}]
                    }]
                }
                
                def _call_api():
                    headers = {'Content-Type': 'application/json'}
                    resp = requests.post(url, json=payload, headers=headers, timeout=30)
                    resp.raise_for_status()
                    return resp.json()

                result = await loop.run_in_executor(None, _call_api)
                
                # Parse response: candidates[0].content.parts[0].text
                if "candidates" in result and result["candidates"]:
                    text = result["candidates"][0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if text:
                        logger.info("Successfully used Google AI Studio API via requests.")
                        return text.strip()
                
                logger.warning(f"Unexpected API response format: {result}")
            except Exception as e:
                logger.warning(f"Google AI Studio API (requests) failed, falling back to CLI: {e}")

        # 2. Fallback to gemini-cli
        try:
            # Call gemini-cli in non-interactive mode (-p)
            process = subprocess.run(
                ["gemini", "--approval-mode", "plan", "-p", full_prompt],
                capture_output=True,
                text=True,
                env=os.environ
            )
            
            if process.returncode != 0:
                logger.error(f"Gemini-CLI error: {process.stderr}")
                return f"Error: Brain is currently offline. ({process.stderr})"
            
            return process.stdout.strip()
        except Exception as e:
            logger.error(f"Failed to invoke Gemini CLI: {e}")
            return "Error: Failed to connect to the brain."
