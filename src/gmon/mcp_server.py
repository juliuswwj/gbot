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
        Tool(name="ping", description="Verify connection", 
             inputSchema={"type":"object", "properties":{"message":{"type":"string"}}}),
        
        Tool(name="get_host_info", description="Get Host info/Tags from dnsmasq configuration.", 
             inputSchema={"type":"object"}),
        
        Tool(name="update_dnsmasq_host", 
             description="Add or update a host in dnsmasq.conf, setting a tag (e.g. 'xiaoming') to associate it with a child.",
             inputSchema={
                "type": "object",
                "properties": {
                    "mac": {"type": "string"},
                    "ip": {"type": "string"},
                    "name": {"type": "string"},
                    "tag": {"type": "string", "description": "The user tag, e.g., 'xiaoming'"}
                },
                "required": ["mac", "ip", "name"]
             }),

        Tool(name="get_host_activity", description="Get current traffic summary for a specific host.", 
             inputSchema={"type":"object", "properties":{"host_name":{"type":"string"}}, "required":["host_name"]}),
        
        Tool(name="set_ip_forwarding", description="Block or allow internet for specific IPs (full or gaming modes).", 
             inputSchema={
                "type":"object", 
                "properties":{
                    "rules": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ip": {"type": "string"},
                                "action": {"type": "string", "enum": ["block", "allow"]},
                                "mode": {"type": "string", "enum": ["full", "gaming"]}
                            },
                            "required": ["ip", "action"]
                        }
                    }
                }, 
                "required":["rules"]
             }),
        
        Tool(name="get_history_report", description="Get historic aggregated traffic report for a specific date (YYYY-MM-DD).", 
             inputSchema={"type":"object", "properties":{"date":{"type":"string"}}, "required":["date"]}),
        
        Tool(name="save_behavior_category", description="Persistently save the classification of a domain (e.g., 'gaming', 'study').", 
             inputSchema={
                "type":"object", 
                "properties":{
                    "domain":{"type":"string"}, 
                    "category":{"type":"string"}
                }, 
                "required":["domain", "category"]
             }),
        
        Tool(name="get_behavior_map", description="Get all learned domain categories from the behavior database.", 
             inputSchema={"type":"object"})
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "ping":
            return [TextContent(type="text", text=f"pong: {arguments.get('message', 'none')}")]
        
        elif name == "get_host_info":
            return [TextContent(type="text", text=json.dumps(dnsmasq.get_hosts(), indent=2))]
        
        elif name == "update_dnsmasq_host":
            dnsmasq.update_host(arguments["mac"], arguments["ip"], arguments["name"], arguments.get("tag"))
            return [TextContent(type="text", text=f"Host {arguments['name']} updated in dnsmasq.")]
            
        elif name == "get_host_activity":
            return [TextContent(type="text", text=json.dumps(aggregator.get_summary(arguments.get("host_name")), indent=2))]
            
        elif name == "set_ip_forwarding":
            firewall.set_forwarding(arguments["rules"])
            return [TextContent(type="text", text="Firewall rules successfully applied.")]
            
        elif name == "get_history_report":
            target_date = arguments.get("date")
            if target_date == "today": target_date = str(date.today())
            return [TextContent(type="text", text=json.dumps(history_db.get_report(target_date), indent=2))]
            
        elif name == "save_behavior_category":
            behavior_db.save_behavior(arguments["domain"], arguments["category"])
            return [TextContent(type="text", text=f"Learned domain {arguments['domain']} as {arguments['category']}.")]
            
        elif name == "get_behavior_map":
            return [TextContent(type="text", text=json.dumps(behavior_db.get_all(), indent=2))]
            
        raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        logger.error(f"Tool execution failed ({name}): {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def background_flusher():
    """Periodically flush memory stats and clean up old history."""
    last_cleanup_day = None
    while True:
        await asyncio.sleep(3600) # Every hour
        today = date.today()
        
        if last_cleanup_day != today:
            logger.info("Executing daily history cleanup...")
            history_db.cleanup()
            last_cleanup_day = today
            
        logger.info("Flushing memory stats to history DB...")
        # Note: Aggregation flush logic should be implemented here in production

async def main():
    aggregator.update_host_map()
    logger.info("gmon MCP Server starting (stdio mode)...")
    asyncio.create_task(background_flusher())
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
