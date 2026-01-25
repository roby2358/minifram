# minifram

Minimal agent framework for local LLM interaction.

## What it does

- Chat with local models (GLM, etc.) via HTTP
- Execute tools through Model Context Protocol (MCP)
- Spawn autonomous agents with text-based contracts
- Persist conversations in SQLite

## Why

Claude Code is powerful but requires Anthropic API. This runs entirely local with your own models.

## Architecture

```
Browser (WebSocket) ↔ FastAPI Server ↔ Local LLM (HTTP)
                           ↓
                      SQLite + MCP Tools
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

## Development Status

Work in progress. See `SPEC.md` for full requirements.

Current phase: Foundation (WebSocket + LLM + SQLite)

## License

MIT
