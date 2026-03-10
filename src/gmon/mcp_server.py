import asyncio
import os
import json
import logging
from datetime import date
from mcp.server import Server
from src.gmon.aggregator import TrafficAggregator
from src.gmon.network_ops import DnsmasqManager, FirewallManager
from src.gmon.behavior_db import BehaviorDB
from src.gmon.history_db import HistoryDB
from mcp.types import Tool, TextContent

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - gmon - %(message)s')
logger = logging.getLogger("gmon")

app = Server("gmon")
aggregator = TrafficAggregator()
dnsmasq = DnsmasqManager()
firewall = FirewallManager()
behavior_db = BehaviorDB()
history_db = HistoryDB()

# --- Tools Definition (Same as before) ---
@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="ping", description="Verify connection", inputSchema={"type":"object", "properties":{"message":{"type":"string"}}}),
        Tool(name="get_host_info", description="Get Host info/Tags", inputSchema={"type":"object"}),
        Tool(name="update_dnsmasq_host", description="Update host tag in dnsmasq", 
             inputSchema={"type":"object", "properties":{"mac":{"type":"string"},"ip":{"type":"string"},"name":{"type":"string"},"tag":{"type":"string"}},"required":["mac","ip","name"]}),
        Tool(name="get_host_activity", description="Current activity", inputSchema={"type":"object", "properties":{"host_name":{"type":"string"}},"required":["host_name"]}),
        Tool(name="set_ip_forwarding", description="Control internet access", inputSchema={"type":"object", "properties":{"rules":{"type":"array"}},"required":["rules"]}),
        Tool(name="get_history_report", description="History report", inputSchema={"type":"object", "properties":{"date":{"type":"string"}},"required":["date"]}),
        Tool(name="save_behavior_category", description="Save behavior", inputSchema={"type":"object", "properties":{"domain":{"type":"string"},"category":{"type":"string"}},"required":["domain","category"]}),
        Tool(name="get_behavior_map", description="Get behavior map", inputSchema={"type":"object"})
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "ping": return [TextContent(type="text", text=f"pong: {arguments.get('message', 'none')}")]
        elif name == "get_host_info": return [TextContent(type="text", text=json.dumps(dnsmasq.get_hosts(), indent=2))]
        elif name == "update_dnsmasq_host": 
            dnsmasq.update_host(arguments["mac"], arguments["ip"], arguments["name"], arguments.get("tag"))
            return [TextContent(type="text", text="Updated.")]
        elif name == "get_host_activity": return [TextContent(type="text", text=json.dumps(aggregator.get_summary(arguments.get("host_name")), indent=2))]
        elif name == "set_ip_forwarding": 
            firewall.set_forwarding(arguments["rules"])
            return [TextContent(type="text", text="Applied.")]
        elif name == "get_history_report":
            t_date = arguments.get("date")
            if t_date == "today": t_date = str(date.today())
            return [TextContent(type="text", text=json.dumps(history_db.get_report(t_date), indent=2))]
        elif name == "save_behavior_category":
            behavior_db.save_behavior(arguments["domain"], arguments["category"])
            return [TextContent(type="text", text="Saved.")]
        elif name == "get_behavior_map": return [TextContent(type="text", text=json.dumps(behavior_db.get_all(), indent=2))]
        raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

# --- Unix Socket Server Logic ---
async def handle_unix_client(reader, writer):
    """Bridge Unix Socket to MCP Server."""
    logger.info("New client connected via Unix Socket")
    await app.run(reader, writer, app.create_initialization_options())
    writer.close()
    await writer.wait_closed()
    logger.info("Client disconnected")

async def main():
    socket_path = "/run/gbot/gmon.sock"
    os.makedirs(os.path.dirname(socket_path), exist_ok=True)
    if os.path.exists(socket_path):
        os.remove(socket_path)

    aggregator.update_host_map()
    server = await asyncio.start_unix_server(handle_unix_client, path=socket_path)
    
    # Set socket permissions so gbot (user) can read/write
    os.chmod(socket_path, 0o666)
    
    logger.info(f"gmon MCP Server listening on {socket_path}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
