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


def test_thinking_content_preserved():
    """Thinking blocks should be captured as plan_text and thinking field."""
    message = {
        "type": "message",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "thinking",
                    "thinking": "用户询问 CeresDB 集群的核心组件。我需要先阅读 DOMAIN.md。",
                },
                {
                    "type": "toolCall",
                    "id": "tc_006",
                    "name": "read",
                    "arguments": {"path": "/root/.openclaw/workspace/DOMAIN.md"},
                },
            ],
        },
        "timestamp": "2026-01-01T00:00:00Z",
        "id": "msg_006",
    }
    result = extract_tool_call_info(message)
    assert result is not None
    assert result["event"] == "tool_call"
    assert result["tool"] == "read"
    assert "CeresDB" in result["plan_text"]
    assert "DOMAIN.md" in result["plan_text"]
    # thinking field should contain raw thinking content
    assert "CeresDB" in result["thinking"]
    assert "DOMAIN.md" in result["thinking"]
    # plan_text should have [thinking] prefix for backward compatibility
    assert "[thinking]" in result["plan_text"]


def test_mixed_thinking_and_text():
    """Both thinking and text blocks should be concatenated."""
    message = {
        "type": "message",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I'll help you with that."},
                {
                    "type": "thinking",
                    "thinking": "This requires checking the database.",
                },
                {
                    "type": "toolCall",
                    "id": "tc_007",
                    "name": "exec",
                    "arguments": {"command": "mysql -e 'SHOW TABLES'"},
                },
            ],
        },
        "timestamp": "2026-01-01T00:00:00Z",
        "id": "msg_007",
    }
    result = extract_tool_call_info(message)
    assert result is not None
    assert result["event"] == "tool_call"
    assert "I'll help you with that." in result["plan_text"]
    assert "checking the database" in result["plan_text"]
    # thinking field should only contain thinking content
    assert result["thinking"] == "This requires checking the database."
    # plan_text should have [thinking] prefix for backward compatibility
    assert "[thinking] This requires checking the database." in result["plan_text"]


def test_thinking_in_llm_response():
    """Thinking blocks should be captured in llm_response events."""
    message = {
        "type": "message",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Here's my analysis."},
                {
                    "type": "thinking",
                    "thinking": "Let me think through this step by step.",
                },
                {"type": "text", "text": "Final answer."},
            ],
        },
        "timestamp": "2026-01-01T00:00:00Z",
        "id": "msg_008",
        "model": "claude-sonnet-4-6",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }
    result = extract_tool_call_info(message)
    assert result is not None
    assert result["event"] == "llm_response"
    assert "Here's my analysis." in result["text"]
    assert "Final answer." in result["text"]
    # thinking field should contain thinking content
    assert result["thinking"] == "Let me think through this step by step."
    # plan_text should include thinking with prefix
    assert "[thinking] Let me think through this step by step." in result["text"]
