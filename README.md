# minifram

Minimal agent framework for local LLM interaction.

## What it does

- Chat with local models (GLM, etc.) via HTTP
- Execute tools through Model Context Protocol (MCP)
- Spawn autonomous agents with text-based contracts
- Expose agent lifecycle via MCP for external orchestration

## Why

Claude Code is powerful but requires Anthropic API. This runs entirely local with your own models.

## Architecture

```
Browser (WebSocket) ↔ FastAPI Server ↔ Local LLM (HTTP)
                           ↓
                      MCP Tools (stdio)
```

## Quick Start

```bash
# Install
uv sync

# Configure
cp .env.example .env
# Edit .env with your LLM endpoint

# Run
uv run go

# Open http://localhost:8101
```

## Configuration

Edit `.env`:

```
LLM_ENDPOINT=http://localhost:8080/v1/chat/completions
LLM_MODEL=glm-4
```

## MCP Tools

Add to `mcp_config.json`:

```json
{
  "filesystem": {
    "command": "mcp-server-filesystem",
    "args": ["--root", "."]
  }
}
```

## Agent Contracts

Click `[+ Agent]` to spawn a new agent. Define its objective in the contract textarea:

```
Review all Python files in src/ for security issues.
Focus on SQL injection and authentication bypasses.
Create a summary report with findings.
```

The agent runs autonomously until it determines the contract is complete.

## Agent MCP Server

Agents can also be started and managed via MCP tools, allowing external orchestrators (like Claude Code) to spawn agents:

- `agent_start` - Start an agent with a contract
- `agent_status` - Check agent status
- `agent_stop` - Stop a running agent
- `agent_complete` - Signal contract completion with optional payload

See `SPEC_AGENT_MCP.md` for details.

## Development Status

- ✅ Phase 1: Foundation (WebSocket + LLM + UI)
- ✅ Phase 2: Tool Integration (MCP)
- ✅ Phase 3: Agent System
- ✅ Phase 4: Agent MCP Server

See `SPEC.md` for full requirements.

## License

MIT
