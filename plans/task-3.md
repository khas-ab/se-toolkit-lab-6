# Task 3: The System Agent

## Implementation Plan

### Overview

This task extends the Task 2 agent with a `query_api` tool that allows the LLM to query the deployed backend API. The agent will now answer two new kinds of questions:
1. **Static system facts** - framework, ports, status codes (read from source code)
2. **Data-dependent queries** - item count, scores, analytics (query the running API)

### Tool Schema: `query_api`

The `query_api` tool will be defined as a function-calling schema alongside `read_file` and `list_files`.

**Parameters:**
- `method` (string, required): HTTP method (GET, POST, PUT, DELETE, etc.)
- `path` (string, required): API endpoint path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests

**Returns:** JSON string with:
- `status_code`: HTTP status code
- `body`: Response body (parsed JSON or raw text)

**Schema format:**
```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Query the backend API. Use this to get data from the running system (e.g., item count, analytics).",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {
          "type": "string",
          "description": "HTTP method (GET, POST, etc.)"
        },
        "path": {
          "type": "string",
          "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"
        },
        "body": {
          "type": "string",
          "description": "JSON request body for POST/PUT requests (optional)"
        }
      },
      "required": ["method", "path"]
    }
  }
}
```

### Authentication

The `query_api` tool must authenticate with the backend using `LMS_API_KEY`:

1. **Read from environment**: Load `LMS_API_KEY` from `.env.docker.secret` (not `.env.agent.secret`)
2. **Two distinct keys**:
   - `LLM_API_KEY` (in `.env.agent.secret`) — authenticates with LLM provider
   - `LMS_API_KEY` (in `.env.docker.secret`) — authenticates with backend API
3. **HTTP header**: Send `X-API-Key: <LMS_API_KEY>` header with each request
4. **Base URL**: Read `AGENT_API_BASE_URL` from environment, default to `http://localhost:42002`

**Implementation:**
```python
def query_api(method: str, path: str, body: str | None = None) -> str:
    """Query the backend API with authentication."""
    api_key = os.environ.get("LMS_API_KEY")
    base_url = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")
    
    url = f"{base_url}{path}"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    
    # Make request with httpx
    # Return JSON string with status_code and body
```

### System Prompt Update

The system prompt must guide the LLM to choose the right tool:

**Decision logic:**
- **Wiki questions** ("According to the wiki...", "What does the project say about...") → use `read_file` / `list_files`
- **Source code questions** ("What framework does the backend use?", "Read the source code...") → use `read_file` on backend files
- **Data questions** ("How many items...", "Query the API...") → use `query_api`
- **Error diagnosis** ("What error do you get...", "Query and find the bug") → use `query_api` first, then `read_file` to find the bug in source

**Updated system prompt:**
```
You are a documentation and system assistant for a software engineering toolkit.

You have three tools available:
1. list_files - Discover what files exist in a directory
2. read_file - Read contents of documentation or source code files
3. query_api - Query the running backend API for data

When answering questions:
- For wiki/documentation questions: use list_files and read_file on wiki/ directory
- For source code questions: use read_file on backend/ files
- For data questions (counts, scores, analytics): use query_api
- For error diagnosis: use query_api to reproduce the error, then read_file to find the bug

Always cite your sources (file path for read_file, or note "from API" for query_api).
```

### Environment Variables

The agent must read all configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api | Optional, defaults to `http://localhost:42002` |

**Important**: The autochecker runs with different credentials. Hardcoding values will fail.

### File Structure

```
se-toolkit-lab-6/
├── agent.py              # Updated with query_api tool
├── AGENT.md              # Updated documentation
├── plans/
│   └── task-3.md         # This plan
└── tests/
    └── test_agent_output.py  # Add 2 more regression tests
```

### Benchmark Questions

The 10 local questions in `run_eval.py`:

