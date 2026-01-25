# Running OpenAI Open Source Models Locally

Guide to running OpenAI's gpt-oss models locally for minifram.

## What is gpt-oss?

In 2026, OpenAI released their first open-weight language models since GPT-2:
- **gpt-oss-20b**: Small model optimized for edge/consumer hardware (16GB RAM)
- **gpt-oss-120b**: Larger model for better performance (requires more resources)

Both use Apache 2.0 license and Mixture-of-Experts (MoE) architecture for efficient inference.

## Model Specs

### gpt-oss-20b (Recommended)
- **Total parameters**: 21 billion
- **Active per token**: 3.6 billion (MoE)
- **Memory**: 16GB (quantized MXFP4)
- **Best for**: Consumer hardware, RTX 3060+, M1+ Macs

### gpt-oss-120b
- **Total parameters**: 120+ billion
- **Active per token**: ~20 billion (MoE)
- **Memory**: 64GB+ recommended
- **Best for**: High-end workstations, servers

## Option 1: Ollama (Easiest)

Ollama provides the simplest setup for gpt-oss models.

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull gpt-oss-20b
ollama pull gpt-oss:20b

# Or pull gpt-oss-120b (if you have the hardware)
ollama pull gpt-oss:120b

# Run Ollama server (starts on port 11434)
ollama serve
```

Configure minifram `.env`:
```
LLM_ENDPOINT=http://localhost:11434/v1/chat/completions
LLM_MODEL=gpt-oss:20b
```

## Option 2: vLLM (Production-Ready)

vLLM offers better throughput and performance for production deployments.

```bash
# Install vLLM
pip install vllm

# Run gpt-oss-20b with OpenAI-compatible server
python -m vllm.entrypoints.openai.api_server \
    --model openai/gpt-oss-20b \
    --port 8080 \
    --served-model-name gpt-oss-20b \
    --dtype auto \
    --max-model-len 8192
```

Configure minifram `.env`:
```
LLM_ENDPOINT=http://localhost:8080/v1/chat/completions
LLM_MODEL=gpt-oss-20b
```

### vLLM with gpt-oss-120b

For the larger model:

```bash
python -m vllm.entrypoints.openai.api_server \
    --model openai/gpt-oss-120b \
    --port 8080 \
    --served-model-name gpt-oss-120b \
    --dtype auto \
    --tensor-parallel-size 2 \
    --max-model-len 8192
```

## Option 3: Hugging Face Transformers

Direct Python integration for custom use cases.

```bash
pip install transformers torch accelerate
```

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "openai/gpt-oss-20b"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    device_map="auto",
    torch_dtype="auto"
)

# Use with Hugging Face TGI or custom server
```

Then use with a server like [Text Generation Inference](https://github.com/huggingface/text-generation-inference).

## Option 4: LM Studio (GUI)

LM Studio provides a desktop app interface.

1. Download from https://lmstudio.ai
2. Search for "gpt-oss-20b" or "gpt-oss-120b"
3. Download the model
4. Start the local server (default port 1234)
5. Enable "OpenAI Compatible Server" in settings

Configure minifram `.env`:
```
LLM_ENDPOINT=http://localhost:1234/v1/chat/completions
LLM_MODEL=gpt-oss-20b
```

## Hardware Requirements

### gpt-oss-20b
- **Minimum**: 16GB RAM/VRAM (quantized)
- **Recommended**: 24GB for better performance
- **GPU**: RTX 3060 12GB, RTX 4060 Ti 16GB, or better
- **CPU**: Works but 10-50x slower

### gpt-oss-120b
- **Minimum**: 64GB RAM/VRAM
- **Recommended**: 80GB+ for production
- **GPU**: RTX 6000 Ada, A100, H100, or multi-GPU setup
- **Multi-GPU**: Use `--tensor-parallel-size 2` or higher

## Testing the Connection

Verify gpt-oss is working:

```bash
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss:20b",
    "messages": [
      {"role": "user", "content": "Write a Python hello world"}
    ]
  }'
```

Expected response:
```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Here's a simple Python hello world program:\n\n```python\nprint(\"Hello, World!\")\n```"
      }
    }
  ]
}
```

## Quantization Options

For lower memory usage, use quantized versions:

### Ollama (auto-quantized)
```bash
# Already quantized when you pull
ollama pull gpt-oss:20b
```

### vLLM with custom quantization
```bash
# 8-bit quantization
python -m vllm.entrypoints.openai.api_server \
    --model openai/gpt-oss-20b \
    --quantization bitsandbytes \
    --load-format bitsandbytes

# 4-bit quantization (even lower memory)
python -m vllm.entrypoints.openai.api_server \
    --model openai/gpt-oss-20b \
    --quantization gptq
```

## Performance Comparison

| Model | Params | Active | Memory | Speed | Use Case |
|-------|--------|--------|--------|-------|----------|
| gpt-oss-20b | 21B | 3.6B | 16GB | Fast | Consumer hardware |
| gpt-oss-120b | 120B+ | ~20B | 64GB+ | Medium | Production/servers |

## Troubleshooting

**Model download fails**
- Check internet connection
- Try alternative mirror: `export HF_ENDPOINT=https://hf-mirror.com`
- Download manually from Hugging Face

**Out of memory**
- Use gpt-oss-20b instead of 120b
- Enable quantization: `--quantization bitsandbytes`
- Reduce context: `--max-model-len 4096`
- Close other GPU applications

**Slow inference**
- Check GPU utilization: `nvidia-smi`
- Verify CUDA is available: `python -c "import torch; print(torch.cuda.is_available())"`
- Consider CPU offloading for partial GPU memory

**Connection refused**
- Verify server is running
- Check port isn't blocked: `lsof -i :11434`
- Try `127.0.0.1` instead of `localhost`

## Why gpt-oss?

**Advantages:**
- Apache 2.0 license (fully open)
- Optimized for consumer hardware (20b model)
- Native quantization support (MXFP4)
- Strong coding and reasoning performance
- Official OpenAI quality

**Trade-offs:**
- Larger than 7B models (more memory)
- Newer, less ecosystem support than Llama
- Still requires decent GPU for best performance

## Next Steps

Once gpt-oss is running:

1. Copy `.env.example` to `.env` (or edit existing)
2. Set `LLM_ENDPOINT` to your server URL
3. Set `LLM_MODEL` to `gpt-oss:20b` or `gpt-oss-20b`
4. Run `uv run go` to start minifram
5. Open http://localhost:8101

The chat interface will connect to your local OpenAI open source model.

## Resources

- [OpenAI gpt-oss announcement](https://openai.com/index/introducing-gpt-oss/)
- [Hugging Face model page](https://huggingface.co/openai/gpt-oss-20b)
- [vLLM documentation](https://docs.vllm.ai/)
- [Ollama models](https://ollama.com/library)

Sources:
- [Introducing gpt-oss | OpenAI](https://openai.com/index/introducing-gpt-oss/)
- [Open models by OpenAI](https://openai.com/open-models/)
- [How to Run AI Models Locally (2026)](https://www.clarifai.com/blog/how-to-run-ai-models-locally-2025-tools-setup-tips)
