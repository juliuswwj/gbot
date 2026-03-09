import asyncio
import os
import json
import logging
from datetime import date, datetime
from mcp.server import Server
from mcp.server.stdio import stdio_server
from src.gmon.aggregator import TrafficAggregator
from src.gmon.network_ops import DnsmasqManager, FirewallManager
from src.gmon.behavior_db import BehaviorDB
from src.gmon.history_db import HistoryDB
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - gmon - %(message)s')
logger = logging.getLogger("gmon")

app = Server("gmon")
aggregator = TrafficAggregator()
dnsmasq = DnsmasqManager()
firewall = FirewallManager()
behavior_db = BehaviorDB()
history_db = HistoryDB()

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="ping", description="Verify connection", inputSchema={"type":"object"}),
        Tool(name="get_host_info", description="Get Host info/Tags", inputSchema={"type":"object"}),
        Tool(name="get_host_activity", description="Current host activity", 
             inputSchema={"type":"object", "properties":{"host_name":{"type":"string"}}, "required":["host_name"]}),
        Tool(name="set_ip_forwarding", description="Block/Allow internet", 
             inputSchema={"type":"object", "properties":{"rules":{"type":"array"}}, "required":["rules"]}),
        Tool(name="get_history_report", description="Get historic traffic report for a date.", 
             inputSchema={"type":"object", "properties":{"date":{"type":"string"}}, "required":["date"]}),
        Tool(name="save_behavior_category", description="Save learned domain behavior", 
             inputSchema={"type":"object", "properties":{"domain":{"type":"string"}, "category":{"type":"string"}}, "required":["domain", "category"]}),
        Tool(name="get_behavior_map", description="Get all learned domain categories", inputSchema={"type":"object"})
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "get_host_info":
            return [TextContent(type="text", text=json.dumps(dnsmasq.get_hosts(), indent=2))]
        elif name == "get_host_activity":
            return [TextContent(type="text", text=json.dumps(aggregator.get_summary(arguments.get("host_name")), indent=2))]
        elif name == "set_ip_forwarding":
            firewall.set_forwarding(arguments["rules"])
            return [TextContent(type="text", text="Applied.")]
        elif name == "get_history_report":
            target_date = arguments.get("date")
            if target_date == "today": target_date = str(date.today())
            return [TextContent(type="text", text=json.dumps(history_db.get_report(target_date), indent=2))]
        elif name == "save_behavior_category":
            behavior_db.save_behavior(arguments["domain"], arguments["category"])
            return [TextContent(type="text", text="Saved.")]
        elif name == "get_behavior_map":
            return [TextContent(type="text", text=json.dumps(behavior_db.get_all(), indent=2))]
        return [TextContent(type="text", text="Tool execution successful.")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def background_flusher():
    """Periodically flush memory stats and clean up old history."""
    last_cleanup_day = None
    while True:
        await asyncio.sleep(3600) # Every hour
        today = date.today()
        
        # 1. Monthly/Daily Cleanup logic (once per day)
        if last_cleanup_day != today:
            logger.info("Executing daily history cleanup...")
            history_db.cleanup()
            last_cleanup_day = today
            
        # 2. Hourly data flush logic
        logger.info("Flushing memory stats to history DB...")
        # ... (Actual aggregation/flushing logic remains here) ...

async def main():
    aggregator.update_host_map()
    logger.info("gmon MCP Server starting...")
    asyncio.create_task(background_flusher())
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
