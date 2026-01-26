"""Agent execution handler for autonomous contract completion."""
import json
from datetime import datetime
from pathlib import Path
from typing import Protocol

from fastapi import WebSocket

from src.agents.state import Agent, AgentStatus
from src.foundation.state import Conversation
from src.models.llm_client import LLMClient
from src.tools.tool_manager import ToolManager


# --- System prompts ---

def get_system_prompt(agent_id: str | None = None) -> str:
    """Get the agent system prompt, optionally with MCP agent_complete instructions."""
    base = """You are an autonomous agent executing a contract. Your task is to complete the objective described in the contract.

Stay focused on the contract objective. Do not ask for user input - work autonomously."""

    if agent_id:
        return f"""{base}

Your agent ID is: {agent_id}

When the contract objective is fully satisfied, call the agent_complete tool with your agent_id and a summary of what you accomplished. You may optionally include a payload with detailed work product data.

If you cannot complete the contract (missing tools, errors, etc.), call agent_complete with a summary explaining the failure."""
    else:
        return f"""{base}

After each action, evaluate whether the contract objective has been fully satisfied. When the objective is complete, respond with exactly: [CONTRACT COMPLETE]

If you cannot complete the contract (missing tools, errors, etc.), respond with: [CONTRACT FAILED] followed by the reason."""


# --- Output emitter abstraction ---

class Emitter(Protocol):
    """Protocol for emitting agent output and status updates."""

    async def output(self, agent: Agent, msg_type: str, content: str, tool_call: str | None = None) -> None:
        """Emit an output message."""
        ...

    async def status(self, agent: Agent, status: AgentStatus) -> None:
        """Emit a status change."""
        ...


class WebSocketEmitter:
    """Emitter that sends to WebSocket and records to agent."""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def output(self, agent: Agent, msg_type: str, content: str, tool_call: str | None = None) -> None:
        agent.add_output(msg_type, content, tool_call=tool_call)
        await self.websocket.send_json({
            "type": msg_type,
            "content": content,
            "tool_call": tool_call
        })

    async def status(self, agent: Agent, status: AgentStatus) -> None:
        agent.status = status
        await self.websocket.send_json({
            "type": "status",
            "content": status.value
        })


class HeadlessEmitter:
    """Emitter that only records to agent (no WebSocket)."""

    async def output(self, agent: Agent, msg_type: str, content: str, tool_call: str | None = None) -> None:
        agent.add_output(msg_type, content, tool_call=tool_call)

    async def status(self, agent: Agent, status: AgentStatus) -> None:
        agent.status = status
        # Set timestamps for MCP-triggered agents
        if status == AgentStatus.COMPLETED:
            agent.completed_at = datetime.now()
        elif status == AgentStatus.STOPPED:
            agent.stopped_at = datetime.now()


# --- Utility functions ---

