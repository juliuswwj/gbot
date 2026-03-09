import asyncio
import subprocess
import sys
import contextlib
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

class GmonClient:
    def __init__(self, gmon_path=None):
        # In a real environment, this would be the path to gmon binary.
        # For development, we launch it as a python script.
        if gmon_path is None:
             self.params = StdioServerParameters(
                command=sys.executable,
                args=["src/gmon/mcp_server.py"],
                env=None
            )
        else:
            self.params = StdioServerParameters(
                command=gmon_path,
                args=[],
                env=None
            )
        self._session = None
        self._exit_stack = None

    async def connect(self):
        """Connect to the gmon MCP Server."""
        self._exit_stack = contextlib.AsyncExitStack()
        read_stream, write_stream = await self._exit_stack.enter_async_context(stdio_client(self.params))
        self._session = await self._exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self._session.initialize()
        return self._session

    async def call_ping(self, message: str):
        """Call the ping tool on gmon."""
        if not self._session:
            raise RuntimeError("Client not connected")
        result = await self._session.call_tool("ping", {"message": message})
        return result.content[0].text

    async def disconnect(self):
        """Disconnect and cleanup."""
        if self._exit_stack:
            await self._exit_stack.aclose()
