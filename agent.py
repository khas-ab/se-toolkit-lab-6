#!/usr/bin/env python3
"""CLI agent that calls an LLM with tool support and returns structured JSON output.

Usage:
    uv run agent.py "How do you resolve a merge conflict?"

Output (stdout):
    {
      "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
      "source": "wiki/git-workflow.md#resolving-merge-conflicts",
      "tool_calls": [...]
    }

All debug output goes to stderr.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# Maximum number of tool calls per question
MAX_TOOL_CALLS = 10


def load_env() -> None:
    """Load environment variables from .env.agent.secret."""
    env_file = Path(".env.agent.secret")
    if not env_file.exists():
        print(f"Error: {env_file} not found", file=sys.stderr)
        print(
            "Copy .env.agent.example to .env.agent.secret and fill in your credentials",
            file=sys.stderr,
        )
        sys.exit(1)

    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def validate_path(path: str) -> Path | None:
    """Validate that a path is within the project directory.

    Args:
        path: Relative path from project root.

    Returns:
        Resolved absolute Path if valid, None if path escapes project directory.
    """
    project_root = Path.cwd().resolve()
    try:
        full_path = (project_root / path).resolve()
        # Check that the resolved path starts with project root
        if not str(full_path).startswith(str(project_root)):
            return None
        return full_path
    except Exception:
        return None


def read_file(path: str) -> str:
    """Read a file from the project repository.

    Args:
        path: Relative path from project root.

    Returns:
        File contents as string, or error message if file doesn't exist or is invalid.
    """
    validated_path = validate_path(path)
    if validated_path is None:
        return f"Error: Path '{path}' is not allowed (must be within project directory)"

    if not validated_path.exists():
        return f"Error: File '{path}' does not exist"

    if not validated_path.is_file():
        return f"Error: '{path}' is not a file"

    try:
        return validated_path.read_text()
    except Exception as e:
        return f"Error: Could not read file '{path}': {e}"


def list_files(path: str) -> str:
    """List files and directories at a given path.

    Args:
        path: Relative directory path from project root.

    Returns:
        Newline-separated listing of entries, or error message if invalid.
    """
    validated_path = validate_path(path)
    if validated_path is None:
        return f"Error: Path '{path}' is not allowed (must be within project directory)"

    if not validated_path.exists():
        return f"Error: Directory '{path}' does not exist"

    if not validated_path.is_dir():
        return f"Error: '{path}' is not a directory"

    try:
        entries = sorted(validated_path.iterdir())
        # Return just the names, one per line
        return "\n".join(entry.name for entry in entries)
    except Exception as e:
        return f"Error: Could not list directory '{path}': {e}"


def get_tool_definitions() -> list[dict]:
    """Return tool definitions for the LLM API.

    Returns:
        List of tool definitions in OpenAI function-calling format.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the project repository. Use this to read documentation files to find answers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given path. Use this to discover what files exist in a directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root (e.g., 'wiki')"
                        }
                    },
                    "required": ["path"]
                }
            }
        }
    ]


