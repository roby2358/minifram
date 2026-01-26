"""FastAPI server with WebSocket chat interface."""
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.agents.handler import execute_agent_loop, execute_agent_loop_headless, build_tool_definitions
from src.agents.mcp_server import mcp, init_mcp, do_agent_complete
from src.agents.state import Agent, AgentStatus, AgentStore
from src.foundation.reasoning import extract_reasoning
from src.foundation.state import Conversation, ConversationStore
from src.models.llm_client import LLMClient
from src.tools.tool_manager import ToolManager


# --- Configuration ---

load_dotenv()

LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://localhost:8080/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "glm-4")
PORT = 8101


# --- Application state ---

store = ConversationStore()
agent_store = AgentStore()
llm: Optional[LLMClient] = None
tools: Optional[ToolManager] = None
static_dir = Path(__file__).parent.parent / "static"

# Create MCP http app early so we can access its lifespan
mcp_app = mcp.http_app(path="/")


async def start_agent_from_mcp(agent: Agent):
    """Callback for MCP to start agent execution."""
    agent.status = AgentStatus.RUNNING
    await execute_agent_loop_headless(agent, llm, tools)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    global llm, tools

    # Startup
    llm = LLMClient(endpoint=LLM_ENDPOINT, model=LLM_MODEL)
    tools = ToolManager()
    await tools.load_config("mcp_config.json")

    # Register agent_complete as internal tool so agents can call it
    tools.register_internal_tool(
        name="agent_complete",
        description="Signal that the agent has completed its contract. Call this when the objective is fulfilled.",
        parameters={
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "The agent's ID"},
                "summary": {"type": "string", "description": "Brief summary of what was accomplished"},
                "payload": {"type": "string", "description": "Optional detailed work product data"}
            },
            "required": ["agent_id", "summary"]
        },
        handler=do_agent_complete
    )

    init_mcp(agent_store, start_agent_from_mcp)

    print(f"🚀 minifram starting on http://localhost:{PORT}")
    print(f"📡 LLM endpoint: {LLM_ENDPOINT}")
    print(f"🤖 Model: {LLM_MODEL}")
    print(f"🔧 Tools loaded: {len(tools.get_all_tools())}")
    print(f"🔌 MCP endpoint: http://localhost:{PORT}/mcp")

    # Run MCP app lifespan nested inside ours
    async with mcp_app.router.lifespan_context(mcp_app):
        yield

    # Shutdown
    if llm:
        await llm.close()
    if tools:
        await tools.close_all()


# --- Application setup ---

app = FastAPI(title="minifram", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/mcp", mcp_app)


# --- HTTP Routes ---

@app.get("/")
async def root():
    """Serve the main HTML interface."""
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "model": LLM_MODEL, "endpoint": LLM_ENDPOINT}


@app.get("/api/tools")
async def get_tools():
    """Get MCP tool status."""
    if not tools:
        return {"servers": [], "tools": []}
    return {"servers": tools.get_server_status(), "tools": tools.get_all_tools()}


# --- Agent HTTP Routes ---

@app.post("/api/agents")
async def create_agent():
    """Create a new agent."""
    agent = agent_store.create()
    return {"id": agent.id, "status": agent.status.value}


@app.get("/api/agents")
async def list_agents():
    """List all agents."""
    return {
        "agents": [
            {
                "id": a.id,
                "status": a.status.value,
                "contract": a.contract[:50] + "..." if len(a.contract) > 50 else a.contract
            }
            for a in agent_store.get_all()
        ]
    }


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details."""
    agent = agent_store.get(agent_id)
    if not agent:
        return {"error": "Agent not found"}
    return {
        "id": agent.id,
        "status": agent.status.value,
        "contract": agent.contract,
        "output": [{"type": o.type, "content": o.content, "tool_call": o.tool_call} for o in agent.output]
    }


@app.post("/api/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    """Request an agent to stop."""
    agent = agent_store.get(agent_id)
    if not agent:
        return {"error": "Agent not found"}
    agent.request_stop()
    return {"status": "stop_requested"}


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete an agent."""
    agent_store.delete(agent_id)
    return {"status": "deleted"}


@app.get("/api/agents/{agent_id}/payload")
async def get_agent_payload(agent_id: str):
    """Get agent payload (gzip-compressed)."""
    agent = agent_store.get(agent_id)
    if not agent:
        return Response(status_code=404, content="Agent not found")
    if agent.payload is None:
        return Response(status_code=404, content="No payload")
    return Response(content=agent.payload, media_type="application/octet-stream", headers={"Content-Encoding": "gzip"})


# --- Chat WebSocket helpers ---

def truncate(text: str, max_len: int = 200) -> str:
    """Truncate text with ellipsis."""
    return text if len(text) <= max_len else text[:max_len] + "..."


