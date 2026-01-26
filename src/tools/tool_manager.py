"""Tool manager for handling MCP servers and tool execution."""
import json
from pathlib import Path
from typing import Any, Callable, Optional
from src.tools.mcp_client import MCPClient


class ToolManager:
    """Manages MCP servers and tool execution."""

    def __init__(self):
        self.servers: dict[str, MCPClient] = {}
        self.internal_tools: dict[str, dict] = {}  # name -> {handler, definition}

    def register_internal_tool(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable[..., Any]
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

    async def load_config(self, config_path: str = "mcp_config.json"):
        """Load MCP server configuration and start servers."""
        config_file = Path(config_path)

        if not config_file.exists():
            print(f"⚠️  MCP config not found: {config_path}")
            return

        try:
            with open(config_file) as f:
                config = json.load(f)

            for server_name, server_config in config.items():
                command = server_config.get("command")
                args = server_config.get("args", [])

                if not command:
                    print(f"⚠️  No command for MCP server: {server_name}")
                    continue

                try:
                    client = MCPClient(command, args)
                    await client.start()
                    self.servers[server_name] = client
                    print(f"✅ MCP server started: {server_name} ({len(client.tools)} tools)")
                except Exception as e:
                    print(f"❌ Failed to start {server_name}: {e}")

        except Exception as e:
            print(f"❌ Failed to load MCP config: {e}")

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
        """Call a tool by name across all servers and internal tools."""
        # Check internal tools first
        if tool_name in self.internal_tools:
            handler = self.internal_tools[tool_name]["handler"]
            result = await handler(**arguments)
            return json.dumps(result) if isinstance(result, dict) else str(result)

        # Find which MCP server has this tool
        for server_name, client in self.servers.items():
            for tool in client.tools:
                if tool["name"] == tool_name:
                    return await client.call_tool(tool_name, arguments)

        # Tool not found
        available = list(self.internal_tools.keys()) + [
            t["name"] for client in self.servers.values() for t in client.tools
        ]
        raise ValueError(f"Tool '{tool_name}' not found. Available tools: {available}")

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
