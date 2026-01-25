# Running GLM Locally

Guide to running ChatGLM locally for minifram.

## What is GLM?

ChatGLM is a bilingual (Chinese-English) conversational language model developed by Tsinghua University and Zhipu AI. GLM-4 is the latest version with strong coding and reasoning capabilities.

## Option 1: Ollama (Easiest)

Ollama provides a simple way to run local models with OpenAI-compatible API.

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull GLM-4 (9B parameters, ~5GB)
ollama pull glm4

# Run with API server (starts on port 11434)
ollama serve
```

Configure minifram `.env`:
```
LLM_ENDPOINT=http://localhost:11434/v1/chat/completions
LLM_MODEL=glm4
```

## Option 2: vLLM (Production-Ready)

vLLM offers better performance and throughput for production use.

```bash
# Install vLLM
pip install vllm

# Run GLM-4 with OpenAI-compatible server
python -m vllm.entrypoints.openai.api_server \
    --model THUDM/glm-4-9b-chat \
    --port 8080 \
    --served-model-name glm-4
```

Configure minifram `.env`:
```
LLM_ENDPOINT=http://localhost:8080/v1/chat/completions
LLM_MODEL=glm-4
```

### vLLM Hardware Requirements

- **Minimum**: 16GB VRAM (for GLM-4-9B)
- **Recommended**: 24GB+ VRAM for better performance
- CPU-only mode available but very slow

## Option 3: LM Studio (GUI)

LM Studio provides a desktop app for running local models.

1. Download from https://lmstudio.ai
2. Search for and download "GLM-4" or "ChatGLM3"
3. Start the local server (default port 1234)
4. Enable "OpenAI Compatible Server" in settings

Configure minifram `.env`:
```
LLM_ENDPOINT=http://localhost:1234/v1/chat/completions
LLM_MODEL=glm-4-9b-chat
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

## Testing the Connection

Verify your local model is working:

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-4",
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
- **Memory**: Allocate at least 2GB more than model size
- **Context**: Longer context = slower responses
- **Batch size**: Increase for multiple concurrent requests

## Next Steps

Once your local model is running:

1. Copy `.env.example` to `.env`
2. Set `LLM_ENDPOINT` to your model server URL
3. Set `LLM_MODEL` to match the model name
4. Run `uv run go` to start minifram
5. Open http://localhost:8101

The chat interface should now connect to your local model.
