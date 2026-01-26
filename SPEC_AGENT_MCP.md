# Agent MCP Server - Technical Specification

Expose agent lifecycle tools via MCP, enabling external clients to spawn agents and agents to signal completion.

## Architecture

```
+------------------+          +----------------------------------+
|  Claude Desktop  |   SSE    |           minifram               |
|  Claude Code     |--------->|  +------------+  +-------------+ |
|  Other Clients   |          |  | FastAPI    |  | AgentStore  | |
+------------------+          |  | /mcp       |  | (shared)    | |
                              |  +-----+------+  +------+------+ |
                              |        |                |        |
                              |        v                |        |
                              |  +------------+         |        |
                              |  | FastMCP    |---------+        |
                              |  | Tools      |                  |
                              |  +------------+                  |
                              |        ^                         |
                              |        |                         |
                              |  +-----+------+                  |
                              |  | Agent Loop |                  |
                              |  | (internal) |                  |
                              |  +------------+                  |
                              +----------------------------------+
```

## Functional Requirements

### MCP Server

- Expose MCP endpoint at `/mcp` via HTTP/SSE
- Use FastMCP 2.x, sharing state with FastAPI
- Combine MCP lifespan with existing app lifespan
- Handle concurrent connections

### Tool: agent_start

**Parameters:** `contract: string`

**Behavior:**
- Create agent, set contract, start execution asynchronously
- Return immediately (don't wait for completion)

**Response:** `{agent_id, status: "running", started_at}`

### Tool: agent_status

**Parameters:** `agent_ids: string[]`

**Response:** List of status objects:
```
{
  agent_id: string,
  status: "ready" | "running" | "stopped" | "completed",
  started_at: string,
  completed_at?: string,      // when completed
  stopped_at?: string,        // when stopped
  summary?: string,           // when completed
  payload_size?: number,      // uncompressed bytes, when payload exists
  payload_url?: string,       // http://localhost:8101/api/agents/{id}/payload
  error?: string              // when agent not found
}
```

For running agents, SHOULD include truncated preview of recent output.

### Tool: agent_complete

**Parameters:** `agent_id: string`, `summary: string`, `payload?: string`

**Behavior:**
- Transition status to "completed"
- Store summary and payload (gzip-compressed)
- Prevent further LLM requests
- Idempotent if already completed

**Response:** `{status: "completed", started_at, completed_at}`

Called by the agent itself to signal completion.

### Tool: agent_stop

**Parameters:** `agent_id: string`

**Behavior:**
- Prevent further LLM requests (in-flight requests complete normally)
- Transition status to "stopped"
- Idempotent if already stopped/completed

**Response:** `{status: "stopped", started_at, stopped_at}`

### Agent System Prompt

- Provide agent's `agent_id` for self-reference
- Instruct agents to call `agent_complete` when finished
- Support `[CONTRACT COMPLETE]` as fallback, auto-invoke agent_complete

### Payload Endpoint

`GET /api/agents/{agent_id}/payload`

- Return gzip-compressed payload with `Content-Encoding: gzip`
- 404 if agent or payload not found
- 406 if client doesn't send `Accept-Encoding: gzip`

### Client Configuration

```json
{
  "minifram": {
    "url": "http://localhost:8101/mcp"
  }
}
```

## Non-Functional Requirements

- agent_start MUST return within 100ms
- agent_status MUST return within 50ms
- MCP server MUST NOT block the event loop
- Existing WebSocket and REST APIs MUST continue to function
- All timestamps are ISO 8601 formatted

## Implementation Notes

**State sharing:** FastMCP tools share AgentStore directly with FastAPI - same process, no IPC.

**Async execution:** agent_start kicks off background task, returns immediately. Callers poll agent_status.

**Payload storage:** Stored as gzip-compressed bytes in memory (~5-10x savings for text). Not persisted to disk.

**Large payloads:** The payload parameter works for small-to-medium data. For large work products, agents should use file editing tools instead. Future extension: an `append_payload` tool for incremental building if needed.

## Error Handling

- Agent not found → error in status object / 404
- Already completed/stopped → idempotent success
- No payload → 404
- No gzip support → 406
- MCP protocol errors → handled by FastMCP

## Out of Scope

- Timeout parameters
- Output streaming via MCP
- Authentication
- Rate limiting
