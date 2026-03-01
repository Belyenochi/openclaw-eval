"""Tests for session metadata extraction."""

import json
import tempfile
from pathlib import Path

from openclaw_edd import session_reader


def test_extract_session_metadata():
    """Test extracting metadata from session header events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock session file
        session_id = "test-session-123"
        session_dir = Path(tmpdir) / ".openclaw" / "agents" / "main" / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / f"{session_id}.jsonl"

        # Write test data
        lines = [
            json.dumps(
                {"type": "session", "version": "1.0", "cwd": "/home/user/project"}
            ),
            json.dumps(
                {
                    "type": "model_change",
                    "provider": "deepseek",
                    "modelId": "deepseek-chat",
                }
            ),
            json.dumps({"type": "thinking_level_change", "thinkingLevel": "high"}),
            json.dumps(
                {
                    "type": "message",
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "Hello"}],
                    },
                }
            ),
            json.dumps(
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Hi!"}],
                    },
                }
            ),
        ]
        session_file.write_text("\n".join(lines))

        # Patch SESSION_DIR temporarily
        original_dir = session_reader.SESSION_DIR
        session_reader.SESSION_DIR = session_dir

        try:
            metadata = session_reader.extract_session_metadata(session_id)

            assert metadata["cwd"] == "/home/user/project"
            assert metadata["session_version"] == "1.0"
            assert metadata["provider"] == "deepseek"
            assert metadata["model"] == "deepseek-chat"
            assert metadata["thinking_level"] == "high"
        finally:
            session_reader.SESSION_DIR = original_dir


def test_extract_session_metadata_stops_at_message():
    """Test that metadata extraction stops at first message event."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_id = "test-session-456"
        session_dir = Path(tmpdir) / ".openclaw" / "agents" / "main" / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / f"{session_id}.jsonl"

        # Write test data with model_change AFTER a message (should be ignored)
        lines = [
            json.dumps({"type": "session", "version": "1.0"}),
            json.dumps({"type": "message", "message": {"role": "user", "content": []}}),
            json.dumps(
                {"type": "model_change", "provider": "anthropic", "modelId": "claude-3"}
            ),
        ]
        session_file.write_text("\n".join(lines))

        original_dir = session_reader.SESSION_DIR
        session_reader.SESSION_DIR = session_dir

        try:
            metadata = session_reader.extract_session_metadata(session_id)

            # Should have session but not the model_change (it came after message)
            assert metadata["session_version"] == "1.0"
            assert "provider" not in metadata or metadata["provider"] == ""
            assert "model" not in metadata or metadata["model"] == ""
        finally:
            session_reader.SESSION_DIR = original_dir


def test_extract_session_metadata_empty_file():
    """Test extracting metadata from empty session file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_id = "test-session-empty"
        session_dir = Path(tmpdir) / ".openclaw" / "agents" / "main" / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / f"{session_id}.jsonl"
        session_file.write_text("")

        original_dir = session_reader.SESSION_DIR
        session_reader.SESSION_DIR = session_dir

        try:
            metadata = session_reader.extract_session_metadata(session_id)

            assert metadata == {}
        finally:
            session_reader.SESSION_DIR = original_dir


def test_extract_session_metadata_missing_file():
    """Test extracting metadata when session file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_id = "non-existent-session"
        session_dir = Path(tmpdir) / ".openclaw" / "agents" / "main" / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)

        original_dir = session_reader.SESSION_DIR
        session_reader.SESSION_DIR = session_dir

        try:
            metadata = session_reader.extract_session_metadata(session_id)

            assert metadata == {}
        finally:
            session_reader.SESSION_DIR = original_dir
