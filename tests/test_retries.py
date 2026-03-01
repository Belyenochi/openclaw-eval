"""Tests for retry detection."""

from datetime import datetime

from openclaw_edd.eval import _check_retries
from openclaw_edd.models import Event


def _ev(tool: str, command: str, ts: str) -> Event:
    """Create a tool_end event."""
    return Event(
        kind="tool_end",
        tool=tool,
        input={"command": command},
        output="",
        duration_ms=100,
        ts=ts,
        session_id="s",
    )


def test_no_retries():
    """Test with no consecutive identical calls - should pass."""
    events = [
        _ev("exec", "ls", "2026-03-01T01:00:00Z"),
        _ev("exec", "cat file.txt", "2026-03-01T01:00:01Z"),
        _ev("exec", "wc -l", "2026-03-01T01:00:02Z"),
    ]
    result = _check_retries(events, max_retries=3)

    assert result["passed"] is True
    assert result["max_consecutive"] == 1
    assert result["limit"] == 3
    assert result["retries"] == []


def test_retry_storm_detected():
    """Test detecting 5 identical consecutive calls (weather retry storm)."""
    events = [
        _ev("exec", 'curl -s "https://wttr.in/Shanghai"', "2026-03-01T01:00:00Z"),
        _ev("exec", 'curl -s "https://wttr.in/Shanghai"', "2026-03-01T01:00:01Z"),
        _ev("exec", 'curl -s "https://wttr.in/Shanghai"', "2026-03-01T01:00:02Z"),
        _ev("exec", 'curl -s "https://wttr.in/Shanghai"', "2026-03-01T01:00:03Z"),
        _ev("exec", 'curl -s "https://wttr.in/Shanghai"', "2026-03-01T01:00:04Z"),
    ]
    result = _check_retries(events, max_retries=3)

    assert result["passed"] is False
    assert result["max_consecutive"] == 5
    assert result["limit"] == 3
    assert len(result["retries"]) == 1
    assert result["retries"][0]["tool"] == "exec"
    assert "curl" in result["retries"][0]["command"]
    assert result["retries"][0]["count"] == 5


def test_max_retries_allowed():
    """Test with exactly max_retries - should pass."""
    events = [
        _ev("exec", "curl https://example.com", "2026-03-01T01:00:00Z"),
        _ev("exec", "curl https://example.com", "2026-03-01T01:00:01Z"),
        _ev("exec", "curl https://example.com", "2026-03-01T01:00:02Z"),
    ]
    result = _check_retries(events, max_retries=3)

    assert result["passed"] is True
    assert result["max_consecutive"] == 3
    assert len(result["retries"]) == 1
    assert result["retries"][0]["count"] == 3


def test_multiple_retry_streaks():
    """Test multiple separate retry streaks."""
    events = [
        _ev("exec", "cmd1", "2026-03-01T01:00:00Z"),
        _ev("exec", "cmd1", "2026-03-01T01:00:01Z"),
        _ev("read", "/tmp/file", "2026-03-01T01:00:02Z"),
        _ev("read", "/tmp/file", "2026-03-01T01:00:03Z"),
        _ev("read", "/tmp/file", "2026-03-01T01:00:04Z"),
    ]
    result = _check_retries(events, max_retries=2)

    assert result["passed"] is False
    assert result["max_consecutive"] == 3
    assert len(result["retries"]) == 2


def test_no_max_retries_skipped():
    """Test that None max_retries skips the check."""
    events = [
        _ev("exec", "curl", "2026-03-01T01:00:00Z"),
        _ev("exec", "curl", "2026-03-01T01:00:01Z"),
        _ev("exec", "curl", "2026-03-01T01:00:02Z"),
    ]
    result = _check_retries(events, max_retries=None)

    assert result["passed"] is True
    assert result["skipped"] is True


def test_different_tools_not_retry():
    """Test that different tools with same input don't count as retry."""
    events = [
        _ev("read", "/tmp/file", "2026-03-01T01:00:00Z"),
        _ev("write", "/tmp/file", "2026-03-01T01:00:01Z"),
        _ev("exec", "/tmp/file", "2026-03-01T01:00:02Z"),
    ]
    result = _check_retries(events, max_retries=2)

    assert result["passed"] is True
    assert result["max_consecutive"] == 1


def test_empty_events():
    """Test with empty event list."""
    events: list[Event] = []
    result = _check_retries(events, max_retries=3)

    # With empty list, should still work (no crash)
    assert result["passed"] is True


def test_single_event():
    """Test with single event."""
    events = [_ev("exec", "ls", "2026-03-01T01:00:00Z")]
    result = _check_retries(events, max_retries=3)

    assert result["passed"] is True
    assert result["max_consecutive"] == 1
    assert result["retries"] == []
