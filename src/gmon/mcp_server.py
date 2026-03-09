import asyncio
import os
import json
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from src.gmon.aggregator import TrafficAggregator
from src.gmon.network_ops import DnsmasqManager, FirewallManager
from src.gmon.behavior_db import BehaviorDB
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - gmon - %(message)s')
logger = logging.getLogger("gmon")

app = Server("gmon")
aggregator = TrafficAggregator()
dnsmasq = DnsmasqManager()
firewall = FirewallManager()
behavior_db = BehaviorDB()

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="ping", description="Verify connection", 
             inputSchema={"type":"object", "properties":{"message":{"type":"string"}}}),
        
        Tool(name="get_host_info", description="Get IP/MAC/Name and Tag from dnsmasq config.", 
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
        
        Tool(name="get_host_activity", description="Get traffic summary for a specific host.", 
             inputSchema={"type":"object", "properties":{"host_name":{"type":"string"}}, "required":["host_name"]}),
        
        Tool(name="set_ip_forwarding", description="Block or allow internet for specific IPs (full or gaming).", 
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
        
        Tool(name="get_behavior_map", description="Return a map of domains to their learned categories.", 
             inputSchema={"type":"object"}),
        
        Tool(name="save_behavior_category", description="Persistently save the classification of a domain.",
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
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "ping":
            return [TextContent(type="text", text=f"pong: {arguments.get('message', 'none')}")]
        
        elif name == "get_host_info":
            return [TextContent(type="text", text=json.dumps(dnsmasq.get_hosts(), indent=2))]
        
        elif name == "update_dnsmasq_host":
            dnsmasq.update_host(arguments["mac"], arguments["ip"], arguments["name"], arguments.get("tag"))
            return [TextContent(type="text", text="Dnsmasq configuration updated and reloaded.")]
        
        elif name == "get_host_activity":
            return [TextContent(type="text", text=json.dumps(aggregator.get_summary(arguments.get("host_name")), indent=2))]
        
        elif name == "set_ip_forwarding":
            firewall.set_forwarding(arguments["rules"])
            return [TextContent(type="text", text="Firewall rules applied.")]
        
        elif name == "get_behavior_map":
            return [TextContent(type="text", text=json.dumps(behavior_db.get_all(), indent=2))]
        
        elif name == "save_behavior_category":
            behavior_db.save_behavior(arguments["domain"], arguments["category"])
            return [TextContent(type="text", text="Behavior category saved.")]
            
        raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    aggregator.update_host_map()
    logger.info("gmon MCP Server starting (stdio mode)...")
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
