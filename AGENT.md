# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM (Large Language Model) with tool-calling capabilities. It can read documentation files and navigate the project wiki to answer questions with proper source citations.

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
```

## Components

### `agent.py`

The main CLI agent with the following responsibilities:

1. **Argument parsing**: Accepts a question as the first command-line argument using `argparse`.

2. **Configuration loading**: Reads LLM credentials from `.env.agent.secret`:
   - `LLM_API_KEY` — API key for authentication
   - `LLM_API_BASE` — Base URL of the LLM API
   - `LLM_MODEL` — Model name to use

3. **Tool definitions**: Defines two tools as function-calling schemas:
   - `read_file` — Read a file from the project repository
   - `list_files` — List files and directories at a given path

4. **Agentic loop**: Implements the reasoning loop:
   - Send user question + tool definitions to LLM
   - If LLM responds with `tool_calls`: execute tools, append results, repeat
   - If LLM responds with text answer: extract answer and source, output JSON
   - Maximum 10 tool calls per question

5. **Path security**: Validates all file paths to prevent directory traversal attacks

6. **Output formatting**: Prints JSON to stdout with `answer`, `source`, and `tool_calls` fields

### Tools

#### `read_file`

Reads a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as a string, or an error message if the file doesn't exist or is invalid.

**Security:** Validates that the resolved path is within the project directory. Rejects paths with `../` traversal.

#### `list_files`

Lists files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing of entry names, or an error message if the path is invalid.

**Security:** Validates that the resolved path is within the project directory.

### Path Security Implementation

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

### Agentic Loop

The agentic loop enables multi-step reasoning:

```
1. User asks: "How do you resolve a merge conflict?"
2. Agent sends question + tool definitions to LLM
3. LLM decides: "I need to explore the wiki first" → calls list_files(wiki)
4. Agent executes list_files, returns result to LLM
5. LLM sees git-workflow.md → calls read_file(wiki/git-workflow.md)
6. Agent executes read_file, returns content to LLM
7. LLM finds the answer in the content → returns text answer
8. Agent extracts answer + source, outputs JSON
```

**Loop termination conditions:**
- LLM returns a text answer (no tool calls) → success
- Maximum 10 tool calls reached → stop with partial results

### System Prompt Strategy

The system prompt guides the LLM to:

1. Use `list_files` to discover wiki files when unsure where to look
2. Use `read_file` to read relevant files and find answers
3. Include source references in answers (e.g., `wiki/git-workflow.md#section`)
4. Stop calling tools once the answer is found

```python
system_prompt = """You are a documentation assistant for a software engineering toolkit.

Your task is to answer questions by reading documentation files in the wiki/ directory.

You have two tools available:
1. list_files - Use this to discover what files exist in a directory
2. read_file - Use this to read the contents of a specific file

When answering questions:
1. First use list_files to explore the wiki/ directory if you're unsure where to look
2. Use read_file to read relevant files and find the answer
3. Include a source reference in your answer (e.g., "See wiki/git-workflow.md#resolving-merge-conflicts")
4. Once you have found the answer, provide it as a text response (no tool calls)

Always be concise and accurate. Cite your sources."""
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
uv run agent.py "How do you resolve a merge conflict?"

# Or with Python directly (if in virtual environment)
python agent.py "What files are in the wiki?"
```

### Output

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

**Output fields:**
- `answer` (string): The LLM's answer to the question
- `source` (string): Reference to the wiki section (e.g., `wiki/git-workflow.md#section`)
- `tool_calls` (array): All tool calls made during the agentic loop, each with `tool`, `args`, and `result`

All debug and error messages are printed to stderr.

## Error Handling

- **Timeout**: 60-second timeout for LLM requests
- **Exit codes**: 0 on success, non-zero on error
- **Error messages**: Printed to stderr, not stdout (to preserve JSON output)
- **Path validation**: Returns error message in tool result (not exception)
- **Max iterations**: Stops after 10 tool calls to prevent infinite loops

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent_output.py -v
```

Tests verify:
1. Output is valid JSON
2. `answer`, `source`, and `tool_calls` fields are present
3. Tool calls are executed correctly for documentation questions
4. Source references point to correct wiki files

## Future Work (Task 3)

- Add more tools (e.g., `query_api`, `search_code`)
- Implement more sophisticated source extraction
- Add caching for repeated file reads
- Support for searching within files
