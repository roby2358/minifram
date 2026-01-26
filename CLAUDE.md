# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Always confirm with the user before running `git commit` or `git push`.**

## Quick Start

```bash
# Install dependencies
uv sync

# Run the server
uv run go

# Access at http://localhost:8101
```

## Architecture Overview

**minifram** is a minimal agent framework for local LLM interaction. It enables chat with local models, MCP tool execution, and autonomous agent spawning.

### Core Components

```
Browser (WebSocket) ↔ FastAPI Server ↔ Local LLM (HTTP API)
                           ↓
                    MCP Tools (stdio)
```

**Server Flow:**
- `src/foundation/server.py` - FastAPI server with WebSocket endpoint
- `src/foundation/state.py` - In-memory conversation store (Conversation, Message dataclasses)
- `src/models/llm_client.py` - HTTP client for LLM communication (httpx)

**Tool Integration:**
- `src/tools/tool_manager.py` - Manages multiple MCP servers
- `src/tools/mcp_client.py` - JSON-RPC 2.0 client for stdio MCP communication
- `src/mcp/hello_server.py` - Example MCP server for testing

**UI:**
- `src/static/` - Vanilla JS chat interface
  - Split panel: chat (left) + reasoning trace (right)
  - Navigation tabs for chat/tools views
  - WebSocket client in `app.js`

### Agentic Loop Pattern

The core pattern is **LLM → Display → Check tools → Execute → Back to LLM**:

1. Send conversation to LLM with available tools
2. Display LLM response to user
3. Check `tool_calls` field in response
4. Execute requested tools, send results back to LLM
5. Repeat until LLM responds without tool_calls

This loop is implemented in `process_tool_calls()` in server.py.

### MCP Protocol

MCP servers are spawned as subprocesses communicating via stdio using JSON-RPC 2.0:
- `initialize` - Handshake with server capabilities
- `tools/list` - Get available tools and schemas
- `tools/call` - Execute a tool with arguments

Configuration in `mcp_config.json`:
```json
{
  "server_name": {
    "command": "python",
    "args": ["path/to/server.py"]
  }
}
```

### Message Flow (WebSocket)

Client → Server:
- `{type: "message", content: "..."}` - User message

Server → Client:
- `{type: "message", role: "user|assistant|system|tool", content: "..."}` - Display message
- `{type: "reasoning", content: "..."}` - Display in reasoning panel (from `message.reasoning` field or `<think>`/`<thinking>` tags)
- `{type: "loading"}` / `{type: "loading_done"}` - Loading indicator
- `{type: "error", content: "..."}` - Error display

### Configuration

**.env:**
```
LLM_ENDPOINT=http://localhost:11434/v1/chat/completions
LLM_MODEL=glm-4.7-flash
```

**mcp_config.json:** MCP server definitions (see above)

### Code Organization

- `src/foundation/` - Server, state management, static UI files
- `src/models/` - LLM client (HTTP communication)
- `src/tools/` - MCP client and tool manager
- `src/mcp/` - MCP server implementations

### Development Phase Status

- ✅ Phase 1: Foundation (WebSocket + LLM + UI)
- ✅ Phase 2: Tool Integration (MCP)
- ✅ Phase 3: Agent System (autonomous agents with contracts)
- ✅ Phase 4: Agent MCP Server (see `SPEC_AGENT_MCP.md`)

See `SPEC.md` for complete functional requirements.

### Testing MCP Integration

Use `README_MCP_TESTING.md` for instructions on testing MCP servers directly.

### Local Model Setup

- `README_GLM.md` - Running GLM models locally with Ollama
- `README_OpenAI_OSS.md` - Running OpenAI OSS models locally

Models must provide OpenAI-compatible `/v1/chat/completions` endpoint.

### Key Technical Details

**Tool calling graceful degradation:** If the LLM returns 400 on tool call request, the system automatically retries without tools and warns the user once. This handles models that don't support OpenAI tool calling format.

**Reasoning extraction:** Three methods supported:
1. `message.reasoning` field (GLM-4.7-flash)
2. `<think>...</think>` tags in content
3. `<thinking>...</thinking>` tags in content

All are extracted and displayed in the reasoning panel.

**Conversation history:** Stored in-memory using ConversationStore. Each conversation has a unique ID. Messages include role, content, timestamp, and optional tool_call data for reconstruction.
