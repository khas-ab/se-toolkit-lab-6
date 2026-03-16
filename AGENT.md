# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM (Large Language Model) with tool-calling capabilities. It can read documentation files, navigate the project wiki, query the backend API, and answer questions with proper source citations.

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
                    │  source,     │
                    │  tool_calls} │
                    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Backend API │
                    │  (query_api) │
                    └──────────────┘
```

## Components

### `agent.py`

The main CLI agent with the following responsibilities:

1. **Argument parsing**: Accepts a question as the first command-line argument using `argparse`.

2. **Configuration loading**: Reads environment variables from `.env.agent.secret` and `.env.docker.secret`:
   - `LLM_API_KEY` — API key for LLM provider authentication
   - `LLM_API_BASE` — Base URL of the LLM API
   - `LLM_MODEL` — Model name to use
   - `LMS_API_KEY` — Backend API key for `query_api` authentication
   - `AGENT_API_BASE_URL` — Base URL for backend API (default: `http://localhost:42002`)

3. **Tool definitions**: Defines three tools as function-calling schemas:
   - `read_file` — Read a file from the project repository
   - `list_files` — List files and directories at a given path
   - `query_api` — Query the backend API with authentication

4. **Agentic loop**: Implements the reasoning loop:
   - Send user question + tool definitions to LLM
   - If LLM responds with `tool_calls`: execute tools, append results, repeat
   - If LLM responds with text answer: extract answer and source, output JSON
   - Maximum 10 tool calls per question

5. **Path security**: Validates all file paths to prevent directory traversal attacks

6. **Output formatting**: Prints JSON to stdout with `answer`, `source`, and `tool_calls` fields

## Tools

### `read_file`

Reads a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as a string, or an error message if the file doesn't exist or is invalid.

**Security:** Validates that the resolved path is within the project directory. Rejects paths with `../` traversal.

### `list_files`

Lists files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing of entry names, or an error message if the path is invalid.

**Security:** Validates that the resolved path is within the project directory.

### `query_api`

Queries the backend API to get data from the running system.

**Parameters:**
- `method` (string, required): HTTP method (GET, POST, PUT, DELETE)
- `path` (string, required): API endpoint path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests
- `auth` (boolean, optional, default=true): Whether to authenticate with API key. Set to `false` to test unauthenticated access.

**Returns:** JSON string with `status_code` and `body`, or an error message.

**Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret` sent as `Authorization: Bearer <key>` header.

**Example usage:**
```bash
# Query with authentication (default)
uv run agent.py "How many items are in the database?"

# Query without authentication (for testing)
# The LLM will automatically set auth=false for questions like:
# "What status code does /items/ return without authentication?"
```

## Tool Selection Strategy

The system prompt guides the LLM to choose the right tool based on the question type:

| Question Type | Example | Tool(s) |
|--------------|---------|---------|
| Wiki/documentation | "According to the wiki...", "What does the project say..." | `list_files`, `read_file` on `wiki/` |
| Source code | "What framework does the backend use?", "Read the source code..." | `read_file` on `backend/` |
| Data queries | "How many items...", "Query the API..." | `query_api` |
| Error diagnosis | "What error do you get...", "Find the bug" | `query_api` first, then `read_file` |
| Authentication testing | "without authentication header" | `query_api` with `auth=false` |

### Decision Flow

```
User question
    │
    ├── Wiki/Documentation? ──→ list_files → read_file → answer
    │
    ├── Source Code? ──────────→ read_file (backend/) → answer
    │
    ├── Data Query? ───────────→ query_api → answer
    │
    └── Error Diagnosis? ──────→ query_api → read_file → answer
```

## Authentication

The agent uses two distinct API keys:

1. **`LLM_API_KEY`** (in `.env.agent.secret`): Authenticates with the LLM provider (Qwen Code API)
2. **`LMS_API_KEY`** (in `.env.docker.secret`): Authenticates with the backend API for `query_api`

The backend expects the API key in the `Authorization: Bearer <key>` header format.

## Path Security Implementation

```python
def validate_path(path: str) -> Path | None:
    """Validate that a path is within the project directory."""
    project_root = Path.cwd().resolve()
    try:
        full_path = (project_root / path).resolve()
        if not str(full_path).startswith(str(project_root)):
            return None  # Path escapes project directory
        return full_path
    except Exception:
        return None
