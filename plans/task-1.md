# Task 1: Call an LLM from Code

## Implementation Plan

### LLM Provider and Model

- **Provider**: Qwen Code API (self-hosted on VM via qwen-code-oai-proxy)
- **Model**: `qwen3-coder-plus`
- **API Format**: OpenAI-compatible `/v1/chat/completions` endpoint

**Rationale**: Qwen Code provides 1000 free requests per day, works from Russia, and requires no credit card. The proxy exposes an OpenAI-compatible API that is simple to integrate with.

### Agent Structure

The agent (`agent.py`) will:

1. **Parse CLI arguments**: Use `argparse` to accept the question as the first positional argument.

2. **Load configuration**: Read environment variables from `.env.agent.secret`:
   - `LLM_API_KEY` — API key for authentication
   - `LLM_API_BASE` — Base URL of the LLM API (e.g., `http://<vm-ip>:<port>/v1`)
   - `LLM_MODEL` — Model name to use

3. **Call the LLM**: Use `httpx` (already in project dependencies) to make a POST request to `/v1/chat/completions`:
   ```python
   POST {LLM_API_BASE}/chat/completions
   Headers:
     Authorization: Bearer {LLM_API_KEY}
     Content-Type: application/json
   Body:
     {
       "model": "{LLM_MODEL}",
       "messages": [{"role": "user", "content": "<question>"}]
     }
   ```

4. **Parse response**: Extract the answer from `response.choices[0].message.content`.

5. **Output JSON**: Print to stdout:
   ```json
   {"answer": "<extracted answer>", "tool_calls": []}
   ```

6. **Error handling**:
   - Timeout: 60 seconds for the API call
   - Exit code 0 on success, non-zero on error
   - All debug output goes to stderr (not stdout)

### File Structure

```
se-toolkit-lab-6/
├── agent.py              # Main agent CLI
├── .env.agent.secret     # LLM configuration (gitignored)
├── AGENT.md              # Documentation
└── plans/
    └── task-1.md         # This plan
```

### Testing Strategy

Create one regression test (`tests/test_agent_output.py`):
- Run `agent.py` as a subprocess with a simple question
- Parse stdout as JSON
- Verify `answer` and `tool_calls` fields are present
- Verify `tool_calls` is an empty list (for Task 1)

### Acceptance Criteria Checklist

- [ ] `plans/task-1.md` exists with implementation plan
- [ ] `agent.py` outputs valid JSON with `answer` and `tool_calls`
- [ ] API key stored in `.env.agent.secret` (not hardcoded)
- [ ] `AGENT.md` documents the architecture
- [ ] 1 regression test passes
- [ ] Git workflow followed (issue, branch, PR, approval)
