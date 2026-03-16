# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM (Large Language Model) and returns structured JSON responses. It is the foundation for a more advanced agent with tool usage capabilities (Tasks 2–3).

## LLM Provider

- **Provider**: Qwen Code API (self-hosted via qwen-code-oai-proxy on a VM)
- **Model**: `qwen3-coder-plus`
- **API Format**: OpenAI-compatible `/v1/chat/completions` endpoint

### Why Qwen Code?

- 1000 free requests per day
- Works from Russia without restrictions
- No credit card required
- OpenAI-compatible API for easy integration

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌─────────────┐
│    User     │────▶│   agent.py   │────▶│  Qwen Code API  │────▶│    LLM      │
│  (CLI arg)  │     │  (CLI tool)  │     │   (VM proxy)    │     │ (Qwen 3)    │
└─────────────┘     └──────────────┘     └─────────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  JSON output │
                    │ {answer,     │
                    │  tool_calls} │
                    └──────────────┘
```

## Components

### `agent.py`

The main CLI agent with the following responsibilities:

1. **Argument parsing**: Accepts a question as the first command-line argument using `argparse`.

2. **Configuration loading**: Reads LLM credentials from `.env.agent.secret`:
   - `LLM_API_KEY` — API key for authentication
   - `LLM_API_BASE` — Base URL of the LLM API
   - `LLM_MODEL` — Model name to use

3. **LLM communication**: Makes HTTP POST requests to the LLM API using `httpx`:
   - Endpoint: `{LLM_API_BASE}/chat/completions`
   - Headers: `Authorization: Bearer {LLM_API_KEY}`, `Content-Type: application/json`
   - Payload: `{"model": "{LLM_MODEL}", "messages": [{"role": "user", "content": "<question>"}]}`

4. **Response parsing**: Extracts the answer from `response.choices[0].message.content`.

5. **Output formatting**: Prints JSON to stdout:
   ```json
   {"answer": "<answer>", "tool_calls": []}
   ```

### `.env.agent.secret`

Environment configuration file (gitignored) containing LLM credentials:

```bash
LLM_API_KEY=your-api-key-here
LLM_API_BASE=http://<vm-ip>:<port>/v1
LLM_MODEL=qwen3-coder-plus
```

## How to Run

### Prerequisites

1. Set up Qwen Code API on your VM following [wiki/qwen-code-api.md](wiki/qwen-code-api.md).

2. Copy and configure the environment file:
   ```bash
   cp .env.agent.example .env.agent.secret
   # Edit .env.agent.secret with your VM IP, port, and API key
   ```

### Usage

```bash
# Run with uv
uv run agent.py "What does REST stand for?"

# Or with Python directly (if in virtual environment)
python agent.py "What is the capital of France?"
```

### Output

The agent outputs a single JSON line to stdout:

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

All debug and error messages are printed to stderr.

## Error Handling

- **Timeout**: 60-second timeout for LLM requests
- **Exit codes**: 0 on success, non-zero on error
- **Error messages**: Printed to stderr, not stdout (to preserve JSON output)

## Testing

Run the regression test:

```bash
uv run pytest tests/test_agent_output.py -v
```

## Future Work (Tasks 2–3)

- Add tool support (e.g., `query_api`, `read_file`, `search_code`)
- Implement agentic loop for multi-step reasoning
- Expand system prompt with domain knowledge
- Add more sophisticated output validation
