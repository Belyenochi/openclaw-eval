"""Session file reader for OpenClaw sessions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from .models import Event

SESSION_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"


def resolve_latest_session(agent: str = "main") -> str | None:
    """Find the most recently modified session file."""
    session_dir = Path.home() / ".openclaw" / "agents" / agent / "sessions"
    jsonl_files = sorted(
        session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not jsonl_files:
        return None
    return jsonl_files[0].stem  # filename without .jsonl


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


def extract_tool_call_info(message: dict) -> dict | None:
    """Extract tool-call or response info from a session message.

    Legacy function kept for backward compatibility with tests.
    New code should use build_events_from_session directly.

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

        # Collect text, thinking, and tool calls separately
        plan_text_parts = []
        thinking_parts = []
        tool_call_info = None

        for item in content:
            if item.get("type") == "text" and item.get("text"):
                plan_text_parts.append(item.get("text").strip())
            elif item.get("type") == "thinking" and item.get("thinking"):
                # Capture thinking content separately
                thinking_text = item.get("thinking").strip()
                thinking_parts.append(thinking_text)
                # Also add to plan_text with prefix for backward compatibility
                plan_text_parts.append(f"[thinking] {thinking_text}")
            elif item.get("type") == "toolCall" and tool_call_info is None:
                # Capture the first toolCall
                tool_call_info = {
                    "event": "tool_call",
                    "tool": item.get("name"),
                    "tool_call_id": item.get("id"),
                    "arguments": item.get("arguments", {}),
                    "timestamp": message.get("timestamp"),
                    "message_id": message.get("id"),
                }

        # Prepare thinking and plan_text
        thinking = "\n".join(thinking_parts)
        plan_text = "\n".join(plan_text_parts)
        # For llm_response: text should only contain actual text content, not thinking
        text_only = "\n".join(
            [p for p in plan_text_parts if not p.startswith("[thinking] ")]
        )

        # If we found a toolCall, return it with plan_text and thinking
        if tool_call_info:
            tool_call_info["plan_text"] = plan_text
            tool_call_info["thinking"] = thinking
            return tool_call_info

        # No toolCall, but has text - return as llm_response
        if plan_text_parts:
            return {
                "event": "llm_response",
                "text": text_only,
                "thinking": thinking,
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


def build_events_from_session(session_id: str) -> list[Event]:
    """Build events from a session file.

    Args:
        session_id: Session ID.

    Returns:
        List of Event objects. Event sequence:
        - llm_turn: represents one complete LLM call (with thinking, tool_calls/text, usage)
        - tool_end: follows each llm_turn that has tool_calls (binds to parent llm_turn)
    """
    events: list[Event] = []
    messages = list(read_session_messages(session_id))

    # Step 1: Build toolCallId -> toolResult message index
    tool_results: dict[str, dict] = {}
    for msg in messages:
        if msg.get("type") != "message":
            continue
        m = msg.get("message", {})
        if m.get("role") == "toolResult":
            tool_results[m.get("toolCallId", "")] = msg

    # Step 2: Process assistant messages
    for msg in messages:
        if msg.get("type") != "message":
            continue
        m = msg.get("message", {})

        if m.get("role") != "assistant":
            continue

        content = m.get("content", [])
        thinking = ""
        text = ""
        tool_calls_in_turn = []

        for block in content:
            block_type = block.get("type")
            if block_type == "thinking":
                thinking = block.get("thinking", "")
            elif block_type == "text":
                text = block.get("text", "")
            elif block_type == "toolCall":
                tool_calls_in_turn.append(block)

        # Create llm_turn event
        llm_turn_event = Event(
            kind="llm_turn",
            thinking=thinking,
            text=text,
            tool_calls=tool_calls_in_turn,
            model=m.get("model", ""),
            usage=m.get("usage", {}),
            stop_reason=m.get("stopReason", ""),
            ts=str(msg.get("timestamp", "")),
            session_id=session_id,
            raw=m,
        )
        events.append(llm_turn_event)

        # Step 3: For each toolCall, find corresponding toolResult and create tool_end
        for tc in tool_calls_in_turn:
            tc_id = tc.get("id", "")
            result_msg = tool_results.get(tc_id)
            if result_msg:
                rm = result_msg.get("message", {})
                output_text = ""
                for item in rm.get("content", []):
                    if item.get("type") == "text":
                        output_text = item.get("text", "")
                        break

                details = rm.get("details", {})
                events.append(
                    Event(
                        kind="tool_end",
                        tool=tc.get("name", ""),
                        input=tc.get("arguments", {}),
                        output=output_text,
                        thinking=thinking,  # Bind to parent llm_turn's thinking
                        model=m.get("model", ""),
                        usage=m.get("usage", {}),  # Bind to parent llm_turn's usage
                        duration_ms=details.get("durationMs"),
                        status=details.get("status", ""),
                        exit_code=details.get("exitCode"),
                        ts=str(result_msg.get("timestamp", "")),
                        session_id=session_id,
                        raw=rm,
                    )
                )

    return events


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
