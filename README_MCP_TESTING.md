# Testing MCP Integration

Guide to testing Phase 2: MCP Tool Integration

## What Was Implemented

Phase 2 adds:
- MCP client for connecting to MCP servers via stdio
- Tool manager for handling multiple MCP servers
- Agentic loop: LLM → tool → LLM
- Tool panel in UI showing server status
- Hello world MCP server for testing

## Hello World MCP Server

A simple test server with two tools:
- `hello`: Greets a person by name
- `echo`: Echoes back a message

Located at: `src/mcp/hello_server.py`

## Quick Test

1. **Start minifram**:
```bash
uv run go
```

2. **Check startup logs**:
```
✅ MCP server started: hello (2 tools)
🚀 minifram starting on http://localhost:8101
🔧 Tools loaded: 2
```

3. **Open the UI**: http://localhost:8101

4. **Click "Tools ▼"** to see:
```
MCP Tools
✓ hello (2 tools)
```

5. **Test tool calling** (if your LLM supports it):
```
User: Say hello to Alice
Assistant: [calls hello tool]
[Tool: hello name=Alice]
Assistant: Hello, Alice! 👋
```

## Testing the Hello Server Directly

You can test the MCP server independently:

```bash
# Run the server
python src/mcp/hello_server.py
```

Then send JSON-RPC commands via stdin:

```bash
# Initialize
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python src/mcp/hello_server.py

# List tools
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | python src/mcp/hello_server.py

# Call hello tool
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"hello","arguments":{"name":"World"}}}' | python src/mcp/hello_server.py
```

Expected response from hello:
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Hello, World! 👋"
      }
    ]
  }
}
```

## Configuration

MCP servers are configured in `mcp_config.json`:

```json
{
  "hello": {
    "command": "python",
    "args": ["src/mcp/hello_server.py"]
  }
}
```

### Adding More Servers

See `mcp_config.json.example` for additional server examples:

```json
{
  "hello": {
    "command": "python",
    "args": ["src/mcp/hello_server.py"]
  },
  "filesystem": {
    "command": "mcp-server-filesystem",
    "args": ["--root", "."]
  }
}
```

## Architecture

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ WebSocket
┌──────▼──────────────────┐
│   FastAPI Server        │
│  ┌──────────────────┐   │
│  │ Tool Manager     │   │
│  └────┬─────────────┘   │
│       │                 │
│  ┌────▼─────┐  ┌──────┐ │
│  │MCP Client│  │ LLM  │ │
│  └────┬─────┘  └──────┘ │
└───────┼──────────────────┘
        │ stdio
   ┌────▼────────┐
   │ MCP Server  │
   │ (hello)     │
   └─────────────┘
```

## Tool Call Flow

1. User sends message
2. Server sends message + tool definitions to LLM
3. LLM responds with tool call
4. Server executes tool via MCP
5. Server sends tool result back to LLM
6. LLM generates final response
7. Server sends response to user

## Troubleshooting

**Server shows "broken" status**
- Check that Python is available: `which python`
- Verify hello_server.py is executable: `ls -l src/mcp/hello_server.py`
- Check logs for error messages

**No tools showing up**
- Verify `mcp_config.json` exists and is valid JSON
- Check server startup logs for errors
- Try running hello_server.py manually

**LLM doesn't call tools**
- Not all models support tool calling
- Ollama requires models with tool/function calling support
- Try: `ollama pull mistral` (has tool support)
- Or use OpenAI-compatible models with function calling

**Tool call fails**
- Check MCP server logs (stderr)
- Verify tool arguments match schema
- Test server directly using echo commands above

## Model Compatibility

**Models with tool support:**
- ✅ gpt-oss-20b (OpenAI)
- ✅ mistral (Ollama)
- ✅ qwen2.5-coder (has function calling)
- ✅ llama3.1 (with proper prompting)

**Models without tool support:**
- ❌ glm4 (may not support OpenAI tool format)
- ❌ older llama2 models

If your model doesn't support tools, the LLM will just respond normally without calling tools.

## Next Steps

Phase 3 will add:
- Agent spawning UI
- Contract-based autonomous execution
- Agent log files

For now, test the tool integration with the hello server and verify the agentic loop works with your model.

## Writing Your Own MCP Server

See `src/mcp/hello_server.py` as a template. Key requirements:

1. **Stdio communication**: Read JSON-RPC from stdin, write to stdout
2. **Initialize method**: Return server info and capabilities
3. **tools/list method**: Return available tools with schemas
4. **tools/call method**: Execute tool and return result

The MCP protocol uses JSON-RPC 2.0 format. Each message must be valid JSON on a single line.
