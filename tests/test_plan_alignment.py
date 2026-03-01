"""Tests for plan alignment feature."""

from openclaw_edd.session_reader import extract_tool_call_info


def test_mixed_content_preserves_plan_text():
    """Text before toolCall must be captured as plan_text."""
    message = {
        "type": "message",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I'll check slow queries now."},
                {
                    "type": "toolCall",
                    "id": "tc_001",
                    "name": "exec",
                    "arguments": {"command": "show processlist"},
                },
            ],
        },
        "timestamp": "2026-01-01T00:00:00Z",
        "id": "msg_001",
    }
    result = extract_tool_call_info(message)
    assert result is not None
    assert result["event"] == "tool_call"
    assert result["tool"] == "exec"
    assert result["plan_text"] == "I'll check slow queries now."


def test_toolcall_only_has_empty_plan_text():
    message = {
        "type": "message",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "toolCall",
                    "id": "tc_002",
                    "name": "read",
                    "arguments": {"path": "/tmp/foo"},
                },
            ],
        },
        "timestamp": "2026-01-01T00:00:00Z",
        "id": "msg_002",
    }
    result = extract_tool_call_info(message)
    assert result is not None
    assert result["event"] == "tool_call"
    assert result["plan_text"] == ""


def test_text_only_returns_llm_response():
    message = {
        "type": "message",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Here is the answer."},
            ],
        },
        "timestamp": "2026-01-01T00:00:00Z",
        "id": "msg_003",
    }
    result = extract_tool_call_info(message)
    assert result is not None
    assert result["event"] == "llm_response"
    assert result["text"] == "Here is the answer."


def test_multiple_text_items_concatenated():
    """Multiple text items should be joined with newlines."""
    message = {
        "type": "message",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "First line of thought."},
                {"type": "text", "text": "Second line of thought."},
                {
                    "type": "toolCall",
                    "id": "tc_003",
                    "name": "exec",
                    "arguments": {"command": "ls"},
                },
            ],
        },
        "timestamp": "2026-01-01T00:00:00Z",
        "id": "msg_004",
    }
    result = extract_tool_call_info(message)
    assert result is not None
    assert result["event"] == "tool_call"
    assert result["plan_text"] == "First line of thought.\nSecond line of thought."


def test_text_after_toolcall_ignored_for_plan():
    """Text that comes after toolCall is still captured in plan_text."""
    message = {
        "type": "message",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Before tool call."},
                {
                    "type": "toolCall",
                    "id": "tc_004",
                    "name": "exec",
                    "arguments": {"command": "ls"},
                },
                {"type": "text", "text": "After tool call."},
            ],
        },
        "timestamp": "2026-01-01T00:00:00Z",
        "id": "msg_005",
    }
    result = extract_tool_call_info(message)
    assert result is not None
    assert result["event"] == "tool_call"
    # All text items are captured
    assert "Before tool call." in result["plan_text"]
    assert "After tool call." in result["plan_text"]
