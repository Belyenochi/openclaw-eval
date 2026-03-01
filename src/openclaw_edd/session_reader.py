"""Session file reader for OpenClaw sessions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from .models import Event

SESSION_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"


def get_session_file_path(session_id: str) -> Path:
    """Return the session file path for a session ID."""
    return SESSION_DIR / f"{session_id}.jsonl"


def read_session_messages(session_id: str) -> Generator[dict, None, None]:
    """Yield messages from a session file.

    Args:
        session_id: Session ID.

    Yields:
        Parsed JSON messages.
    """
    session_file = get_session_file_path(session_id)
    if not session_file.exists():
        return

    with open(session_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def tail_session_file(
    session_id: str, from_end: bool = True
) -> Generator[dict, None, None]:
    """Tail a session file and yield new messages.

    Args:
        session_id: Session ID.
        from_end: If True, start from end of file.

    Yields:
        Parsed JSON messages.
    """
    import time

    session_file = get_session_file_path(session_id)

    while not session_file.exists():
        time.sleep(0.5)

    with open(session_file, "r", encoding="utf-8") as f:
        if from_end:
            f.seek(0, 2)

        while True:
            line = f.readline()
            if line:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        pass
            else:
                time.sleep(0.05)


def extract_tool_call_info(message: dict) -> dict | None:
    """Extract tool-call or response info from a session message.

    Args:
        message: Session message dict.

    Returns:
        Parsed info dict or None if not applicable.
    """
    if message.get("type") != "message":
        return None

    msg = message.get("message", {})
    role = msg.get("role")

    if role == "assistant":
        content = msg.get("content", [])

        for item in content:
            if item.get("type") == "toolCall":
                return {
                    "event": "tool_call",
                    "tool": item.get("name"),
                    "tool_call_id": item.get("id"),
                    "arguments": item.get("arguments", {}),
                    "timestamp": message.get("timestamp"),
                    "message_id": message.get("id"),
                }

        for item in content:
            if item.get("type") == "text" and item.get("text"):
                return {
                    "event": "llm_response",
                    "text": item.get("text"),
                    "timestamp": message.get("timestamp"),
                    "message_id": message.get("id"),
                    "model": msg.get("model", ""),
                    "usage": msg.get("usage", {}),
                }

    elif role == "toolResult":
        content = msg.get("content", [])
        text_content = ""
        for item in content:
            if item.get("type") == "text":
                text_content = item.get("text", "")
                break

        details = msg.get("details", {})
        return {
            "event": "tool_result",
            "tool": msg.get("toolName"),
            "tool_call_id": msg.get("toolCallId"),
            "output": text_content,
            "duration_ms": details.get("durationMs", 0),
            "status": details.get("status", ""),
            "exit_code": details.get("exitCode"),
            "timestamp": message.get("timestamp"),
            "message_id": message.get("id"),
            "parent_id": message.get("parentId"),
        }

    return None


def extract_session_metadata(session_id: str) -> dict[str, Any]:
    """Extract metadata from session header events.

    Returns dict with keys: model, provider, thinking_level, cwd, session_version.
    """
    metadata: dict[str, Any] = {}
    for message in read_session_messages(session_id):
        msg_type = message.get("type", "")
        if msg_type == "session":
            metadata["cwd"] = message.get("cwd", "")
            metadata["session_version"] = message.get("version")
        elif msg_type == "model_change":
            metadata["provider"] = message.get("provider", "")
            metadata["model"] = message.get("modelId", "")
        elif msg_type == "thinking_level_change":
            metadata["thinking_level"] = message.get("thinkingLevel", "")
        elif msg_type == "message":
            break  # Stop after header events
    return metadata


def build_events_from_session(session_id: str) -> list[Event]:
    """Build events from a session file.

    Args:
        session_id: Session ID.

    Returns:
        List of Event objects.
    """
    events: list[Event] = []
    pending_calls: dict[str, dict] = {}

    for message in read_session_messages(session_id):
        info = extract_tool_call_info(message)
        if not info:
            continue

        event_type = info.get("event")

        if event_type == "tool_call":
            tool_call_id = (
                info.get("tool_call_id")
                or f"{info.get('tool','')}-{info.get('message_id','')}"
            )
            pending_calls[tool_call_id] = info
            continue

        if event_type == "tool_result":
            tool_call_id = (
                info.get("tool_call_id")
                or f"{info.get('tool','')}-{info.get('message_id','')}"
            )
            call_info = pending_calls.pop(tool_call_id, None)
            ts = str(
                info.get("timestamp")
                or (call_info.get("timestamp") if call_info else "")
            )
            events.append(
                Event(
                    kind="tool_end",
                    tool=info.get("tool", ""),
                    input=call_info.get("arguments", {}) if call_info else {},
                    output=info.get("output", ""),
                    duration_ms=info.get("duration_ms"),
                    ts=ts,
                    session_id=session_id,
                    raw=info,
                    plan_text=call_info.get("plan_text", "") if call_info else "",
                    model=call_info.get("model", "") if call_info else "",
                    usage=call_info.get("usage", {}) if call_info else {},
                    status=info.get("status", ""),
                    exit_code=info.get("exit_code"),
                )
            )
            continue

        if event_type == "llm_response":
            events.append(
                Event(
                    kind="llm_response",
                    output=info.get("text", ""),
                    ts=info.get("timestamp", ""),
                    session_id=session_id,
                    raw=info,
                    plan_text=info.get("text", ""),
                    model=info.get("model", ""),
                    usage=info.get("usage", {}),
                )
            )

    return events
