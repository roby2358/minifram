# Running GLM Locally

Guide to running ChatGLM locally for minifram.

## What is GLM?

ChatGLM is a bilingual (Chinese-English) conversational language model developed by Tsinghua University and Zhipu AI. GLM-4.7 is the latest version (2026) with strong coding and reasoning capabilities, achieving 73.8% on SWE-bench and 41% on Terminal Bench 2.0.

## Option 1: Ollama (Easiest)

Ollama provides a simple way to run local models with OpenAI-compatible API.

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull GLM-4.7-flash (30B MoE, ~23GB - RECOMMENDED for tool calling)
ollama pull glm-4.7-flash

# Or pull GLM-4 (9B parameters, ~5GB - smaller, no tool support)
ollama pull glm4

# Run with API server (starts on port 11434)
ollama serve
```

Configure minifram `.env`:
```
LLM_ENDPOINT=http://localhost:11434/v1/chat/completions
LLM_MODEL=glm-4.7-flash
```

**Note**: GLM-4.7-flash supports tool calling (required for MCP integration). GLM-4 does not.

## Option 2: vLLM (Production-Ready)

vLLM offers better performance and throughput for production use.

```bash
# Install vLLM
pip install vllm

# Run GLM-4.7 with OpenAI-compatible server
python -m vllm.entrypoints.openai.api_server \
    --model THUDM/glm-4-9b-chat \
    --port 8080 \
    --served-model-name glm-4.7
```

Configure minifram `.env`:
```
LLM_ENDPOINT=http://localhost:8080/v1/chat/completions
LLM_MODEL=glm-4.7
```

### vLLM Hardware Requirements

- **GLM-4-9B**: 16GB VRAM minimum
- **GLM-4.7-flash**: 24GB+ VRAM recommended (30B MoE model)
- CPU-only mode available but very slow

## Option 3: LM Studio (GUI)

LM Studio provides a desktop app for running local models.

1. Download from https://lmstudio.ai
2. Search for and download "GLM-4.7" or "GLM-4"
3. Start the local server (default port 1234)
4. Enable "OpenAI Compatible Server" in settings

Configure minifram `.env`:
```
LLM_ENDPOINT=http://localhost:1234/v1/chat/completions
LLM_MODEL=glm-4.7-flash
```

## Alternative Models

If GLM doesn't work or you want alternatives:

### Qwen (Recommended for coding)
```bash
# Ollama
ollama pull qwen2.5-coder:7b

# vLLM
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-Coder-7B-Instruct \
    --port 8080
```

### DeepSeek Coder
```bash
# Ollama
ollama pull deepseek-coder-v2:16b

# vLLM
python -m vllm.entrypoints.openai.api_server \
    --model deepseek-ai/deepseek-coder-6.7b-instruct \
    --port 8080
```

### Llama 3 (General purpose)
```bash
# Ollama
ollama pull llama3.1:8b

# vLLM
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --port 8080
```

## Model Comparison

| Model | Size | Tool Support | Memory | Best For |
|-------|------|--------------|--------|----------|
| **glm-4.7-flash** | 30B MoE | ✅ Yes | 16-24GB | **Recommended** - Full MCP tool support |
| glm4 | 9B | ❌ No | 8-16GB | Smaller, basic chat only |

## Testing the Connection

Verify your local model is working:

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-4.7-flash",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

Expected response:
```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      }
    }
  ]
}
```

## Troubleshooting

**Connection refused**
- Check if the model server is running
- Verify the port matches your `.env` configuration
- Try `http://127.0.0.1` instead of `localhost`

**Out of memory**
- Use a smaller model (7B instead of 9B)
- Reduce context length with `--max-model-len 2048`
- Enable CPU offloading if available

**Slow responses**
- Check GPU utilization with `nvidia-smi`
- Reduce batch size or concurrent requests
- Consider quantized models (4-bit or 8-bit)

**Model not found**
- Verify model name matches server configuration
- Check vLLM/Ollama logs for exact model name
- Use `ollama list` to see available models

## Performance Tips

- **GPU required**: CPU-only inference is 10-100x slower
- **Memory**: GLM-4.7-flash needs 16GB minimum, 24GB recommended
- **Apple Silicon**: 16GB unified memory works with 4-bit quantization and 2-4K context
- **Context**: GLM-4.7 supports up to 200K tokens but uses more memory
- **MoE advantage**: Only activates 3B parameters per token despite being 30B total

## Tool Calling with GLM-4.7

GLM-4.7-flash fully supports OpenAI function calling format, enabling MCP tool integration:

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-4.7-flash",
    "messages": [{"role": "user", "content": "Say hello to Alice"}],
    "tools": [{
      "type": "function",
      "function": {
        "name": "hello",
        "description": "Says hello to a person",
        "parameters": {
          "type": "object",
          "properties": {
            "name": {"type": "string"}
          }
        }
      }
    }]
  }'
```

The model will respond with a tool call, which minifram executes via MCP.

## Next Steps

Once your local model is running:

1. Edit `.env` to set `LLM_MODEL=glm-4.7-flash`
2. Run `uv run go` to start minifram
3. Open http://localhost:8101
4. Try: "Say hello to Alice" to test tool calling
5. Click "tools" tab to see available MCP tools

The chat interface should now connect to your local model with full MCP integration.
