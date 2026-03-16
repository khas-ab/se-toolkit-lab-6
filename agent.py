#!/usr/bin/env python3
"""CLI agent that calls an LLM and returns structured JSON output.

Usage:
    uv run agent.py "What does REST stand for?"

Output (stdout):
    {"answer": "Representational State Transfer.", "tool_calls": []}

All debug output goes to stderr.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx


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


def call_llm(question: str) -> str:
    """Call the LLM API and return the answer.

    Args:
        question: The user's question.

    Returns:
        The LLM's answer as a string.

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
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": question}],
    }

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
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        print(f"Error: Unexpected LLM response format: {e}", file=sys.stderr)
        print(f"Response: {data}", file=sys.stderr)
        sys.exit(1)

    return answer


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="CLI agent that calls an LLM and returns structured JSON output"
    )
    parser.add_argument("question", help="The question to ask the LLM")
    args = parser.parse_args()

    load_env()

    answer = call_llm(args.question)

    output = {
        "answer": answer,
        "tool_calls": [],
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