| # | Question Type | Expected Tool |
|---|---------------|---------------|
| 0 | Wiki: branch protection | `read_file` |
| 1 | Wiki: SSH connection | `read_file` |
| 2 | Source: backend framework | `read_file` |
| 3 | Source: API router modules | `list_files` |
| 4 | Data: item count | `query_api` |
| 5 | Data: status code without auth | `query_api` |
| 6 | Data + Bug: division error | `query_api`, `read_file` |
| 7 | Data + Bug: NoneType error | `query_api`, `read_file` |
| 8 | Reasoning: request lifecycle | `read_file` (LLM judge) |
| 9 | Reasoning: ETL idempotency | `read_file` (LLM judge) |

### Iteration Strategy

1. **Initial run**: Run `uv run run_eval.py` to get baseline score
2. **Analyze failures**: For each failing question:
   - Check if the right tool was called
   - Check if the answer contains expected keywords
   - Adjust tool description or system prompt as needed
3. **Common issues**:
   - Tool not called → improve tool description
   - Wrong arguments → clarify parameter descriptions
   - Wrong answer → adjust system prompt for better reasoning
4. **Re-run**: After each fix, re-run benchmark

### Testing Strategy

Add 2 regression tests:

1. **System fact question**:
   - Question: "What Python web framework does this project's backend use?"
   - Expects: `read_file` in tool_calls, answer contains "FastAPI"

2. **Data query question**:
   - Question: "How many items are currently stored in the database?"
   - Expects: `query_api` in tool_calls, answer contains a number > 0

### Acceptance Criteria

- [ ] `plans/task-3.md` exists with implementation plan
- [ ] `agent.py` defines `query_api` as function-calling schema
- [ ] `query_api` authenticates with `LMS_API_KEY` from environment
- [ ] Agent reads all LLM config from environment variables
- [ ] Agent reads `AGENT_API_BASE_URL` from environment (defaults to localhost)
- [ ] `run_eval.py` passes all 10 local questions
- [ ] `AGENT.md` documents final architecture (200+ words)
- [ ] 2 tool-calling regression tests exist and pass

---

## Benchmark Results

### Initial Score

- **Score**: 4/10
- **Date**: March 17, 2026

### First Failures

| Question | Issue | Fix |
|----------|-------|-----|
| 5 (item count) | LMS_API_KEY not loaded | Updated `load_env()` to load both `.env.agent.secret` and `.env.docker.secret` |
| 5 (item count) | API returned 401 | Changed auth header from `X-API-Key` to `Authorization: Bearer` |
| 6 (auth status) | Agent always sent API key | Added `auth` parameter to `query_api` for testing unauthenticated access |
| 7 (division error) | LLM didn't call `read_file` | Updated system prompt to explicitly require `read_file` for bug diagnosis |
| 8 (top-learners) | Tested with fake lab names | Added guidance to use real lab IDs like "lab-01" |
| 8 (top-learners) | Reached max tool calls | LLM was testing many fake labs before finding error |

### Iteration Log

| Iteration | Score | Changes Made |
|-----------|-------|--------------|
| 1 | 4/10 | Initial implementation with `query_api` tool |
| 2 | 5/10 | Fixed LMS_API_KEY loading and auth header format |
| 3 | 6/10 | Added `auth` parameter for testing unauthenticated access |
| 4 | 7/10 | Updated system prompt to require `read_file` for bug diagnosis |
| 5 | 8/10 | Added guidance to use real lab IDs |
| 6 | 9/10 | Fixed tool message format (assistant message with tool_calls) |
| 7 | 10/10 | All tests passing |

### Final Score: 10/10 PASSED

All 10 local benchmark questions pass:
- ✓ Wiki questions (branch protection, SSH connection)
- ✓ Source code questions (backend framework, API routers)
- ✓ Data queries (item count, status codes)
- ✓ Error diagnosis (division by zero, TypeError with NoneType)
- ✓ Reasoning questions (request lifecycle, ETL idempotency)
