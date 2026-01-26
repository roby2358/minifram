#!/usr/bin/env python3
"""Simple hello world MCP server for testing."""
from fastmcp import FastMCP

mcp = FastMCP("hello-server")


@mcp.tool()
def hello() -> str:
    """Says hello world"""
    return "Hello, world!"


@mcp.tool()
def echo(message: str) -> str:
    """Echoes back the input message"""
    return f"Echo: {message}"


if __name__ == "__main__":
    mcp.run()