async def execute_tool(
    websocket: WebSocket,
    conversation: Conversation,
    tools: ToolManager,
    tool_call: dict,
    available_tools: list,
    llm: LLMClient
) -> tuple[str, list]:
    """Execute a tool call and get model's next response."""
    func = tool_call["function"]
    tool_name = func["name"]
    tool_args = json.loads(func["arguments"]) if isinstance(func["arguments"], str) else func["arguments"]

    # Send tool call to UI
    await websocket.send_json({
        "type": "message",
        "role": "tool",
        "content": "",
        "tool_call": tools.format_tool_call(tool_name, tool_args)
    })

    # Execute tool
    result = await tools.call_tool(tool_name, tool_args)
    conversation.add_message("tool", result)

    # Send result preview to UI
    await websocket.send_json({
        "type": "message",
        "role": "system",
        "content": f"→ {truncate(result)}"
    })

    # Get model's response to tool result
    response = await llm.chat(conversation.to_llm_format(), available_tools)
    message = response["choices"][0]["message"]
    return message.get("content", ""), message.get("tool_calls", [])


async def process_tool_loop(
    websocket: WebSocket,
    conversation: Conversation,
    tools: ToolManager,
    assistant_content: str,
    tool_calls: list,
    available_tools: list,
    llm: LLMClient
) -> str:
    """Process tool calls until model stops requesting them."""
    while tool_calls and tools:
        if assistant_content:
            await websocket.send_json({"type": "message", "role": "assistant", "content": assistant_content})

        conversation.add_message("assistant", assistant_content or "", tool_call=json.dumps(tool_calls))

        for tool_call in tool_calls:
            try:
                assistant_content, tool_calls = await execute_tool(
                    websocket, conversation, tools, tool_call, available_tools, llm
                )
                if tool_calls:
                    break
            except Exception as e:
                await websocket.send_json({"type": "error", "content": f"Tool error: {str(e)}"})

        if not tool_calls:
            break

    return assistant_content


async def handle_chat_message(websocket: WebSocket, conversation: Conversation, user_content: str):
    """Handle a single chat message from user."""
    conversation.add_message("user", user_content)
    await websocket.send_json({"type": "message", "role": "user", "content": user_content})
    await websocket.send_json({"type": "loading", "content": "Waiting for model response..."})

    try:
        # Build tools and get initial response
        available_tools = build_tool_definitions(tools) if tools else []
        response = await llm.chat(conversation.to_llm_format(), available_tools) if available_tools else await llm.chat(conversation.to_llm_format())

        # Handle tool unsupported warning
        if available_tools and response.get("_tools_unsupported"):
            await websocket.send_json({"type": "system", "content": f"Note: {LLM_MODEL} doesn't support tool calling."})
            available_tools = []

        message = response["choices"][0]["message"]
        assistant_content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])

        # Process any tool calls
        if tool_calls:
            assistant_content = await process_tool_loop(
                websocket, conversation, tools, assistant_content, tool_calls, available_tools, llm
            )

        # Send final response
        await websocket.send_json({"type": "loading_done"})

        reasoning, cleaned_content = extract_reasoning(message, assistant_content)
        if reasoning:
            await websocket.send_json({"type": "reasoning", "content": reasoning})

        if cleaned_content:
            conversation.add_message("assistant", cleaned_content)
            await websocket.send_json({"type": "message", "role": "assistant", "content": cleaned_content})

    except Exception as e:
        await websocket.send_json({"type": "loading_done"})
        await websocket.send_json({"type": "error", "content": f"LLM error: {str(e)}"})


# --- WebSocket endpoints ---

@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    """WebSocket endpoint for chat conversations."""
    await websocket.accept()
    conversation = store.get_or_create(conversation_id)

    # Send connection info and history
    await websocket.send_json({"type": "system", "content": f"Connected to {LLM_MODEL}", "conversation_id": conversation_id})
    for msg in conversation.messages:
        await websocket.send_json({
            "type": "message",
            "role": msg.role,
            "content": msg.content,
            "tool_call": msg.tool_call,
            "timestamp": msg.timestamp.isoformat()
        })

    try:
        while True:
            data = await websocket.receive_json()
            if data["type"] == "message":
                await handle_chat_message(websocket, conversation, data["content"])
    except WebSocketDisconnect:
        print(f"Client disconnected from conversation {conversation_id}")


@app.websocket("/ws/agent/{agent_id}")
async def agent_websocket_endpoint(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for agent execution."""
    await websocket.accept()

    agent = agent_store.get(agent_id)
    if not agent:
        await websocket.send_json({"type": "error", "content": "Agent not found"})
        await websocket.close()
        return

    await websocket.send_json({"type": "init", "id": agent.id, "status": agent.status.value, "contract": agent.contract})

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "set_contract":
                agent.contract = data["contract"]
                await websocket.send_json({"type": "contract_set", "contract": agent.contract})

            elif data["type"] == "start":
                if agent.status != AgentStatus.READY:
                    await websocket.send_json({"type": "error", "content": "Agent not in ready state"})
                elif not agent.contract.strip():
                    await websocket.send_json({"type": "error", "content": "Contract is empty"})
                else:
                    await execute_agent_loop(websocket, agent, llm, tools)

            elif data["type"] == "stop":
                agent.request_stop()
                await websocket.send_json({"type": "stop_requested"})

            elif data["type"] == "restart":
                agent.reset_for_restart()
                await websocket.send_json({"type": "status", "content": "ready"})

    except WebSocketDisconnect:
        print(f"Client disconnected from agent {agent_id}")


# --- Entry point ---

def main():
    """Entry point for uv run go."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
