import subprocess
import json
import logging
import os
from src.gbot.brain_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class GeminiBrain:
    def __init__(self, socket_path="/run/gbot/gmon.sock"):
        self.socket_path = socket_path

    async def query(self, user_input):
        """Invoke gemini-cli with MCP server configuration."""
        # Define the MCP server for gemini-cli to connect to
        mcp_config = {
            "mcpServers": {
                "gmon": {
                    "command": "mcp-proxy", # We use a helper or direct socket if gemini-cli supports it
                    "args": [self.socket_path]
                }
            }
        }
        
        # For simplicity in this implementation, we'll use gemini-cli's stdio mcp 
        # By telling gemini-cli to run a command that connects to our socket.
        # But the standard way is to use a config file.
        
        try:
            # Prepare the prompt
            full_prompt = f"{SYSTEM_PROMPT}\n\nUser Message: {user_input}"
            
            # Call gemini-cli
            process = subprocess.run(
                ["gemini", "ask", full_prompt],
                capture_output=True,
                text=True,
                env=os.environ
            )
            
            if process.returncode != 0:
                logger.error(f"Gemini-CLI error: {process.stderr}")
                return f"Error: Brain is currently offline. ({process.stderr})"
            
            return process.stdout.strip()
        except Exception as e:
            logger.error(f"Failed to invoke Gemini: {e}")
            return "Error: Failed to connect to the brain."
