"""Agent MCP server exposing lifecycle tools."""
import asyncio
import gzip
from datetime import datetime

from fastmcp import FastMCP

from src.agents.state import Agent, AgentStatus, AgentStore


# Create the MCP server instance
mcp = FastMCP("minifram-agents")

# These will be set by server.py on startup
agent_store: AgentStore = None
start_agent_callback = None  # async function to start agent execution


def init_mcp(store: AgentStore, start_callback):
    """Initialize MCP with shared state and callbacks."""
    global agent_store, start_agent_callback
    agent_store = store
    start_agent_callback = start_callback


def _format_timestamp(dt: datetime | None) -> str | None:
    """Format datetime as ISO 8601 string."""
    return dt.isoformat() if dt else None


def _build_status_object(agent: Agent) -> dict:
    """Build status response object for an agent."""
    result = {
        "agent_id": agent.id,
        "status": agent.status.value,
        "started_at": _format_timestamp(agent.started_at),
    }

    if agent.status == AgentStatus.COMPLETED:
        result["completed_at"] = _format_timestamp(agent.completed_at)
        if agent.summary:
            result["summary"] = agent.summary

    if agent.status == AgentStatus.STOPPED:
        result["stopped_at"] = _format_timestamp(agent.stopped_at)

    if agent.payload is not None:
        result["payload_size"] = agent.payload_size
        result["payload_url"] = f"http://localhost:8101/api/agents/{agent.id}/payload"

    # For running agents, include truncated recent output
    if agent.status == AgentStatus.RUNNING and agent.output:
        recent = agent.output[-1]
        preview = recent.content[:200] + "..." if len(recent.content) > 200 else recent.content
        result["recent_output"] = preview

    return result


@mcp.tool()
async def agent_start(contract: str) -> dict:
    """Start an autonomous agent with the given contract.

    Args:
        contract: The task objective for the agent to complete.

    Returns:
        Agent ID, status, and start timestamp.
    """
    if not agent_store:
        return {"error": "Agent store not initialized"}

    agent = agent_store.create()
    agent.contract = contract
    agent.started_at = datetime.now()

    # Start agent execution in background
    if start_agent_callback:
        asyncio.create_task(start_agent_callback(agent))

    return {
        "agent_id": agent.id,
        "status": "running",
        "started_at": _format_timestamp(agent.started_at),
    }


@mcp.tool()
async def agent_status(agent_ids: list[str]) -> list[dict]:
    """Check the status of one or more agents.

    Args:
        agent_ids: List of agent IDs to check.

    Returns:
        List of status objects for each agent.
    """
    if not agent_store:
        return [{"error": "Agent store not initialized"}]

    results = []
    for agent_id in agent_ids:
        agent = agent_store.get(agent_id)
        if agent:
            results.append(_build_status_object(agent))
        else:
            results.append({"agent_id": agent_id, "error": "Agent not found"})

    return results


@mcp.tool()
async def agent_stop(agent_id: str) -> dict:
    """Stop a running agent.

    Args:
        agent_id: The ID of the agent to stop.

    Returns:
        Status confirmation with timestamps.
    """
    if not agent_store:
        return {"error": "Agent store not initialized"}

    agent = agent_store.get(agent_id)
    if not agent:
        return {"error": "Agent not found"}

    # Idempotent - already stopped or completed
    if agent.status in (AgentStatus.STOPPED, AgentStatus.COMPLETED):
        return {
            "status": agent.status.value,
            "started_at": _format_timestamp(agent.started_at),
            "stopped_at": _format_timestamp(agent.stopped_at),
            "completed_at": _format_timestamp(agent.completed_at),
        }

    agent.request_stop()
    agent.stopped_at = datetime.now()
    agent.status = AgentStatus.STOPPED

    return {
        "status": "stopped",
        "started_at": _format_timestamp(agent.started_at),
        "stopped_at": _format_timestamp(agent.stopped_at),
    }


@mcp.tool()
async def agent_complete(agent_id: str, summary: str, payload: str | None = None) -> dict:
    """Signal that an agent has completed its contract.

    Called by the agent itself when the contract objective is fulfilled.

    Args:
        agent_id: The ID of the completing agent.
        summary: A brief description of the outcome.
        payload: Optional work product data.

    Returns:
        Status confirmation with timestamps.
    """
    if not agent_store:
        return {"error": "Agent store not initialized"}

    agent = agent_store.get(agent_id)
    if not agent:
        return {"error": "Agent not found"}

    # Idempotent - already completed
    if agent.status == AgentStatus.COMPLETED:
        return {
            "status": "completed",
            "started_at": _format_timestamp(agent.started_at),
            "completed_at": _format_timestamp(agent.completed_at),
        }

    agent.status = AgentStatus.COMPLETED
    agent.completed_at = datetime.now()
    agent.summary = summary

    # Store payload as gzip-compressed bytes
    if payload:
        payload_bytes = payload.encode("utf-8")
        agent.payload_size = len(payload_bytes)
        agent.payload = gzip.compress(payload_bytes)

    return {
        "status": "completed",
        "started_at": _format_timestamp(agent.started_at),
        "completed_at": _format_timestamp(agent.completed_at),
    }
