import asyncio
import os
import json
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
# Note: We'll use a custom Unix Socket transport for gmon
from src.gmon.aggregator import TrafficAggregator
from src.gmon.network_ops import DnsmasqManager, FirewallManager
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - gmon - %(message)s')
logger = logging.getLogger("gmon")

app = Server("gmon")
aggregator = TrafficAggregator()
dnsmasq = DnsmasqManager()
firewall = FirewallManager()

# ... (Previous tools registration remains the same) ...
from src.gmon.config_manager import ConfigManager

# ... (Previous initialization) ...
config_mgr = ConfigManager()

from src.gmon.behavior_db import BehaviorDB

# ... (Previous initialization) ...
behavior_db = BehaviorDB()

@app.list_tools()
async def list_tools():
    return [
        # ... (Existing tools) ...
        Tool(name="get_behavior_map", description="Return a map of domains to their learned categories.", 
             inputSchema={"type":"object"}),
        Tool(name="save_behavior_category", 
             description="Persistently save the classification of a domain (e.g. 'gaming', 'study').",
             inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "category": {"type": "string"}
                },
                "required": ["domain", "category"]
             })
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    # ... (Previous tool handling) ...
    if name == "get_behavior_map":
        return [TextContent(type="text", text=json.dumps(behavior_db.get_all()))]
    elif name == "save_behavior_category":
        behavior_db.save_behavior(arguments["domain"], arguments["category"])
        return [TextContent(type="text", text=f"Learned {arguments['domain']} as {arguments['category']}.")]
    return []

async def run_unix_server(path="/run/gbot/gmon.sock"):
    # Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    
    logger.info(f"Starting gmon MCP Server on {path}")
    
    # Simple Unix Socket logic - in production, use mcp.server.lowlevel.lowlevel_server
    # For now, we continue supporting stdio as a fallback or implement the socket listener
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(run_unix_server())
