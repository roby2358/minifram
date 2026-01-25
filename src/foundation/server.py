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

# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
async def startup():
    """Initialize LLM client on startup."""
    global llm
    llm = LLMClient(endpoint=LLM_ENDPOINT, model=LLM_MODEL)
    print(f"🚀 minifram starting on http://localhost:{PORT}")
    print(f"📡 LLM endpoint: {LLM_ENDPOINT}")
    print(f"🤖 Model: {LLM_MODEL}")


@app.on_event("shutdown")
async def shutdown():
    """Close LLM client on shutdown."""
    if llm:
        await llm.close()


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
    """Get MCP tool status (placeholder for Phase 2)."""
    # Phase 2: Load from mcp_config.json and check status
    return {"tools": []}


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

                # Get LLM response
                try:
                    llm_messages = conversation.to_llm_format()
                    response = await llm.chat(llm_messages)

                    # Extract assistant message
                    assistant_content = response["choices"][0]["message"]["content"]

                    # Add assistant message to conversation
                    conversation.add_message("assistant", assistant_content)

                    # Send assistant response
                    await websocket.send_json({
                        "type": "message",
                        "role": "assistant",
                        "content": assistant_content
                    })

                except Exception as e:
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
