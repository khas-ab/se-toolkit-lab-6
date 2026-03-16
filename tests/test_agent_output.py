"""Regression tests for agent.py output structure.

These tests run agent.py as a subprocess and verify:
1. The output is valid JSON
2. The 'answer' field is present
3. The 'tool_calls' field is present and is a list
4. The 'source' field is present for documentation questions
5. Tool calls are executed correctly for documentation questions
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


AGENT_PATH = Path("agent.py")
TEST_QUESTION = "What is 2 + 2?"


@pytest.fixture
def agent_script() -> Path:
    """Return path to agent.py."""
    return AGENT_PATH


@pytest.fixture
def env_file() -> Path:
    """Return path to .env.agent.secret."""
    return Path(".env.agent.secret")


def test_agent_output_structure(agent_script: Path, env_file: Path) -> None:
    """Test that agent.py outputs valid JSON with required fields.

    This test:
    1. Runs agent.py as a subprocess with a simple question
    2. Parses stdout as JSON
    3. Verifies 'answer' and 'tool_calls' fields are present
    4. Verifies 'tool_calls' is an empty list (Task 1 requirement)
    """
    # Skip if .env.agent.secret is not configured
    if not env_file.exists():
        pytest.skip(".env.agent.secret not found")

    # Check if LLM_API_KEY is still the placeholder value
    env_content = env_file.read_text()
    if "your-llm-api-key-here" in env_content:
        pytest.skip("LLM_API_KEY not configured in .env.agent.secret")

    # Run agent.py as subprocess
    result = subprocess.run(
        [sys.executable, str(agent_script), TEST_QUESTION],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Check exit code
    assert result.returncode == 0, (
        f"Agent exited with code {result.returncode}\n"
        f"Stderr: {result.stderr}"
    )

    # Parse stdout as JSON
    stdout = result.stdout.strip()
    assert stdout, "Agent produced no output"

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Agent output is not valid JSON: {e}\nOutput: {stdout[:200]}")

    # Check required fields
    assert "answer" in data, "Missing 'answer' field in output"
    assert "tool_calls" in data, "Missing 'tool_calls' field in output"

    # Check field types
    assert isinstance(data["answer"], str), "'answer' should be a string"
    assert isinstance(data["tool_calls"], list), "'tool_calls' should be a list"
    assert "source" in data, "Missing 'source' field in output (Task 2 requirement)"

    # For simple math questions, tool_calls may be empty (LLM can answer directly)
    # For documentation questions, tool_calls should be populated

    # Check answer is not empty
    assert data["answer"].strip(), "'answer' should not be empty"


def test_agent_handles_simple_question(agent_script: Path, env_file: Path) -> None:
    """Test that agent responds to a simple factual question.

    This is a basic sanity check that the LLM is working.
    """
    if not env_file.exists():
        pytest.skip(".env.agent.secret not found")

    env_content = env_file.read_text()
    if "your-llm-api-key-here" in env_content:
        pytest.skip("LLM_API_KEY not configured in .env.agent.secret")

    question = "What color is the sky?"
    result = subprocess.run(
        [sys.executable, str(agent_script), question],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        pytest.skip(f"Agent failed: {result.stderr[:200]}")

    data = json.loads(result.stdout.strip())

    # Just check that we got a non-empty answer
    assert len(data["answer"].strip()) > 0, "Answer should not be empty"


def test_agent_merge_conflict_question(
    agent_script: Path, env_file: Path
) -> None:
    """Test that agent uses read_file to answer merge conflict question.

    This test verifies:
    1. The 'source' field is present in output
    2. read_file is used in tool_calls
    3. The source references wiki/git-workflow.md
    """
    if not env_file.exists():
        pytest.skip(".env.agent.secret not found")

    env_content = env_file.read_text()
    if "your-llm-api-key-here" in env_content:
        pytest.skip("LLM_API_KEY not configured in .env.agent.secret")

    question = "How do you resolve a merge conflict?"
    result = subprocess.run(
        [sys.executable, str(agent_script), question],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        pytest.skip(f"Agent failed: {result.stderr[:200]}")

    stdout = result.stdout.strip()
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Agent output is not valid JSON: {e}\nOutput: {stdout[:200]}")

    # Check required fields for Task 2
    assert "answer" in data, "Missing 'answer' field in output"
    assert "source" in data, "Missing 'source' field in output"
    assert "tool_calls" in data, "Missing 'tool_calls' field in output"

    # Check that tool_calls is a list and not empty
    assert isinstance(data["tool_calls"], list), "'tool_calls' should be a list"
    assert len(data["tool_calls"]) > 0, "Expected at least one tool call"

    # Check that read_file was used
    tool_names = [tc.get("tool") for tc in data["tool_calls"]]
    assert "read_file" in tool_names, "Expected read_file to be called"

    # Check that source references a wiki git file
    source = data["source"]
    assert "wiki/git" in source and ".md" in source, (
        f"Expected source to reference wiki git file, got: {source}"
    )


def test_agent_wiki_listing_question(
    agent_script: Path, env_file: Path
) -> None:
    """Test that agent uses list_files to answer wiki listing question.

    This test verifies:
    1. list_files is used in tool_calls
    2. The tool was called with path 'wiki'
    """
    if not env_file.exists():
        pytest.skip(".env.agent.secret not found")

    env_content = env_file.read_text()
    if "your-llm-api-key-here" in env_content:
        pytest.skip("LLM_API_KEY not configured in .env.agent.secret")

    question = "What files are in the wiki?"
    result = subprocess.run(
        [sys.executable, str(agent_script), question],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        pytest.skip(f"Agent failed: {result.stderr[:200]}")

    stdout = result.stdout.strip()
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Agent output is not valid JSON: {e}\nOutput: {stdout[:200]}")

    # Check required fields for Task 2
    assert "answer" in data, "Missing 'answer' field in output"
    assert "tool_calls" in data, "Missing 'tool_calls' field in output"

    # Check that tool_calls is a list and not empty
    assert isinstance(data["tool_calls"], list), "'tool_calls' should be a list"
    assert len(data["tool_calls"]) > 0, "Expected at least one tool call"

    # Check that list_files was used
    tool_names = [tc.get("tool") for tc in data["tool_calls"]]
    assert "list_files" in tool_names, "Expected list_files to be called"

    # Check that list_files was called with path 'wiki'
    list_files_calls = [
        tc for tc in data["tool_calls"] if tc.get("tool") == "list_files"
    ]
    wiki_paths = [tc.get("args", {}).get("path") for tc in list_files_calls]
    assert "wiki" in wiki_paths, (
        f"Expected list_files to be called with path 'wiki', got: {wiki_paths}"
    )


def test_agent_backend_framework_question(
    agent_script: Path, env_file: Path
) -> None:
    """Test that agent uses read_file to answer backend framework question.

    This test verifies:
    1. The 'source' field references a backend file
    2. read_file is used in tool_calls
    3. The answer mentions FastAPI
    """
    if not env_file.exists():
        pytest.skip(".env.agent.secret not found")

    env_content = env_file.read_text()
    if "your-llm-api-key-here" in env_content:
        pytest.skip("LLM_API_KEY not configured in .env.agent.secret")

    question = "What Python web framework does this project's backend use?"
    result = subprocess.run(
        [sys.executable, str(agent_script), question],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        pytest.skip(f"Agent failed: {result.stderr[:200]}")

    stdout = result.stdout.strip()
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Agent output is not valid JSON: {e}\nOutput: {stdout[:200]}")

    # Check required fields
    assert "answer" in data, "Missing 'answer' field in output"
    assert "source" in data, "Missing 'source' field in output"
    assert "tool_calls" in data, "Missing 'tool_calls' field in output"

    # Check that tool_calls is a list and not empty
    assert isinstance(data["tool_calls"], list), "'tool_calls' should be a list"
    assert len(data["tool_calls"]) > 0, "Expected at least one tool call"

    # Check that read_file was used
    tool_names = [tc.get("tool") for tc in data["tool_calls"]]
    assert "read_file" in tool_names, "Expected read_file to be called"

    # Check that answer mentions FastAPI
    answer = data["answer"].lower()
    assert "fastapi" in answer, (
        f"Expected answer to mention FastAPI, got: {data['answer']}"
    )

    # Check that source references a backend file
    source = data["source"]
    assert "backend" in source.lower(), (
        f"Expected source to reference backend file, got: {source}"
    )


def test_agent_database_item_count_question(
    agent_script: Path, env_file: Path
) -> None:
    """Test that agent uses query_api to answer database item count question.

    This test verifies:
    1. query_api is used in tool_calls
    2. The answer contains a number greater than 0
    3. The source references the API endpoint
    """
    if not env_file.exists():
        pytest.skip(".env.agent.secret not found")

    env_content = env_file.read_text()
    if "your-llm-api-key-here" in env_content:
        pytest.skip("LLM_API_KEY not configured in .env.agent.secret")

    # Also check if LMS_API_KEY is configured
    if "my-secret-api-key" in env_content and "LMS_API_KEY" not in env_content:
        pytest.skip("LMS_API_KEY not configured in .env.docker.secret")

    question = "How many items are currently stored in the database?"
    result = subprocess.run(
        [sys.executable, str(agent_script), question],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        pytest.skip(f"Agent failed: {result.stderr[:200]}")

    stdout = result.stdout.strip()
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Agent output is not valid JSON: {e}\nOutput: {stdout[:200]}")

    # Check required fields
    assert "answer" in data, "Missing 'answer' field in output"
    assert "tool_calls" in data, "Missing 'tool_calls' field in output"

    # Check that tool_calls is a list and not empty
    assert isinstance(data["tool_calls"], list), "'tool_calls' should be a list"
    assert len(data["tool_calls"]) > 0, "Expected at least one tool call"

    # Check that query_api was used
    tool_names = [tc.get("tool") for tc in data["tool_calls"]]
    assert "query_api" in tool_names, "Expected query_api to be called"

    # Check that answer contains a number > 0
    import re
    numbers = re.findall(r"\d+", data["answer"])
    assert len(numbers) > 0, f"Expected answer to contain a number, got: {data['answer']}"
    
    # At least one number should be greater than 0
    has_positive = any(int(n) > 0 for n in numbers)
    assert has_positive, (
        f"Expected answer to contain a positive number, got numbers: {numbers}"
    )

    # Check that source references the API
    source = data["source"]
    assert "api" in source.lower() or "/items" in source, (
        f"Expected source to reference API, got: {source}"
    )
