# minifram - Technical Specification

A minimal agent framework for local LLM interaction with MCP tool support.

## Purpose

Provide a lightweight alternative to Claude Code that runs entirely local. Single dev working with local models (GLM) needs chat interface, tool calling via MCP, and autonomous agent spawning.

## UI Layout

```
+----------------------------------------------------------+
|  minifram                                    [+ Agent]   |
+----------------------------------------------------------+
| [Chat] [Agent-1] [Agent-2]                              |
+----------------------------------------------------------+
|                                                          |
|  System: Connected to GLM                               |
|  User: Fix the bug in auth.py                           |
|  Assistant: Reading auth.py...                          |
|  [Tool: Read auth.py]                                   |
|  Assistant: Found the issue on line 42...               |
|                                                          |
+----------------------------------------------------------+
|  [Message input...................................] [>]  |
+----------------------------------------------------------+

New Agent Tab:
+----------------------------------------------------------+
|  Agent: code-reviewer                        [x]        |
+----------------------------------------------------------+
|  Contract:                                              |
|  +----------------------------------------------------+ |
|  | Review all Python files for security issues.       | |
|  | Focus on SQL injection and XSS vulnerabilities.    | |
|  +----------------------------------------------------+ |
|                                                          |
|  [Start Agent]                                          |
|                                                          |
|  Agent output appears here after start...               |
+----------------------------------------------------------+
```

## Functional Requirements

### Chat Interface

- The application MUST provide a WebSocket-based chat interface
- The application MUST display user messages, assistant responses, and tool calls
- The application MUST support multiple concurrent chat tabs
- Each tab MUST maintain independent conversation history
- The application MUST persist conversations to SQLite

### LLM Integration

- The application MUST connect to local LLM via HTTP (GLM or compatible)
- The application MUST support multi-turn conversations with context
- The application MUST implement the agentic loop: LLM → tool → LLM
- The application SHOULD stream responses when the model supports it
- The model endpoint MUST be configurable

### MCP Tool Integration

- The application MUST implement the Model Context Protocol for tool calling
- The application MUST execute tools requested by the LLM
- The application MUST return tool results to the LLM for continued processing
- The application MUST display available MCP tools in the UI
- The application MUST allow configuration of MCP server connections
- The application SHOULD support multiple concurrent MCP servers

### Agent Spawning

- The application MUST provide a button to create new agent tabs
- Each agent tab MUST include a contract textarea for defining objectives
- The application MUST execute the agent autonomously until contract completion
- The agent MUST have access to the same tools as the main chat
- The agent MUST determine when its contract is satisfied
- The application SHOULD display agent progress and tool usage

### State Management

- The application MUST maintain conversation history in memory during runtime
- The application MUST load MCP server configurations from `mcp_config.json`
- Agent output SHOULD be written to files when appropriate
- The application MAY clear state on restart

## Non-Functional Requirements

### Architecture

- The backend MUST be implemented in Python
- The application SHOULD use FastAPI for HTTP/WebSocket handling
- The UI MAY be minimal HTML/JS without heavy frameworks
- The application MUST run entirely on localhost
- The application MUST start with `uv run go`
- The application MUST serve the HTML interface on port 8101

### Performance

- The application SHOULD respond to user input within 100ms
- Tool execution MUST not block the UI
- The application SHOULD handle multiple simultaneous agent executions

### Configuration

- The application MUST support configuration via environment variables or config file
- LLM endpoint, model name, and API format MUST be configurable
- The application MAY provide UI for editing configuration

## Dependencies

**Backend:**
- Python 3.10+
- FastAPI for HTTP/WebSocket server
- httpx or requests for LLM API calls
- MCP Python SDK for protocol implementation

**Frontend:**
- Vanilla JavaScript for UI interactions
- WebSocket API for real-time communication
- Minimal CSS for layout

**Tooling:**
- uv for package management

## Technical Choices

### Python + FastAPI
Python for rapid iteration and MCP SDK availability. FastAPI provides built-in WebSocket support and async handling. Rust port possible later if performance matters.

### In-Memory State (Phases 1-3)
No persistence overhead. State lives in Python dicts and lists. Fast iteration, no schema migration headaches. Restart = fresh start.

### Vanilla JS
No build step, no framework bloat. WebSocket and DOM APIs are enough for the simple UI requirements.

### Local LLM (GLM)
Full control, no API costs, no rate limits. OpenAI-compatible format makes integration straightforward.

### MCP Python SDK
Official protocol implementation. Handles tool schema translation and message format complexity.

### uv
Fast package management, simpler than pip+venv. Lock file ensures reproducible builds. Script aliases in `pyproject.toml` provide clean entry point (`uv run go`).

## Implementation Notes

### Contract Evaluation

The agent determines contract completion through LLM self-evaluation. After each tool execution cycle, the LLM assesses whether the contract objective is met. No external validation logic required.

### MCP Protocol

The MCP SDK handles protocol details. The application wraps available tools as MCP-compatible functions and lets the SDK manage the request/response cycle with the LLM.

### Local LLM Format

GLM and similar local models use OpenAI-compatible API format. The application translates between this format and MCP tool schemas as needed.

### WebSocket Message Format

All messages (user, assistant, tool calls, tool results) flow through WebSocket as JSON. The client maintains display state; server maintains conversation state in memory.

### Agent Isolation

Each agent tab runs in an independent context with its own conversation history in memory. Agents can run concurrently without interference.

### Flat File Storage

MCP configuration lives in `mcp_config.json`. Environment config in `.env`. Agent outputs written to files as needed. No database schemas to maintain.

## Error Handling

The application MUST handle these error conditions:

- LLM server unreachable or timeout
- Invalid tool call parameters from LLM
- MCP server connection failure
- Tool execution errors
- File write failures (config, agent output)
- WebSocket disconnection
- Malformed messages from client or LLM

## Development Phases

### Phase 1: Foundation
- WebSocket chat server
- In-memory conversation storage
- Basic LLM HTTP client
- Simple HTML/JS UI

### Phase 2: Tool Integration
- MCP protocol implementation
- Tool execution pipeline
- Tool display in UI
- MCP server configuration from JSON file

### Phase 3: Agent System
- Agent tab creation
- Contract interface
- Autonomous execution loop
- Completion detection

### Phase 4: Persistence (Optional)
- SQLite conversation history
- Session resumption
- Agent contract/result storage
- Conversation search/replay