def build_tool_definitions(tools: ToolManager) -> list[dict]:
    """Build tool definitions for LLM from MCP tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["inputSchema"]
            }
        }
        for tool in tools.get_all_tools()
    ]


def truncate_result(text: str, max_len: int = 200) -> str:
    """Truncate text with ellipsis if too long."""
    return text if len(text) <= max_len else text[:max_len] + "..."


def check_contract_status(content: str) -> str | None:
    """Check if content indicates contract completion or failure.

    Returns 'completed', 'stopped', or None.
    """
    if "[CONTRACT COMPLETE]" in content:
        return "completed"
    if "[CONTRACT FAILED]" in content:
        return "stopped"
    return None


def parse_tool_call(tool_call: dict) -> tuple[str, dict]:
    """Extract tool name and arguments from a tool call."""
    func = tool_call["function"]
    args = func["arguments"]
    return func["name"], json.loads(args) if isinstance(args, str) else args


def init_agent_conversation(agent: Agent, use_mcp_prompt: bool = False):
    """Initialize agent conversation with system prompt and contract."""
    agent.conversation = Conversation(id=agent.id)
    prompt = get_system_prompt(agent.id if use_mcp_prompt else None)
    agent.conversation.add_message("system", prompt)
    agent.conversation.add_message("user", f"Contract:\n{agent.contract}\n\nBegin executing this contract now.")


# --- LLM interaction ---

async def get_llm_response(llm: LLMClient, messages: list, tools: list) -> tuple[str, list]:
    """Get LLM response and extract content and tool calls."""
    response = await llm.chat(messages, tools) if tools else await llm.chat(messages)
    message = response["choices"][0]["message"]
    return message.get("content", ""), message.get("tool_calls", [])


# --- Logging ---

async def write_agent_log(agent: Agent):
    """Write agent output to a timestamped log file."""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"{agent.id}_{timestamp}.log"

    lines = [
        f"Agent: {agent.id}",
        f"Status: {agent.status.value}",
        f"Created: {agent.created_at.isoformat()}",
        f"Contract:\n{agent.contract}",
        "",
        "=" * 60,
        "Output:",
        "=" * 60,
        ""
    ]

    for entry in agent.output:
        ts = entry.timestamp.strftime("%H:%M:%S")
        if entry.tool_call:
            lines.append(f"[{ts}] [Tool: {entry.tool_call}]")
        else:
            lines.append(f"[{ts}] [{entry.type}] {entry.content}")

    log_file.write_text("\n".join(lines))


# --- Tool execution ---

async def execute_tool_call(
    emitter: Emitter,
    agent: Agent,
    tools: ToolManager,
    tool_call: dict
) -> str:
    """Execute a single tool call and return the result."""
    tool_name, tool_args = parse_tool_call(tool_call)
    tool_display = tools.format_tool_call(tool_name, tool_args)
    await emitter.output(agent, "tool", "", tool_call=tool_display)

    try:
        result = await tools.call_tool(tool_name, tool_args)
        await emitter.output(agent, "system", f"→ {truncate_result(result)}")
        return result
    except Exception as e:
        error_msg = f"Tool error: {str(e)}"
        await emitter.output(agent, "error", error_msg)
        return f"Error: {str(e)}"


async def process_tool_calls(
    emitter: Emitter,
    agent: Agent,
    tools: ToolManager,
    tool_calls: list,
    assistant_content: str
):
    """Process all tool calls and update conversation."""
    if assistant_content:
        await emitter.output(agent, "assistant", assistant_content)
        agent.conversation.add_message("assistant", assistant_content)

    for tool_call in tool_calls:
        if agent.stop_requested:
            break

        result = await execute_tool_call(emitter, agent, tools, tool_call)
        agent.conversation.add_message("assistant", assistant_content or "", tool_call=json.dumps(tool_calls))
        agent.conversation.add_message("tool", result)


# --- Agent loop ---

async def process_single_turn(
    emitter: Emitter,
    agent: Agent,
    llm: LLMClient,
    tools: ToolManager,
    available_tools: list
) -> bool:
    """Process one LLM turn. Returns True if loop should continue."""
    assistant_content, tool_calls = await get_llm_response(
        llm, agent.conversation.to_llm_format(), available_tools
    )

    # Check for contract completion (legacy pattern or MCP tool already called)
    if agent.status == AgentStatus.COMPLETED:
        return False

    final_status = check_contract_status(assistant_content)
    if final_status:
        await emitter.output(agent, "assistant", assistant_content)
        status = AgentStatus.COMPLETED if final_status == "completed" else AgentStatus.STOPPED
        await emitter.status(agent, status)
        return False

    # Process tool calls or plain response
    if tool_calls:
        await process_tool_calls(emitter, agent, tools, tool_calls, assistant_content)
    else:
        await emitter.output(agent, "assistant", assistant_content)
        agent.conversation.add_message("assistant", assistant_content)

    return True


async def run_agent_loop(
    emitter: Emitter,
    agent: Agent,
    llm: LLMClient,
    tools: ToolManager,
    available_tools: list
):
    """Run the agent loop until completion, failure, or stop."""
    while not agent.stop_requested and agent.status != AgentStatus.COMPLETED:
        if not await process_single_turn(emitter, agent, llm, tools, available_tools):
            return

    if agent.stop_requested and agent.status != AgentStatus.COMPLETED:
        await emitter.status(agent, AgentStatus.STOPPED)


async def execute_agent_loop_core(
    emitter: Emitter,
    agent: Agent,
    llm: LLMClient,
    tools: ToolManager,
    use_mcp_prompt: bool
):
    """Core agent loop execution used by both WebSocket and headless modes."""
    init_agent_conversation(agent, use_mcp_prompt=use_mcp_prompt)
    await emitter.status(agent, AgentStatus.RUNNING)
    available_tools = build_tool_definitions(tools) if tools else []

    try:
        await run_agent_loop(emitter, agent, llm, tools, available_tools)
    except Exception as e:
        await emitter.output(agent, "error", f"Agent error: {str(e)}")
        await emitter.status(agent, AgentStatus.STOPPED)

    await write_agent_log(agent)


# --- Public entry points ---

async def execute_agent_loop(
    websocket: WebSocket,
    agent: Agent,
    llm: LLMClient,
    tools: ToolManager
):
    """Execute agent loop with WebSocket output (for UI)."""
    emitter = WebSocketEmitter(websocket)
    await execute_agent_loop_core(emitter, agent, llm, tools, use_mcp_prompt=True)


async def execute_agent_loop_headless(
    agent: Agent,
    llm: LLMClient,
    tools: ToolManager
):
    """Execute agent loop without WebSocket (for MCP)."""
    emitter = HeadlessEmitter()
    await execute_agent_loop_core(emitter, agent, llm, tools, use_mcp_prompt=True)
