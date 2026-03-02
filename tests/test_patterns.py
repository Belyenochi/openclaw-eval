"""Tests for action pattern classification."""

from openclaw_edd.models import Event
from openclaw_edd.patterns import ActionClassifier, BUILTIN_PATTERNS


def test_classify_ls():
    c = ActionClassifier()
    assert "list_files" in c.classify("ls -la /tmp")


def test_classify_curl_weather():
    c = ActionClassifier()
    actions = c.classify('curl -s "https://api.open-meteo.com/v1/forecast?latitude=31"')
    assert "http_request" in actions
    assert "weather_query" in actions or "metric_query" in actions


def test_classify_unknown():
    c = ActionClassifier()
    assert c.classify("echo hello") == ["unknown"]


def test_custom_patterns():
    custom = {"my_action": [r"custom_cmd"]}
    c = ActionClassifier(custom_patterns=custom)
    assert "my_action" in c.classify("custom_cmd --flag")


def test_check_actions():
    from openclaw_edd.eval import _check_actions

    events = [
        Event(kind="tool_end", tool="exec", input={"command": "ls -la"}),
        Event(kind="tool_end", tool="exec", input={"command": "wc -l file.txt"}),
    ]
    classifier = ActionClassifier()
    result = _check_actions(events, ["list_files", "count_items"], classifier)
    assert result["passed"]


def test_check_actions_missing():
    from openclaw_edd.eval import _check_actions

    events = [
        Event(kind="tool_end", tool="exec", input={"command": "ls -la"}),
    ]
    classifier = ActionClassifier()
    result = _check_actions(events, ["list_files", "database_operation"], classifier)
    assert not result["passed"]
    assert "database_operation" in result["missing"]


def test_check_actions_ordered():
    from openclaw_edd.eval import _check_actions_ordered

    events = [
        Event(kind="tool_end", tool="exec", input={"command": "ls -la"}),
        Event(kind="tool_end", tool="exec", input={"command": "wc -l file.txt"}),
    ]
    classifier = ActionClassifier()
    result = _check_actions_ordered(events, ["list_files", "count_items"], classifier)
    assert result["passed"]
    assert result["matched_count"] == 2


def test_classify_events():
    c = ActionClassifier()
    events = [
        Event(kind="tool_end", tool="exec", input={"command": "ls -la"}),
        Event(kind="tool_end", tool="exec", input={"command": "cat file.txt"}),
    ]
    results = c.classify_events(events)
    assert len(results) == 2
    assert "list_files" in results[0]["actions"]
    assert "file_read" in results[1]["actions"]


def test_builtin_patterns_exist():
    assert "list_files" in BUILTIN_PATTERNS
    assert "count_items" in BUILTIN_PATTERNS
    assert "http_request" in BUILTIN_PATTERNS
    assert "weather_query" in BUILTIN_PATTERNS
    assert "database_operation" in BUILTIN_PATTERNS
