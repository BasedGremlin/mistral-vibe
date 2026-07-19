# Local AI Model Guide: What to Run and Why

## Model Selection Framework

Ask three questions:
1. What task? (code, creative, chat, embeddings)
2. How much RAM? (GPU VRAM or CPU RAM)
3. Online or offline? (download now vs. later)

## The Quantization Trade-off

Quantization compresses model weights:
- Full (F16): highest quality, 2x model size in RAM
- Q8_0: ~5% quality loss, half the size of F16
- Q4_K_M: ~8-10% quality loss, ~1/4 the size — **sweet spot for USB**
- Q2_K: ~20% quality loss, very small — emergency use

**Rule of thumb**: Use Q4_K_M for everything on a 30GB USB.

## Models Worth Having (all fit in <6GB)

### General Intelligence
**dolphin3:8b-llama3.1-q4_K_M** (4.9 GB)
- Based on Llama 3.1 8B, fine-tuned for instruction following
- Uncensored (no system-prompt refusals)
- Best for: general chat, creative writing, reasoning, research
- Pull: `ollama pull dolphin3:8b-llama3.1-q4_K_M`

### Code Generation
**qwen2.5-coder:7b-instruct-q4_K_M** (4.7 GB)
- Alibaba's Qwen 2.5 Coder, specialized for code
- Excellent at GDScript, Python, JavaScript
- Supports function calling and structured output
- Pull: `ollama pull qwen2.5-coder:7b-instruct-q4_K_M`

### Embeddings (RAG)
**nomic-embed-text** (274 MB)
- Purpose-built embedding model
- 768-dimension vectors, strong recall
- Required by the WORDLIB RAG system
- Pull: `ollama pull nomic-embed-text`

## System Prompts Matter

The same model with different system prompts is almost a different model.

```python
# General assistant
system = "You are a helpful, direct assistant. Be concise and accurate."

# Code reviewer
system = """You are an expert code reviewer. When reviewing code:
- Point out bugs and security issues first
- Suggest specific improvements with examples
- Explain the WHY behind each suggestion
- Be direct, not diplomatic"""

# Game design advisor
system = """You are an experienced game designer specializing in indie games.
You balance creativity with practical constraints of small teams and limited budgets.
Always consider: player experience, development effort, and scope."""
```

## Temperature Guide

- **0.0-0.2**: Deterministic, factual, code (use for code generation)
- **0.3-0.5**: Balanced, slightly creative (use for most tasks)
- **0.6-0.8**: More creative, less predictable (use for brainstorming)
- **0.9-1.0**: Highly creative, sometimes incoherent (use sparingly)

## Context Window Limits

| Model | Context | Practical limit |
|-------|---------|-----------------|
| dolphin3 8B | 131K | ~40K (RAM limits) |
| qwen2.5-coder 7B | 32K | ~16K |

On USB: lower context = faster response. Use 4096 as default.

## RAG vs. Long Context

**Use RAG when**: documents are large, you have many docs, offline use
**Use long context when**: single document analysis, code review of full files

RAG with nomic-embed-text + dolphin3 = best offline knowledge retrieval.
Long context with dolphin3 = best for single-document deep analysis.

## Prompt Engineering Quick Reference

```python
# Chain of thought (better reasoning)
prompt = "Think through this step by step: " + question

# Few-shot (show examples)
prompt = f"""
Example: [input] -> [output]
Example: [input] -> [output]
Now do: {user_input}"""

# Structured output (JSON)
prompt = f"""Answer in JSON: {{"answer": ..., "confidence": 0-1, "reasoning": ...}}
Question: {question}"""

# Role + task + format
prompt = f"""
Role: Expert Python developer
Task: {task}
Format: Code block with comments, then brief explanation
"""
```
