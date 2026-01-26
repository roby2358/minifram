"""FastAPI server with WebSocket chat interface."""
import json
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.foundation.state import Conversation, ConversationStore
from src.models.llm_client import LLMClient
from src.tools.tool_manager import ToolManager


def extract_reasoning_field(message: dict) -> str | None:
    """Extract reasoning from message.reasoning field (GLM-4.7-flash)."""
    return message.get("reasoning")


def extract_think_tags(content: str) -> tuple[str | None, str]:
    """Extract <think>/<thinking> tags from content and return (reasoning, cleaned_content).

    Handles both <think>...</think> and <thinking>...</thinking> tag variants.
    Also handles unclosed tags (extracts content after opening tag to end).

    Returns:
        (reasoning, cleaned_content) where reasoning is extracted thinking or None,
        and cleaned_content is the content with think tags removed.
    """
    if not content:
        return None, content

    # Check if any think tags (opening or closing) are present
    has_tags = any(tag in content for tag in [
        "<think>", "</think>", "<thinking>", "</thinking>"
    ])
    if not has_tags:
        return None, content

    all_reasoning = []
    cleaned_content = content

    # Process both tag variants
    for tag in ["thinking", "think"]:
        open_tag = f"<{tag}>"
        close_tag = f"</{tag}>"

        # Extract complete tag pairs
        pattern = rf'<{tag}>(.*?)</{tag}>'
        matches = re.findall(pattern, cleaned_content, re.DOTALL)
        all_reasoning.extend(matches)

        # Remove complete tag pairs
        cleaned_content = re.sub(pattern, '', cleaned_content, flags=re.DOTALL)

        # Handle unclosed tags - extract content from opening tag to end
        if open_tag in cleaned_content:
            unclosed_pattern = rf'<{tag}>(.*)$'
            unclosed_match = re.search(unclosed_pattern, cleaned_content, re.DOTALL)
            if unclosed_match:
                all_reasoning.append(unclosed_match.group(1))
                cleaned_content = re.sub(unclosed_pattern, '', cleaned_content, flags=re.DOTALL)

        # Remove any stray closing tags
        cleaned_content = cleaned_content.replace(close_tag, '')

    if not all_reasoning:
        return None, cleaned_content.strip()

    reasoning = "\n\n".join(r.strip() for r in all_reasoning if r.strip())
    return reasoning if reasoning else None, cleaned_content.strip()


def build_tool_definitions(tools: ToolManager) -> list[dict]:
    """Build tool definitions for LLM from MCP tools."""
    available_tools = []
    for tool in tools.get_all_tools():
        available_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["inputSchema"]
            }
        })

    print(f"\n📋 Sending {len(available_tools)} tools to model")
    for t in available_tools:
        print(f"  - {t['function']['name']}: {t['function']['description']}")

    return available_tools


async def execute_single_tool(
    websocket: WebSocket,
    conversation: Conversation,
    tools: ToolManager,
    tool_call: dict,
    available_tools: list[dict],
    llm: LLMClient
) -> tuple[str, list]:
    """Execute a single tool call and get model's response.

    Returns:
        (assistant_content, tool_calls) for next iteration
    """
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
    print("\n" + "="*80)
    print("🔧 CALLING TOOL:")
    print(f"  Tool: {tool_name}")
    print(f"  Arguments: {json.dumps(tool_args, indent=2)}")
    print("="*80)

    tool_result = await tools.call_tool(tool_name, tool_args)

    print("\n" + "="*80)
    print("✅ TOOL RESULT:")
    print(f"  {tool_result}")
    print("="*80 + "\n")

    # Add tool result to conversation
    conversation.add_message("tool", tool_result)

    # Send tool result to UI
    await websocket.send_json({
        "type": "message",
        "role": "system",
        "content": f"→ {tool_result[:200]}{'...' if len(tool_result) > 200 else ''}"
    })

    # Continue conversation with tool result AND tools
    llm_messages = conversation.to_llm_format()
    response = await llm.chat(llm_messages, available_tools)
    message = response["choices"][0]["message"]

    # Extract content and tool_calls for next iteration
    assistant_content = message.get("content", "")
    tool_calls = message.get("tool_calls", [])

    if tool_calls:
        print(f"\n🎯 Model requested {len(tool_calls)} more tool call(s)")

    return assistant_content, tool_calls


async def process_tool_calls(
    websocket: WebSocket,
    conversation: Conversation,
    tools: ToolManager,
    assistant_content: str,
    tool_calls: list,
    available_tools: list[dict],
    llm: LLMClient
) -> str:
    """Process tool calls in a loop until model stops requesting them.

    Agentic loop pattern:
    1. Display LLM response
    2. Check for tool_calls
    3. Execute tools and send results back to LLM
    4. Repeat until LLM responds without tool_calls

    Returns:
        Final assistant_content after all tool calls complete
    """
    while tool_calls and tools:
        # Send the assistant's message BEFORE the tool call
        if assistant_content:
            await websocket.send_json({
                "type": "message",
                "role": "assistant",
                "content": assistant_content
            })

        # Add the assistant's tool call message to conversation
        conversation.add_message("assistant", assistant_content or "", tool_call=json.dumps(tool_calls))

        # Execute each tool call
        for tool_call in tool_calls:
            try:
                assistant_content, tool_calls = await execute_single_tool(
                    websocket, conversation, tools, tool_call, available_tools, llm
                )

                if tool_calls:
                    break  # Break inner loop to process new tool calls

            except Exception as e:
                print("\n" + "="*80)
                print(f"❌ TOOL ERROR: {str(e)}")
                print("="*80 + "\n")

                await websocket.send_json({
                    "type": "error",
                    "content": f"Tool error: {str(e)}"
                })
                continue

        # If no more tool calls after processing, break the while loop
        if not tool_calls:
            break

    return assistant_content


async def send_final_response(
    websocket: WebSocket,
    conversation: Conversation,
    message: dict,
    assistant_content: str
):
    """Extract reasoning, send to UI, and send final assistant response."""
    # Clear loading indicator
    await websocket.send_json({
        "type": "loading_done"
    })

    # Extract reasoning - try both methods
    reasoning = extract_reasoning_field(message)
    if not reasoning:
        reasoning, assistant_content = extract_think_tags(assistant_content)

    # Send reasoning trace if present
    if reasoning:
        await websocket.send_json({
            "type": "reasoning",
            "content": reasoning
        })

    # Send final assistant response
    if assistant_content:
        conversation.add_message("assistant", assistant_content)
        await websocket.send_json({
            "type": "message",
            "role": "assistant",
            "content": assistant_content
        })


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
                        available_tools = build_tool_definitions(tools)

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
                            available_tools = []
                    else:
                        response = await llm.chat(llm_messages)

                    message = response["choices"][0]["message"]
                    assistant_content = message.get("content", "")
                    tool_calls = message.get("tool_calls", [])

                    if tool_calls:
                        print(f"\n🎯 Model requested {len(tool_calls)} tool call(s)")
                    else:
                        print("\n⚠️  Model did NOT request any tool calls (no tool_calls field in response)")

                    # Process tool calls in a loop
                    assistant_content = await process_tool_calls(
                        websocket, conversation, tools,
                        assistant_content, tool_calls, available_tools, llm
                    )

                    # Send final response with reasoning
                    await send_final_response(websocket, conversation, message, assistant_content)

                except Exception as e:
                    await websocket.send_json({"type": "loading_done"})
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