def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return the result.

    Args:
        tool_name: Name of the tool to execute.
        args: Arguments for the tool.

    Returns:
        Tool result as a string.
    """
    if tool_name == "read_file":
        path = args.get("path", "")
        return read_file(path)
    elif tool_name == "list_files":
        path = args.get("path", "")
        return list_files(path)
    else:
        return f"Error: Unknown tool '{tool_name}'"


def extract_source_from_answer(answer: str, tool_results: list[dict]) -> str:
    """Extract source reference from the answer and tool results.

    Args:
        answer: The LLM's final answer.
        tool_results: List of tool call results with their paths.

    Returns:
        Source reference string (e.g., 'wiki/git-workflow.md#section').
    """
    # Look for file references in the answer (pattern: path.md or path.md#section)
    import re

    # Try to find a wiki file reference with optional anchor
    pattern = r'(wiki/[\w-]+\.md)(#[\w-]+)?'
    match = re.search(pattern, answer)
    if match:
        return match.group(0)

    # Fallback: use the last read_file result's path
    for tool_call in reversed(tool_results):
        if tool_call.get("tool") == "read_file":
            path = tool_call.get("args", {}).get("path", "")
            if path.startswith("wiki/"):
                return path

    return "unknown"


def call_llm(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Call the LLM API and return the response.

    Args:
        messages: List of message dicts with 'role' and 'content' fields.
        tools: Optional list of tool definitions.

    Returns:
        Parsed response dict with 'answer' and optional 'tool_calls'.

    Raises:
        SystemExit: If the API call fails.
    """
    api_key = os.environ.get("LLM_API_KEY")
    api_base = os.environ.get("LLM_API_BASE")
    model = os.environ.get("LLM_MODEL")

    if not api_key or api_key == "your-llm-api-key-here":
        print("Error: LLM_API_KEY not configured in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    if not api_base:
        print("Error: LLM_API_BASE not configured in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    if not model:
        print("Error: LLM_MODEL not configured in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "model": model,
        "messages": messages,
    }

    if tools:
        payload["tools"] = tools

    print(f"Calling LLM at {url}...", file=sys.stderr)

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
    except httpx.TimeoutException:
        print("Error: LLM request timed out (60s)", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"Error: Failed to connect to LLM: {e}", file=sys.stderr)
        sys.exit(1)

    data = response.json()

    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError) as e:
        print(f"Error: Unexpected LLM response format: {e}", file=sys.stderr)
        print(f"Response: {data}", file=sys.stderr)
        sys.exit(1)

    # Parse tool calls if present
    tool_calls = []
    if "tool_calls" in message and message["tool_calls"]:
        for tc in message["tool_calls"]:
            if tc.get("type") == "function":
                func = tc.get("function", {})
                tool_calls.append({
                    "id": tc.get("id"),
                    "name": func.get("name"),
                    "arguments": func.get("arguments"),
                })

    return {
        "content": message.get("content"),
        "tool_calls": tool_calls,
    }


def run_agentic_loop(question: str) -> dict:
    """Run the agentic loop to answer a question.

    Args:
        question: The user's question.

    Returns:
        Dict with 'answer', 'source', and 'tool_calls' fields.
    """
    # System prompt to guide the LLM
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

    # Initialize messages with system prompt and user question
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    tool_definitions = get_tool_definitions()
    all_tool_calls = []
    tool_results = []

    # Agentic loop
    for iteration in range(MAX_TOOL_CALLS):
        print(f"\n[Iteration {iteration + 1}/{MAX_TOOL_CALLS}]", file=sys.stderr)

        # Call LLM
        response = call_llm(messages, tool_definitions)

        # Check if LLM wants to call tools
        if response["tool_calls"]:
            print(f"LLM wants to call {len(response['tool_calls'])} tool(s)", file=sys.stderr)

            # Execute each tool call
            for tc in response["tool_calls"]:
                tool_name = tc["name"]
                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}

                print(f"  Executing {tool_name}({args})", file=sys.stderr)

                result = execute_tool(tool_name, args)

                # Record the tool call for output
                all_tool_calls.append({
                    "tool": tool_name,
                    "args": args,
                    "result": result,
                })

                tool_results.append({
                    "tool": tool_name,
                    "args": args,
                    "result": result,
                })

                # Append tool result as a new message
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            # Continue loop - LLM will process tool results
            continue
        else:
            # LLM provided a final answer (no tool calls)
            print("LLM provided final answer", file=sys.stderr)
            answer = response["content"] or ""

            # Extract source reference
            source = extract_source_from_answer(answer, tool_results)

            return {
                "answer": answer,
                "source": source,
                "tool_calls": all_tool_calls,
            }

    # Max iterations reached
    print("Warning: Maximum tool calls reached", file=sys.stderr)

    # Return whatever we have
    answer = "I reached the maximum number of tool calls. Here's what I found so far."
    source = extract_source_from_answer(answer, tool_results)

    return {
        "answer": answer,
        "source": source,
        "tool_calls": all_tool_calls,
    }


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="CLI agent that calls an LLM with tool support and returns structured JSON output"
    )
    parser.add_argument("question", help="The question to ask the LLM")
    args = parser.parse_args()

    load_env()

    result = run_agentic_loop(args.question)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
