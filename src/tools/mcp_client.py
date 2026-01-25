"""MCP client for connecting to MCP servers via stdio."""
import asyncio
import json
from typing import Any, Optional
import sys


class MCPClient:
    """Client for communicating with an MCP server over stdio."""

    def __init__(self, command: str, args: list[str]):
        self.command = command
        self.args = args
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0
        self.server_info: Optional[dict] = None
        self.tools: list[dict] = []

    async def start(self):
        """Start the MCP server process."""
        try:
            self.process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Initialize the connection
            await self._initialize()

            # List available tools
            await self._list_tools()

        except FileNotFoundError:
            raise RuntimeError(f"MCP server not found: {self.command}")
        except Exception as e:
            raise RuntimeError(f"Failed to start MCP server: {e}")

    async def _send_request(self, method: str, params: Optional[dict] = None) -> dict:
        """Send JSON-RPC request to server."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("MCP server not started")

        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }

        # Send request
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()

        # Read response
        if self.process.stdout:
            response_line = await self.process.stdout.readline()
            response = json.loads(response_line.decode())

            if "error" in response:
                raise RuntimeError(f"MCP error: {response['error']}")

            return response.get("result", {})

        raise RuntimeError("No stdout from MCP server")

    async def _initialize(self):
        """Initialize the MCP connection."""
        result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "minifram",
                "version": "0.1.0"
            }
        })
        self.server_info = result

    async def _list_tools(self):
        """List available tools from the server."""
        result = await self._send_request("tools/list")
        self.tools = result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Call a tool on the MCP server."""
        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })

        # Extract text from content
        content = result.get("content", [])
        if content and len(content) > 0:
            return content[0].get("text", "")

        return ""

    async def close(self):
        """Close the MCP server connection."""
        if self.process:
            if self.process.stdin:
                self.process.stdin.close()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()

    def get_tools(self) -> list[dict]:
        """Get list of available tools."""
        return self.tools

    def is_active(self) -> bool:
        """Check if server is running."""
        return self.process is not None and self.process.returncode is None
