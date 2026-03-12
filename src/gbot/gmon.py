import asyncio
import os
import contextlib
from mcp.client.session import ClientSession

class GmonClient:
    def __init__(self, socket_path=None):
        if socket_path is None:
            socket_path = os.path.expanduser("~/.gbot/gmon.sock")
            if not os.path.exists(socket_path):
                socket_path = "/run/gbot/gmon.sock"
        self.socket_path = socket_path
        self._session = None
        self._exit_stack = None

    async def connect(self):
        """Connect to the gmon MCP Server via Unix Domain Socket."""
        self._exit_stack = contextlib.AsyncExitStack()
        
        # Connect to the unix socket
        reader, writer = await asyncio.open_unix_connection(self.socket_path)
        
        # Initialize session
        self._session = await self._exit_stack.enter_async_context(ClientSession(reader, writer))
        await self._session.initialize()
        return self._session

    async def call_tool(self, tool_name: str, arguments: dict):
        if not self._session:
            raise RuntimeError("Client not connected")
        return await self._session.call_tool(tool_name, arguments)

    async def call_ping(self, message: str):
        result = await self.call_tool("ping", {"message": message})
        return result.content[0].text

    async def disconnect(self):
        if self._exit_stack:
            await self._exit_stack.aclose()
