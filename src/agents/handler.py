"""Agent WebSocket handler for autonomous execution."""
import json
from datetime import datetime
from pathlib import Path

from fastapi import WebSocket

from src.agents.state import Agent, AgentStatus
from src.foundation.state import Conversation
from src.models.llm_client import LLMClient
from src.tools.tool_manager import ToolManager


AGENT_SYSTEM_PROMPT = """You are an autonomous agent executing a contract. Your task is to complete the objective described in the contract.

After each action, evaluate whether the contract objective has been fully satisfied. When the objective is complete, respond with exactly: [CONTRACT COMPLETE]

If you cannot complete the contract (missing tools, errors, etc.), respond with: [CONTRACT FAILED] followed by the reason.

Stay focused on the contract objective. Do not ask for user input - work autonomously."""


# --- Pure utility functions (no dependencies) ---

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
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def check_contract_status(content: str) -> str | None:
    """Check if content indicates contract completion or failure.

    Returns:
        'completed' if contract complete, 'stopped' if failed, None otherwise
    """
    if "[CONTRACT COMPLETE]" in content:
        return "completed"
    if "[CONTRACT FAILED]" in content:
        return "stopped"
    return None


def parse_tool_call(tool_call: dict) -> tuple[str, dict]:
    """Extract tool name and arguments from a tool call.

    Returns:
        (tool_name, tool_args) tuple
    """
    func = tool_call["function"]
    tool_name = func["name"]
    args = func["arguments"]
    tool_args = json.loads(args) if isinstance(args, str) else args
    return tool_name, tool_args


def init_agent_conversation(agent: Agent):
    """Initialize agent conversation with system prompt and contract."""
    agent.conversation = Conversation(id=agent.id)
    agent.conversation.add_message("system", AGENT_SYSTEM_PROMPT)
    agent.conversation.add_message("user", f"Contract:\n{agent.contract}\n\nBegin executing this contract now.")


# --- Async helpers for WebSocket communication ---

async def emit_output(
    websocket: WebSocket,
    agent: Agent,
    msg_type: str,
    content: str,
    tool_call: str = None
):
    """Record output to agent and send to websocket."""
    agent.add_output(msg_type, content, tool_call=tool_call)
    await websocket.send_json({
        "type": msg_type,
        "content": content,
        "tool_call": tool_call
    })


async def set_agent_status(websocket: WebSocket, agent: Agent, status: AgentStatus):
    """Update agent status and notify websocket."""
    agent.status = status
    await websocket.send_json({
        "type": "status",
        "content": status.value
    })


async def get_llm_response(llm: LLMClient, messages: list, tools: list) -> tuple[str, list]:
    """Get LLM response and extract content and tool calls.

    Returns:
        (assistant_content, tool_calls) tuple
    """
    if tools:
        response = await llm.chat(messages, tools)
    else:
        response = await llm.chat(messages)

    message = response["choices"][0]["message"]
    return message.get("content", ""), message.get("tool_calls", [])


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
    websocket: WebSocket,
    agent: Agent,
    tools: ToolManager,
    tool_call: dict
) -> str:
    """Execute a single tool call and return the result.

    Returns:
        Tool result string (or error message)
    """
    tool_name, tool_args = parse_tool_call(tool_call)

    # Display tool call
    tool_display = tools.format_tool_call(tool_name, tool_args)
    await emit_output(websocket, agent, "tool", "", tool_call=tool_display)

    # Execute and display result
    try:
        result = await tools.call_tool(tool_name, tool_args)
        display_result = f"→ {truncate_result(result)}"
        await emit_output(websocket, agent, "system", display_result)
        return result
    except Exception as e:
        error_msg = f"Tool error: {str(e)}"
        await emit_output(websocket, agent, "error", error_msg)
        return f"Error: {str(e)}"


async def process_tool_calls(
    websocket: WebSocket,
    agent: Agent,
    tools: ToolManager,
    tool_calls: list,
    assistant_content: str
):
    """Process all tool calls and update conversation."""
    # Send assistant message before tool calls
    if assistant_content:
        await emit_output(websocket, agent, "assistant", assistant_content)
        agent.conversation.add_message("assistant", assistant_content)

    # Execute each tool
    for tool_call in tool_calls:
        if agent.stop_requested:
            break

        result = await execute_tool_call(websocket, agent, tools, tool_call)

        # Add to conversation
        agent.conversation.add_message("assistant", assistant_content or "", tool_call=json.dumps(tool_calls))
        agent.conversation.add_message("tool", result)


# --- Agent loop ---

async def process_single_turn(
    websocket: WebSocket,
    agent: Agent,
    llm: LLMClient,
    tools: ToolManager,
    available_tools: list
) -> bool:
    """Process one LLM turn. Returns True if loop should continue."""
    assistant_content, tool_calls = await get_llm_response(
        llm, agent.conversation.to_llm_format(), available_tools
    )

    # Check for contract completion
    final_status = check_contract_status(assistant_content)
    if final_status:
        await emit_output(websocket, agent, "assistant", assistant_content)
        status = AgentStatus.COMPLETED if final_status == "completed" else AgentStatus.STOPPED
        await set_agent_status(websocket, agent, status)
        return False

    # Process tool calls or plain response
    if tool_calls:
        await process_tool_calls(websocket, agent, tools, tool_calls, assistant_content)
    else:
        await emit_output(websocket, agent, "assistant", assistant_content)
        agent.conversation.add_message("assistant", assistant_content)

    return True


async def run_agent_loop(
    websocket: WebSocket,
    agent: Agent,
    llm: LLMClient,
    tools: ToolManager,
    available_tools: list
):
    """Run the agent loop until completion, failure, or stop."""
    while not agent.stop_requested:
        should_continue = await process_single_turn(
            websocket, agent, llm, tools, available_tools
        )
        if not should_continue:
            return

    await set_agent_status(websocket, agent, AgentStatus.STOPPED)


async def execute_agent_loop(
    websocket: WebSocket,
    agent: Agent,
    llm: LLMClient,
    tools: ToolManager
):
    """Execute the autonomous agent loop.

    The agent runs until:
    - Contract is completed (LLM responds with [CONTRACT COMPLETE])
    - Contract fails (LLM responds with [CONTRACT FAILED])
    - Stop is requested by user
    - Error occurs
    """
    init_agent_conversation(agent)
    await set_agent_status(websocket, agent, AgentStatus.RUNNING)
    available_tools = build_tool_definitions(tools) if tools else []

    try:
        await run_agent_loop(websocket, agent, llm, tools, available_tools)
    except Exception as e:
        await emit_output(websocket, agent, "error", f"Agent error: {str(e)}")
        await set_agent_status(websocket, agent, AgentStatus.STOPPED)

    await write_agent_log(agent)
