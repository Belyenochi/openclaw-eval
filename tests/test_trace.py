"""Tests for trace functionality."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from openclaw_edd import session_reader
from openclaw_edd.models import Event


def test_resolve_latest_session():
    """Test finding the most recent session file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir) / ".openclaw" / "agents" / "main" / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)

        # Create session files with different timestamps
        session1 = session_dir / "session-001.jsonl"
        session2 = session_dir / "session-002.jsonl"
        session3 = session_dir / "session-003.jsonl"

        session1.write_text('{"type": "session"}\n')
        time.sleep(0.01)
        session2.write_text('{"type": "session"}\n')
        time.sleep(0.01)
        session3.write_text('{"type": "session"}\n')

        # Patch Path.home to return our temp directory
        with patch.object(Path, "home", return_value=Path(tmpdir)):
            latest = session_reader.resolve_latest_session("main")
            assert latest == "session-003"


def test_resolve_latest_session_empty_dir():
    """Test finding latest session when no sessions exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir) / ".openclaw" / "agents" / "main" / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)

        # Patch Path.home to return our temp directory
        with patch.object(Path, "home", return_value=Path(tmpdir)):
            latest = session_reader.resolve_latest_session("main")
            assert latest is None


def test_retry_detection():
    """Test that consecutive identical tool calls are detected as retries."""
    events = [
        Event(
            kind="tool_end",
            tool="exec",
            input={"command": "curl https://example.com"},
            output="timeout",
            ts="2026-03-01T01:00:00Z",
            session_id="s1",
            status="running",
        ),
        Event(
            kind="tool_end",
            tool="exec",
            input={"command": "curl https://example.com"},
            output="timeout",
            ts="2026-03-01T01:00:05Z",
            session_id="s1",
            status="running",
        ),
        Event(
            kind="tool_end",
            tool="exec",
            input={"command": "curl https://example.com"},
            output="success",
            ts="2026-03-01T01:00:10Z",
            session_id="s1",
            status="completed",
            exit_code=0,
        ),
    ]

    # Simulate retry counting logic
    retry_count = 0
    last_tool = ""
    last_input = {}
    retry_indicators = []

    for event in events:
        is_retry = (
            event.tool == last_tool
            and event.input == last_input
            and event.tool == "exec"
        )
        if is_retry:
            retry_count += 1
        else:
            retry_count = 0
        last_tool = event.tool
        last_input = event.input

        if retry_count > 0:
            retry_indicators.append(retry_count)

    assert retry_indicators == [1, 2]


def test_event_with_plan_text():
    """Test that plan_text is properly stored in events."""
    event = Event(
        kind="tool_end",
        tool="exec",
        input={"command": "ls"},
        output="file.txt",
        ts="2026-03-01T01:00:00Z",
        session_id="s1",
        plan_text="I'll list the files in the directory",
        model="deepseek-chat",
        usage={"input": 100, "output": 50},
    )

    assert event.plan_text == "I'll list the files in the directory"
    assert event.model == "deepseek-chat"
    assert event.usage["input"] == 100
