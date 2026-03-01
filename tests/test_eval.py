from datetime import datetime, timezone, timedelta

from openclaw_edd.models import Event, EvalCase
from openclaw_edd import eval as eval_module


def _ev(tool, command, ts):
    return Event(
        kind="tool_end",
        tool=tool,
        input={"command": command},
        output="",
        duration_ms=1,
        ts=ts,
        session_id="s"
    )


def test_expect_commands_matching():
    events = [
        _ev("exec", "curl -s https://example.com/weather?city=Tokyo", "2026-03-01T01:00:00Z")
    ]
    case = EvalCase(
        id="cmd_match",
        message="",
        expect_commands=["curl", "tokyo"],
    )
    passed, failures, checks = eval_module.check_assertions(case, events, "Tokyo weather")
    assert passed
    assert failures == []
    assert checks["commands"]["passed"] is True


def test_forbidden_commands():
    events = [
        _ev("exec", "rm -rf /", "2026-03-01T01:00:00Z")
    ]
    case = EvalCase(
        id="forbid",
        message="",
        forbidden_commands=["rm -rf /"],
    )
    passed, failures, checks = eval_module.check_assertions(case, events, "")
    assert not passed
    assert not passed and len(failures) > 0
    assert checks["forbidden_commands"]["passed"] is False


def test_commands_ordered():
    events = [
        _ev("exec", "ls", "2026-03-01T01:00:00Z"),
        _ev("exec", "wc -l", "2026-03-01T01:00:01Z"),
    ]
    case = EvalCase(
        id="ordered",
        message="",
        expect_commands_ordered=["ls", "wc"],
    )
    passed, failures, checks = eval_module.check_assertions(case, events, "")
    assert passed
    assert checks["commands_ordered"]["passed"] is True


def test_expect_tool_args_substring():
    events = [
        _ev("exec", "bash ./skills/ceresdb/scripts/check_health.sh prod-01", "2026-03-01T01:00:00Z")
    ]
    case = EvalCase(
        id="tool_args",
        message="",
        expect_tool_args={"exec": {"command": "check_health"}},
    )
    passed, failures, checks = eval_module.check_assertions(case, events, "")
    assert passed
    assert checks["tool_args"]["passed"] is True


def test_session_isolation_time_window():
    base = datetime(2026, 3, 1, 1, 0, 0, tzinfo=timezone.utc)
    events = [
        _ev("exec", "old", (base - timedelta(seconds=10)).isoformat()),
        _ev("exec", "inside", (base + timedelta(seconds=1)).isoformat()),
        _ev("exec", "new", (base + timedelta(seconds=10)).isoformat()),
    ]
    start_dt = base
    end_dt = base + timedelta(seconds=5)
    filtered = eval_module._filter_events_by_time(events, start_dt, end_dt)
    cmds = [e.input.get("command") for e in filtered]
    assert "inside" in cmds
    assert "old" not in cmds
    assert "new" not in cmds