```

This prevents:
- Reading files outside the project (e.g., `/etc/passwd`)
- Directory traversal attacks (e.g., `../../../secret.txt`)

## Agentic Loop

The agentic loop enables multi-step reasoning:

```
1. User asks: "How many items are in the database?"
2. Agent sends question + tool definitions to LLM
3. LLM decides: "I need to query the API" → calls query_api(GET, /items/)
4. Agent executes query_api with LMS_API_KEY, returns result to LLM
5. LLM sees the response with 44 items → returns text answer
6. Agent extracts answer + source, outputs JSON
```

**Loop termination conditions:**
- LLM returns a text answer (no tool calls) → success
- Maximum 10 tool calls reached → stop with partial results

## System Prompt Strategy

The system prompt guides the LLM to:

1. Identify the question type (wiki, source code, data, error diagnosis)
2. Select the appropriate tool(s)
3. For error diagnosis: first reproduce the error with `query_api`, then read the source code with `read_file`
4. Include source references in answers
5. Stop calling tools once the answer is found

## Environment Variables

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api | Optional, defaults to `http://localhost:42002` |

**Important:** The autochecker runs with different credentials. Hardcoding values will fail evaluation.

## How to Run

### Prerequisites

1. Set up Qwen Code API on your VM following [wiki/qwen-code-api.md](wiki/qwen-code-api.md).

2. Copy and configure the environment files:
   ```bash
   cp .env.agent.example .env.agent.secret
   cp .env.docker.example .env.docker.secret
   # Edit both files with your credentials
   ```

### Usage

```bash
# Run with uv
uv run agent.py "How many items are in the database?"

# Or with Python directly (if in virtual environment)
python agent.py "What files are in the wiki?"
```

### Output

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "There are 44 items in the database.",
  "source": "API: /items/",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": [...]}"
    }
  ]
}
```

**Output fields:**
- `answer` (string): The LLM's answer to the question
- `source` (string): Reference to the source (file path or API endpoint)
- `tool_calls` (array): All tool calls made during the agentic loop, each with `tool`, `args`, and `result`

All debug and error messages are printed to stderr.

## Error Handling

- **Timeout**: 60-second timeout for LLM requests, 30-second for API requests
- **Exit codes**: 0 on success, non-zero on error
- **Error messages**: Printed to stderr, not stdout (to preserve JSON output)
- **Path validation**: Returns error message in tool result (not exception)
- **Max iterations**: Stops after 10 tool calls to prevent infinite loops

## Lessons Learned from Benchmark

### Initial Failures

1. **Tool message format**: The LLM API requires the full `tool_calls` structure in assistant messages, not just the tool results. Fixed by adding the assistant message with tool_calls before appending tool results.

2. **Authentication header**: The backend expects `Authorization: Bearer <key>`, not `X-API-Key`. Fixed by updating the headers in `query_api`.

3. **Environment loading**: The `LMS_API_KEY` was not being loaded because `load_env` only read from `.env.agent.secret`. Fixed by loading both `.env.agent.secret` and `.env.docker.secret`.

4. **LLM not calling read_file**: For error diagnosis questions, the LLM was inferring bugs from tracebacks without reading source code. Fixed by explicitly instructing the LLM to "MUST call read_file" in the system prompt.

5. **Testing with fake lab names**: The LLM was testing analytics endpoints with fake lab names like "sample-lab" instead of real IDs like "lab-01". Fixed by adding guidance to use real lab IDs.

### Iteration Strategy

1. Run `uv run run_eval.py` to get baseline score
2. For each failing question:
   - Check if the right tool was called
   - Check if the answer contains expected keywords
   - Adjust tool description or system prompt
3. Re-run after each fix

## Final Evaluation Score

**Local benchmark: 10/10 passed**

All questions passed:
- ✓ Wiki questions (branch protection, SSH connection)
- ✓ Source code questions (backend framework, API routers)
- ✓ Data queries (item count, status codes)
- ✓ Error diagnosis (division by zero, TypeError with NoneType)
- ✓ Reasoning questions (request lifecycle, ETL idempotency)

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent_output.py -v
```

Tests verify:
1. Output is valid JSON
2. `answer`, `source`, and `tool_calls` fields are present
3. Tool calls are executed correctly for different question types
4. Source references point to correct files or API endpoints

## Future Work

- Add more tools (e.g., `search_code` for grep-like search)
- Implement caching for repeated file reads or API calls
- Support for streaming responses for long answers
- Better error recovery when API is unavailable
