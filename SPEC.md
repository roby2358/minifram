# minifram - Technical Specification

A minimal agent framework for local LLM interaction with MCP tool support.

## Purpose

Provide a lightweight alternative to Claude Code that runs entirely local. Single dev working with local models (GLM) needs chat interface, tool calling via MCP, and autonomous agent spawning.

## UI Layout

```
+----------------------------------------------------------+
|  minifram                       [Tools ▼]    [+ Agent]   |
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

Tools Panel (dropdown):
+----------------------------------+
| MCP Tools                        |
+----------------------------------+
| ✓ filesystem (active)            |
| ✓ git (active)                   |
| ✗ browser (broken)               |
+----------------------------------+

New Agent Tab (before start):
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
+----------------------------------------------------------+

Agent Tab (running):
+----------------------------------------------------------+
|  Agent: code-reviewer                        [x]        |
+----------------------------------------------------------+
|  Output:                                     [Running]  |
|  +----------------------------------------------------+ |
|  | Reading src/auth.py...                             | |
|  | [Tool: Read src/auth.py]                           | |
|  | Checking for SQL injection...                      | |
|  | [Tool: Grep "SELECT.*%s" --type py]                | |
|  |                                           (scroll) | |
|  +----------------------------------------------------+ |
+----------------------------------------------------------+
```

## Functional Requirements

### Chat Interface

- The application MUST provide a WebSocket-based chat interface
- The application MUST display user messages, assistant responses, and tool calls
- The application MUST support multiple concurrent chat tabs
- Each tab MUST maintain independent conversation history
- Tool calls MUST be displayed with name and parameters, limited to 80 characters with ellipsis
- The application MUST extract and display LLM reasoning in a separate panel
- Reasoning MUST be extracted from `message.reasoning` field, `<think>` tags, or `<thinking>` tags

### LLM Integration

- The application MUST connect to local LLM via HTTP (GLM or compatible)
- The application MUST support multi-turn conversations with context
- The application MUST implement the agentic loop: LLM → tool → LLM
- The model endpoint MUST be configurable

### MCP Tool Integration

- The application MUST implement the Model Context Protocol for tool calling
- The application MUST display a tools panel showing MCP tool status (active/broken)
- The application MUST load MCP server configuration from `mcp_config.json`
- The application MUST support multiple concurrent MCP servers

### Agent Spawning

- The application MUST provide a button to create new agent tabs
- Each agent tab MUST include a contract textarea for defining objectives
- The application MUST provide a [Start Agent] button to begin execution
- The application MUST execute the agent autonomously until contract completion
- The agent MUST determine when its contract is satisfied
- The application MUST display agent progress in a read-only scrollable textarea
- The application MUST write agent output to a timestamped log file

## Non-Functional Requirements

### Architecture

- The backend MUST be implemented in Python
- The application MUST use FastAPI for HTTP/WebSocket handling
- The UI MUST be minimal HTML/JS without heavy frameworks
- The application MUST run entirely on localhost
- The application MUST start with `uv run go`
- The application MUST serve the HTML interface on port 8101

### Performance

- Tool execution MUST not block the UI
- The application MUST handle multiple simultaneous agent executions

### Configuration

- LLM endpoint and model name MUST be configurable via `.env`
- MCP servers MUST be configurable via `mcp_config.json`

## Dependencies

**Backend:**
- Python 3.10+
- FastAPI for HTTP/WebSocket server
- httpx for async LLM API calls
- MCP Python SDK for protocol implementation

**Frontend:**
- Vanilla JavaScript for UI interactions
- WebSocket API for real-time communication
- Minimal CSS for layout

**Tooling:**
- uv for package management

## Technical Choices

### In-Memory State
No persistence overhead. Fast iteration, no schema migration. Restart = fresh start. Exercise left to the reader to add SQLite if needed.

### Local LLM (GLM)
Full control, no API costs, no rate limits. OpenAI-compatible format makes integration straightforward.

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

Each agent tab runs in an independent context with its own conversation history. Agents can run concurrently without interference.

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
- httpx LLM HTTP client
- Simple HTML/JS UI
- Tool panel with status display

### Phase 2: Tool Integration
- MCP protocol implementation
- Tool execution pipeline
- Tool display in chat (80 char limit)
- MCP server configuration from JSON file

### Phase 3: Agent System
- Agent tab creation
- Contract textarea interface
- [Start Agent] button and execution flow
- Autonomous execution loop with read-only output display
- Agent log file writing
- Completion detection
