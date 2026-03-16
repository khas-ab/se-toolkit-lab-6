# Task 2: The Documentation Agent

## Implementation Plan

### Overview

This task extends the Task 1 agent with tool-calling capabilities. The agent will have two tools (`read_file` and `list_files`) to navigate the project wiki and answer documentation questions.

### Tool Definitions

#### `read_file`

- **Purpose**: Read contents of a file from the project repository
- **Parameters**: 
  - `path` (string, required): Relative path from project root
- **Returns**: File contents as string, or error message if file doesn't exist
- **Security**: Must validate path doesn't escape project directory (no `../` traversal)

#### `list_files`

- **Purpose**: List files and directories at a given path
- **Parameters**:
  - `path` (string, required): Relative directory path from project root
- **Returns**: Newline-separated listing of entries
- **Security**: Must validate path doesn't escape project directory

### Tool Schema Format (OpenAI Function Calling)

Tools will be defined as JSON schemas in the LLM API request:

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read a file from the project repository",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Relative path from project root"
        }
      },
      "required": ["path"]
    }
  }
}
```

### Agentic Loop

The agentic loop will:

1. **Initialize**: Start with user question as a `user` role message
2. **Send to LLM**: Call LLM with messages + tool definitions
3. **Check response**:
   - If `tool_calls` present: execute each tool, append results as `tool` role messages, go to step 2
   - If text answer (no tool calls): extract answer and source, output JSON and exit
4. **Limit**: Maximum 10 tool calls per question to prevent infinite loops

```
User question → LLM (with tools) → tool_calls? → execute → append result → LLM → ... → final answer
```

### Path Security

To prevent directory traversal attacks:

1. **Resolve to absolute path**: Use `Path.resolve()` to get canonical path
2. **Check prefix**: Verify resolved path starts with project root
3. **Reject invalid paths**: Return error message if path escapes project directory

```python
def validate_path(path: str) -> Path | None:
    """Validate path is within project directory."""
    project_root = Path.cwd().resolve()
    try:
        full_path = (project_root / path).resolve()
        if not str(full_path).startswith(str(project_root)):
            return None
        return full_path
    except Exception:
        return None
```

### System Prompt Strategy

The system prompt will instruct the LLM to:

1. Use `list_files` to discover wiki files when unsure where to look
2. Use `read_file` to read relevant files and find answers
3. Include source reference (file path + section anchor) in the final answer
4. Stop calling tools once the answer is found

### Output Structure

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "git-workflow.md\n..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

### File Structure

```
se-toolkit-lab-6/
├── agent.py              # Updated with tools and agentic loop
├── AGENT.md              # Updated documentation
├── plans/
│   └── task-2.md         # This plan
└── tests/
    └── test_agent_output.py  # Add 2 more regression tests
```

### Testing Strategy

Add 2 regression tests to `tests/test_agent_output.py`:

1. **Test merge conflict question**:
   - Question: "How do you resolve a merge conflict?"
   - Expects: `read_file` in tool_calls, `wiki/git-workflow.md` in source

2. **Test wiki listing question**:
   - Question: "What files are in the wiki?"
   - Expects: `list_files` in tool_calls

### Acceptance Criteria Checklist

- [ ] `plans/task-2.md` exists with implementation plan
- [ ] `agent.py` defines `read_file` and `list_files` as tool schemas
- [ ] The agentic loop executes tool calls and feeds results back to the LLM
- [ ] `tool_calls` in output is populated when tools are used
- [ ] The `source` field correctly identifies the wiki section
- [ ] Tools do not access files outside project directory
- [ ] `AGENT.md` documents the tools and agentic loop
- [ ] 2 tool-calling regression tests exist and pass
- [ ] Git workflow followed (issue, branch, PR, approval)
