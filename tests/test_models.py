from openclaw_edd.models import EvalCase, EvalResult, Event


def test_event_to_dict_filters_empty_values():
    event = Event(kind="tool_end", tool="exec")
    data = event.to_dict()
    assert data["kind"] == "tool_end"
    assert data["tool"] == "exec"
    assert "output" not in data


def test_eval_result_tool_names():
    event = Event(kind="tool_end", tool="exec")
    case = EvalCase(id="c1", message="hi")
    result = EvalResult(
        case=case,
        passed=True,
        events=[event],
        final_output="ok",
        duration_s=0.1,
    )
    assert result.tool_names == ["exec"]
