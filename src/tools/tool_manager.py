"""Tool manager for handling MCP servers and tool execution."""
import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from src.tools.mcp_client import MCPClient

logger = logging.getLogger(__name__)


class ToolManager:
    """Manages MCP servers and tool execution."""

    def __init__(self):
        self.servers: dict[str, MCPClient] = {}
        self.internal_tools: dict[str, dict] = {}  # name -> {handler, definition}
        self._tool_index: dict[str, str] = {}  # tool_name -> server_name (for O(1) lookup)

    def register_internal_tool(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable[..., Awaitable[Any]]
    ):
        """Register an internal tool (not from MCP server)."""
        self.internal_tools[name] = {
            "handler": handler,
            "definition": {
                "name": name,
                "description": description,
                "inputSchema": parameters,
                "_server": "_internal"
            }
        }
        self._tool_index[name] = "_internal"

    async def load_config(self, config_path: str = "mcp_config.json"):
        """Load MCP server configuration and start servers."""
        config_file = Path(config_path)

        if not config_file.exists():
            logger.warning("MCP config not found: %s", config_path)
            return

        try:
            with open(config_file) as f:
                config = json.load(f)

            for server_name, server_config in config.items():
                command = server_config.get("command")
                args = server_config.get("args", [])

                if not command:
                    logger.warning("No command for MCP server: %s", server_name)
                    continue

                try:
                    client = MCPClient(command, args)
                    await client.start()
                    self.servers[server_name] = client
                    # Index all tools from this server for O(1) lookup
                    for tool in client.tools:
                        self._tool_index[tool["name"]] = server_name
                    logger.info("MCP server started: %s (%d tools)", server_name, len(client.tools))
                except Exception as e:
                    logger.error("Failed to start %s: %s", server_name, e)

        except Exception as e:
            logger.error("Failed to load MCP config: %s", e)

    def get_all_tools(self) -> list[dict]:
        """Get all tools from all servers and internal tools."""
        all_tools = []

        # MCP server tools
        for server_name, client in self.servers.items():
            for tool in client.get_tools():
                tool_with_server = tool.copy()
                tool_with_server["_server"] = server_name
                all_tools.append(tool_with_server)

        # Internal tools
        for tool_info in self.internal_tools.values():
            all_tools.append(tool_info["definition"])

        return all_tools

    def get_server_status(self) -> list[dict]:
        """Get status of all MCP servers."""
        status = []
        for server_name, client in self.servers.items():
            status.append({
                "name": server_name,
                "status": "active" if client.is_active() else "broken",
                "tools": len(client.tools)
            })
        return status

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call a tool by name across all servers and internal tools.

        Returns the tool result as a string. For MCP tools with multiple content
        blocks, all text content is joined with newlines.
        """
        # O(1) lookup using index
        server_name = self._tool_index.get(tool_name)

        if server_name is None:
            available = list(self._tool_index.keys())
            raise ValueError(f"Tool '{tool_name}' not found. Available tools: {available}")

        # Internal tool
        if server_name == "_internal":
            handler = self.internal_tools[tool_name]["handler"]
            result = await handler(**arguments)
            return json.dumps(result) if isinstance(result, dict) else str(result)

        # MCP server tool
        client = self.servers[server_name]
        content_blocks = await client.call_tool(tool_name, arguments)

        # Extract text from all content blocks
        texts = [block.get("text", "") for block in content_blocks if block.get("type") == "text"]
        return "\n".join(texts) if texts else ""

    def format_tool_call(self, tool_name: str, arguments: dict) -> str:
        """Format tool call for display (80 char limit)."""
        # Format as: ToolName arg1=val1 arg2=val2
        args_str = " ".join(f"{k}={v}" for k, v in arguments.items())
        full = f"{tool_name} {args_str}".strip()

        if len(full) <= 80:
            return full

        return full[:77] + "..."

    async def close_all(self):
        """Close all MCP server connections."""
        for client in self.servers.values():
            await client.close()
        self.servers.clear()
        # Keep internal tools in index, remove MCP tools
        self._tool_index = {k: v for k, v in self._tool_index.items() if v == "_internal"}
