"""FastAPI server with WebSocket chat interface."""
import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.foundation.state import ConversationStore
from src.models.llm_client import LLMClient
from src.tools.tool_manager import ToolManager


# Load environment variables
load_dotenv()

# Configuration
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://localhost:8080/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "glm-4")
PORT = 8101

# Initialize
app = FastAPI(title="minifram")
store = ConversationStore()
llm: Optional[LLMClient] = None
tools: Optional[ToolManager] = None

# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
async def startup():
    """Initialize LLM client and tool manager on startup."""
    global llm, tools
    llm = LLMClient(endpoint=LLM_ENDPOINT, model=LLM_MODEL)
    tools = ToolManager()
    await tools.load_config("mcp_config.json")

    print(f"🚀 minifram starting on http://localhost:{PORT}")
    print(f"📡 LLM endpoint: {LLM_ENDPOINT}")
    print(f"🤖 Model: {LLM_MODEL}")
    print(f"🔧 Tools loaded: {len(tools.get_all_tools())}")


@app.on_event("shutdown")
async def shutdown():
    """Close LLM client and tool manager on shutdown."""
    if llm:
        await llm.close()
    if tools:
        await tools.close_all()


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

    return {
        "servers": tools.get_server_status(),
        "tools": tools.get_all_tools()
    }


@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    """WebSocket endpoint for chat conversations."""
    await websocket.accept()

    # Get or create conversation
    conversation = store.get_or_create(conversation_id)

    # Send connection confirmation
    await websocket.send_json({
        "type": "system",
        "content": f"Connected to {LLM_MODEL}",
        "conversation_id": conversation_id
    })

    # Send conversation history
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
            # Receive message from client
            data = await websocket.receive_json()

            if data["type"] == "message":
                user_content = data["content"]

                # Add user message to conversation
                conversation.add_message("user", user_content)

                # Echo user message back
                await websocket.send_json({
                    "type": "message",
                    "role": "user",
                    "content": user_content
                })

                # Send loading indicator
                await websocket.send_json({
                    "type": "loading",
                    "content": "Waiting for model response..."
                })

                # Get LLM response with tool support
                try:
                    # Build tool definitions for LLM
                    available_tools = []
                    if tools:
                        for tool in tools.get_all_tools():
                            available_tools.append({
                                "type": "function",
                                "function": {
                                    "name": tool["name"],
                                    "description": tool["description"],
                                    "parameters": tool["inputSchema"]
                                }
                            })

                    llm_messages = conversation.to_llm_format()

                    # Try with tools first if available
                    if available_tools:
                        response = await llm.chat(llm_messages, available_tools)

                        # If model doesn't support tools, warn once
                        if response.get("_tools_unsupported"):
                            await websocket.send_json({
                                "type": "system",
                                "content": f"Note: {LLM_MODEL} doesn't support tool calling. Tools won't be used."
                            })
                            # Don't try tools again for this model
                            available_tools = []
                    else:
                        response = await llm.chat(llm_messages)

                    message = response["choices"][0]["message"]

                    # Check if LLM wants to call a tool
                    tool_calls = message.get("tool_calls", [])

                    if tool_calls and tools:
                        # Execute tool calls
                        for tool_call in tool_calls:
                            func = tool_call["function"]
                            tool_name = func["name"]
                            tool_args = json.loads(func["arguments"]) if isinstance(func["arguments"], str) else func["arguments"]

                            # Format and send tool call display
                            tool_display = tools.format_tool_call(tool_name, tool_args)
                            await websocket.send_json({
                                "type": "message",
                                "role": "tool",
                                "content": "",
                                "tool_call": tool_display
                            })

                            # Execute the tool
                            try:
                                tool_result = await tools.call_tool(tool_name, tool_args)

                                # Add tool result to conversation
                                conversation.add_message("tool", tool_result)

                                # Continue conversation with tool result
                                llm_messages = conversation.to_llm_format()
                                response = await llm.chat(llm_messages)
                                message = response["choices"][0]["message"]

                            except Exception as e:
                                await websocket.send_json({
                                    "type": "error",
                                    "content": f"Tool error: {str(e)}"
                                })
                                continue

                    # Clear loading indicator
                    await websocket.send_json({
                        "type": "loading_done"
                    })

                    # Extract and send final assistant message
                    assistant_content = message.get("content", "")

                    if assistant_content:
                        # Add assistant message to conversation
                        conversation.add_message("assistant", assistant_content)

                        # Send assistant response
                        await websocket.send_json({
                            "type": "message",
                            "role": "assistant",
                            "content": assistant_content
                        })

                except Exception as e:
                    # Clear loading indicator on error
                    await websocket.send_json({
                        "type": "loading_done"
                    })
                    # Send error message
                    await websocket.send_json({
                        "type": "error",
                        "content": f"LLM error: {str(e)}"
                    })

    except WebSocketDisconnect:
        print(f"Client disconnected from conversation {conversation_id}")


def main():
    """Entry point for uv run go."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
