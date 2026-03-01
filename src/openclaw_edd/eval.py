"""
Eval command implementation

Responsibilities:
- run: Run evaluation cases
- gen-cases: Generate case template
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import session_reader, store
from .models import EvalCase, EvalResult, Event
from .tracer import _is_turn_end

# Built-in cases
BUILTIN_CASES = [
    {
        "id": "weather_shanghai",
        "message": "What's the weather in Shanghai today?",
        "expect_tools": ["get_weather"],
        "description": "Weather query basic check",
    },
    {
        "id": "mysql_slow_query",
        "message": "Any slow queries in MySQL recently?",
        "expect_tools": ["query_metrics"],
        "description": "MySQL slow query check",
    },
    {
        "id": "no_tool_chitchat",
        "message": "Hello",
        "forbidden_tools": ["query_db", "execute_sql"],
        "description": "Chat should not call tools",
    },
]


def load_cases(cases_file: str = None) -> list[EvalCase]:
    """Load test cases"""
    if not cases_file:
        return [EvalCase(**c) for c in BUILTIN_CASES]

    cases_path = Path(cases_file)

    # Support JSONL format (golden dataset)
    if cases_path.suffix == ".jsonl":
        try:
            cases = []
            with open(cases_path, "r", encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line)
                    # Convert golden dataset format to EvalCase
                    for conv in record.get("conversation", []):
                        case_data = {
                            "id": record["id"],
                            "message": conv["user"],
                            "description": record.get("description", ""),
                            "tags": record.get("tags", []),
                        }
                        # Extract expectations from assertions
                        for assertion in conv.get("assert", []):
                            if assertion["type"] == "tool_called":
                                if "expect_tools" not in case_data:
                                    case_data["expect_tools"] = []
                                case_data["expect_tools"].append(assertion["value"])
                            elif assertion["type"] == "tool_order":
                                case_data["expect_tools_ordered"] = assertion["value"]
                                case_data["expect_tools_ordered_strict"] = (
                                    assertion.get("strict", False)
                                )
                            elif assertion["type"] == "not_tool_called":
                                if "forbidden_tools" not in case_data:
                                    case_data["forbidden_tools"] = []
                                case_data["forbidden_tools"].append(assertion["value"])
                            elif assertion["type"] == "contains":
                                if "expect_output_contains" not in case_data:
                                    case_data["expect_output_contains"] = []
                                case_data["expect_output_contains"].append(
                                    assertion["value"]
                                )
                            elif assertion["type"] == "command_contains":
                                if "expect_commands" not in case_data:
                                    case_data["expect_commands"] = []
                                case_data["expect_commands"].append(assertion["value"])
                            elif assertion["type"] == "command_order":
                                case_data["expect_commands_ordered"] = assertion[
                                    "value"
                                ]
                            elif assertion["type"] == "not_command_contains":
                                if "forbidden_commands" not in case_data:
                                    case_data["forbidden_commands"] = []
                                case_data["forbidden_commands"].append(
                                    assertion["value"]
                                )
                            elif assertion["type"] == "tool_args":
                                if "expect_tool_args" not in case_data:
                                    case_data["expect_tool_args"] = {}
                                tool_name = assertion["tool"]
                                case_data["expect_tool_args"][tool_name] = assertion[
                                    "args"
                                ]

                        cases.append(EvalCase(**case_data))
            return cases
        except Exception as e:
            print(f"✗ Failed to load JSONL cases: {e}")
            sys.exit(1)

    # JSON
    if cases_path.suffix == ".json":
        try:
            with open(cases_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [EvalCase(**c) for c in data.get("cases", [])]
        except Exception as e:
            print(f"✗ Failed to load JSON cases: {e}")
            sys.exit(1)

    # YAML
    try:
        import yaml

        with open(cases_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return [EvalCase(**c) for c in data.get("cases", [])]
    except ImportError:
        print("✗ PyYAML is required: pip install pyyaml")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Failed to load cases: {e}")
        sys.exit(1)


def send_message(agent: str, message: str, use_local: bool = False) -> str:
    """Send a message to the agent and return session_id"""
    try:
        cmd = ["openclaw", "agent", f"--agent={agent}", "--json", "--message", message]
        if use_local:
            cmd.insert(4, "--local")  # Insert --local before --json

        # Increase timeout for OpenClaw processing
        timeout = 120 if use_local else 60

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        # Check command execution
        if result.returncode != 0:
            print(
                f"⚠ openclaw command returned non-zero exit code: {result.returncode}"
            )
            if result.stderr:
                print(f"   Error: {result.stderr[:200]}")
            return None

        # Parse JSON response to extract sessionId
        try:
            data = json.loads(result.stdout)
            # Gateway mode: result.meta.agentMeta.sessionId
            session_id = (
                data.get("result", {})
                .get("meta", {})
                .get("agentMeta", {})
                .get("sessionId")
            )
            if session_id:
                return session_id
            # Local mode: meta.agentMeta.sessionId
            session_id = data.get("meta", {}).get("agentMeta", {}).get("sessionId")
            if session_id:
                return session_id

            # If missing, print debug info
            print(f"⚠ Failed to extract sessionId from response")
            print(f"   Response keys: {list(data.keys())}")

        except json.JSONDecodeError as e:
            print(f"⚠ JSON parse failed: {e}")
            print(f"   Response content: {result.stdout[:200]}")

        return None
    except subprocess.TimeoutExpired:
        print(f"⚠ Send message timed out（{timeout}）")
        return None
    except Exception as e:
        print(f"⚠ Send message failed: {e}")
        return None


def wait_for_completion(session_id: str, timeout_s: int, log_dir: str) -> bool:
    """Wait for agent completion"""
    start_time = time.time()
    last_line_count = 0
    stable_count = 0

    while time.time() - start_time < timeout_s:
        elapsed = int(time.time() - start_time)

        try:
            result = subprocess.run(
                [
                    "openclaw",
                    "logs",
                    "--json",
                    f"--session={session_id}",
                    f"--since={elapsed}s",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            lines = result.stdout.strip().splitlines()

            # Check completion marker
            for line in lines:
                from .tracer import parse_line

                entry = parse_line(line)
                if entry and _is_turn_end(entry):
                    return True

            # Check stability
            if len(lines) == last_line_count:
                stable_count += 1
                if stable_count >= 3:
                    return True
            else:
                stable_count = 0

            last_line_count = len(lines)

        except Exception:
            pass

        time.sleep(2)

    return False


def _lower(s: str) -> str:
    return s.lower()


def _get_exec_commands(events: list[Event]) -> list[str]:
    commands = []
    for e in events:
        if e.kind != "tool_end" or e.tool != "exec":
            continue
        if isinstance(e.input, dict):
            cmd = e.input.get("command", "")
            if isinstance(cmd, str) and cmd:
                commands.append(cmd)
    return commands


def _check_commands(exec_commands: list[str], expect_commands: list[str]) -> dict:
    details = {}
    for pattern in expect_commands:
        if not isinstance(pattern, str):
            continue
        pat = pattern.lower()
        matched_in = [cmd for cmd in exec_commands if pat in cmd.lower()]
        details[pattern] = {
            "passed": len(matched_in) > 0,
            "matched_in": matched_in[:3],
        }
    return {
        "passed": all(v["passed"] for v in details.values()) if details else True,
        "details": details,
        "actual_commands": exec_commands,
    }


def _check_forbidden_commands(
    exec_commands: list[str], forbidden_commands: list[str]
) -> dict:
    violations = {}
    for pattern in forbidden_commands:
        if not isinstance(pattern, str):
            continue
        pat = pattern.lower()
        matched = [cmd for cmd in exec_commands if pat in cmd.lower()]
        if matched:
            violations[pattern] = matched[:3]
    return {
        "passed": len(violations) == 0,
        "violations": violations,
    }


def _check_commands_ordered(
    exec_commands: list[str], expect_ordered: list[str]
) -> dict:
    idx = 0
    for cmd in exec_commands:
        if idx < len(expect_ordered) and expect_ordered[idx].lower() in cmd.lower():
            idx += 1
    return {
        "passed": idx == len(expect_ordered),
        "matched_count": idx,
        "expected_count": len(expect_ordered),
        "expected": expect_ordered,
        "actual_commands": exec_commands,
    }


def check_assertions(
    case: EvalCase, events: list[Event], final_output: str
) -> tuple[bool, list[str], dict]:
    """Check assertions"""
    failures: list[str] = []
    checks: dict = {}
    tool_names = [e.tool for e in events if e.kind == "tool_end"]

    # expect_tools
    if case.expect_tools:
        missing = set(case.expect_tools) - set(tool_names)
        if missing:
            failures.append(
                f"Missing required tool calls: {', '.join(missing)}（: {tool_names}）"
            )
        checks["tool_called"] = {
            "passed": len(missing) == 0,
            "expected": case.expect_tools,
            "actual": tool_names,
            "missing": sorted(missing),
        }

    # expect_tools_ordered
    if case.expect_tools_ordered:
        if case.expect_tools_ordered_strict:
            # EXACT ：
            if tool_names != case.expect_tools_ordered:
                failures.append(
                    f"Tool order mismatch (strict):  {case.expect_tools_ordered}， {tool_names}"
                )
        else:
            # IN_ORDER ：，
            it = iter(tool_names)
            if not all(tool in it for tool in case.expect_tools_ordered):
                failures.append(
                    f"Tool order mismatch:  {case.expect_tools_ordered}， {tool_names}"
                )
        checks["tool_ordered"] = {
            "passed": not any("Tool order mismatch" in f for f in failures),
            "expected": case.expect_tools_ordered,
            "actual": tool_names,
            "strict": case.expect_tools_ordered_strict,
        }

    # forbidden_tools
    if case.forbidden_tools:
        forbidden_used = set(case.forbidden_tools) & set(tool_names)
        if forbidden_used:
            failures.append(f"Forbidden tool was called: {', '.join(forbidden_used)}")
        checks["forbidden_tools"] = {
            "passed": len(forbidden_used) == 0,
            "expected": case.forbidden_tools,
            "violations": sorted(forbidden_used),
        }

    exec_commands = _get_exec_commands(events)

    if case.expect_commands:
        cmd_check = _check_commands(exec_commands, case.expect_commands)
        checks["commands"] = cmd_check
        if not cmd_check["passed"]:
            missing = [k for k, v in cmd_check["details"].items() if not v["passed"]]
            failures.append(f"Missing expected command keywords: {', '.join(missing)}")

    if case.forbidden_commands:
        forbid_check = _check_forbidden_commands(exec_commands, case.forbidden_commands)
        checks["forbidden_commands"] = forbid_check
        if not forbid_check["passed"]:
            failures.append(
                f"Forbidden command keywords found: {', '.join(forbid_check['violations'].keys())}"
            )

    if case.expect_commands_ordered:
        order_check = _check_commands_ordered(
            exec_commands, case.expect_commands_ordered
        )
        checks["commands_ordered"] = order_check
        if not order_check["passed"]:
            failures.append(
                f"Command order mismatch:  {case.expect_commands_ordered}， {order_check['matched_count']}/{order_check['expected_count']}"
            )

    # expect_output_contains
    if case.expect_output_contains:
        output_lower = final_output.lower()
        missing_keywords = [
            kw for kw in case.expect_output_contains if kw.lower() not in output_lower
        ]
        if missing_keywords:
            failures.append(
                f"Output missing expected keywords: {', '.join(missing_keywords)}"
            )
        checks["output_contains"] = {
            "passed": len(missing_keywords) == 0,
            "expected": case.expect_output_contains,
            "missing": missing_keywords,
        }

    # expect_tool_args
    if case.expect_tool_args:
        tool_arg_details = {}
        tool_arg_passed = True
        for tool_name, expected_args in case.expect_tool_args.items():
            #  event
            actual_events = [
                e for e in events if e.kind == "tool_end" and e.tool == tool_name
            ]
            if not actual_events:
                failures.append(
                    f"Tool not called; cannot validate arguments: {tool_name}"
                )
                tool_arg_details[tool_name] = {"passed": False, "missing_tool": True}
                tool_arg_passed = False
                continue
            tool_arg_details[tool_name] = {"passed": True, "args": {}}
            for key, expected_val in expected_args.items():
                matched = False
                for ev in actual_events:
                    actual_val = (
                        ev.input.get(key) if isinstance(ev.input, dict) else None
                    )
                    if isinstance(expected_val, str):
                        if expected_val.lower() in str(actual_val).lower():
                            matched = True
                            break
                    else:
                        if str(actual_val) == str(expected_val):
                            matched = True
                            break
                tool_arg_details[tool_name]["args"][key] = {
                    "expected": expected_val,
                    "matched": matched,
                }
                if not matched:
                    failures.append(
                        f"Tool argument mismatch: {tool_name}.{key} ={expected_val}"
                    )
                    tool_arg_passed = False
            if not tool_arg_details[tool_name]["args"]:
                tool_arg_details[tool_name]["passed"] = True
            else:
                tool_arg_details[tool_name]["passed"] = all(
                    v["matched"] for v in tool_arg_details[tool_name]["args"].values()
                )
        checks["tool_args"] = {
            "passed": tool_arg_passed,
            "details": tool_arg_details,
        }

    return len(failures) == 0, failures, checks


def _parse_event_ts(ts: str) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _filter_events_by_time(
    events: list[Event], start_dt: datetime, end_dt: datetime
) -> list[Event]:
    if not start_dt or not end_dt:
        return events
    filtered: list[Event] = []
    for ev in events:
        ev_dt = _parse_event_ts(ev.ts)
        if ev_dt is None:
            filtered.append(ev)
            continue
        if start_dt <= ev_dt <= end_dt:
            filtered.append(ev)
    return filtered


def run_eval_case(
    case: EvalCase,
    dry_run: bool,
    log_dir: str,
    use_local: bool = False,
    session_id_override: str = None,
) -> EvalResult:
    """Run a single test case"""
    start_time = time.time()
    session_id = session_id_override  # Use provided session_id for dry-run testing
    events = []
    final_output = ""

    start_dt = None
    end_dt = None

    if not dry_run:
        start_dt = datetime.now(timezone.utc)
        session_id = send_message(case.agent, case.message, use_local)
        if not session_id:
            return EvalResult(
                case=case,
                passed=False,
                events=[],
                final_output="",
                duration_s=time.time() - start_time,
                failures=["Failed to send message or get session_id"],
                checks={},
                timestamp=datetime.now().isoformat(),
            )

        wait_for_completion(session_id, case.timeout_s, log_dir)
        end_dt = datetime.now(timezone.utc)

    # Extract events (session file first, then state)
    if session_id:
        events = session_reader.build_events_from_session(session_id)
        if not events:
            state = store.state_load(session_id)
            events = _events_from_state(state, session_id)

    # Filter events to case time window to avoid leakage
    if start_dt and end_dt:
        events = _filter_events_by_time(events, start_dt, end_dt)

    # Get final output
    for event in reversed(events):
        if event.kind == "llm_response":
            final_output = event.output
            break

    # Check assertions
    passed, failures, checks = check_assertions(case, events, final_output)

    return EvalResult(
        case=case,
        passed=passed,
        events=events,
        final_output=final_output,
        duration_s=time.time() - start_time,
        failures=failures,
        checks=checks,
        session_id=session_id,
        timestamp=datetime.now().isoformat(),
    )


def _events_from_state(state: dict, session_id: str) -> list[Event]:
    """Build Event list from state file (compatible)"""
    events: list[Event] = []
    if not isinstance(state, dict):
        return events

    raw_events = state.get("events") or state.get("trace") or []
    if not isinstance(raw_events, list):
        return events

    for item in raw_events:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind") or item.get("type")
        if kind == "tool":
            kind = "tool_end"
        if kind not in ("tool_start", "tool_end", "llm_response"):
            continue
        events.append(
            Event(
                kind=kind,
                tool=item.get("tool", ""),
                input=item.get("input", {}) or item.get("arguments", {}) or {},
                output=item.get("output", "") or item.get("out_text", "") or "",
                duration_ms=item.get("duration_ms") or item.get("durationMs"),
                ts=item.get("ts") or item.get("timestamp", ""),
                session_id=session_id,
                raw=item,
            )
        )

    return events


def generate_html_report(results: list[EvalResult], output_file: str):
    """Generate HTML report"""
    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)
    pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>OpenClaw EDD Report</title>
    <style>
        body {{ font-family: 'Monaco', 'Menlo', monospace; background: #1e1e1e; color: #d4d4d4; padding: 20px; }}
        h1 {{ color: #4ec9b0; }}
        .summary {{ background: #252526; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .case {{ background: #252526; padding: 15px; border-radius: 5px; margin-bottom: 15px; }}
        .pass {{ color: #4ec9b0; }}
        .fail {{ color: #f48771; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; }}
        .badge-pass {{ background: #4ec9b0; color: #1e1e1e; }}
        .badge-fail {{ background: #f48771; color: #1e1e1e; }}
        pre {{ background: #1e1e1e; padding: 10px; border-radius: 3px; overflow-x: auto; }}
    </style>
</head>
<body>
    <h1>⚡ OpenClaw EDD Report</h1>
    <div class="summary">
        <strong>Total:</strong> {total_count} cases<br>
        <strong>Passed:</strong> <span class="pass">{passed_count}</span><br>
        <strong>Failed:</strong> <span class="fail">{total_count - passed_count}</span><br>
        <strong>Passed:</strong> {pass_rate:.1f}%
    </div>
"""

    for result in results:
        status_class = "pass" if result.passed else "fail"
        badge_class = "badge-pass" if result.passed else "badge-fail"
        status_text = "PASS" if result.passed else "FAIL"

        html += f"""
    <div class="case">
        <h3>{result.case.id} <span class="badge {badge_class}">{status_text}</span></h3>
        <p><strong>Message:</strong> {result.case.message}</p>
        <p><strong>Duration:</strong> {result.duration_s:.2f}s</p>
        <p><strong>Tool chain:</strong> {', '.join(result.tool_names) if result.tool_names else '()'}</p>
"""

        if result.failures:
            html += "        <p><strong class='fail'>Failed:</strong></p><ul>"
            for failure in result.failures:
                html += f"<li>{failure}</li>"
            html += "</ul>"

        if result.final_output:
            output_preview = result.final_output[:200]
            if len(result.final_output) > 200:
                output_preview += "..."
            html += (
                f"        <p><strong>Output:</strong></p><pre>{output_preview}</pre>"
            )

        html += "    </div>"

    html += """
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)


def cmd_run(args):
    """Run command entry"""
    # Load cases
    if getattr(args, "quickstart", False) and args.cases:
        print("✗ --quickstart cannot be used with --cases")
        sys.exit(1)
    if getattr(args, "quickstart", False) and args.case:
        print("✗ --quickstart cannot be used with --case")
        sys.exit(1)

    if args.case:
        cases = [
            EvalCase(
                id="cli_case",
                message=args.case,
                expect_tools=args.expect_tools or [],
                expect_commands=getattr(args, "expect_commands", None) or [],
                expect_commands_ordered=getattr(args, "expect_commands_ordered", None)
                or [],
                forbidden_tools=args.forbidden_tools or [],
                forbidden_commands=getattr(args, "forbidden_commands", None) or [],
                agent=args.agent,
            )
        ]
    elif getattr(args, "quickstart", False):
        from importlib import resources

        quickstart_ref = resources.files("openclaw_edd").joinpath(
            "quickstart_cases.json"
        )
        with resources.as_file(quickstart_ref) as quickstart_path:
            cases = load_cases(str(quickstart_path))
    else:
        cases = load_cases(args.cases)

    #  tags
    if args.tags:
        tag_set = set(args.tags)
        cases = [c for c in cases if tag_set & set(c.tags)]

    if not cases:
        print("✗ No cases to run")
        sys.exit(1)

    print(f"⚡ OpenClaw Eval  —  {len(cases)} cases\n")

    validation_only = args.dry_run and not getattr(args, "session", None)
    if validation_only:
        print("ℹ Dry-run  session，cases，Message\n")

    results = []
    for case in cases:
        print(f"→ {case.id}: {case.message}")

        if validation_only:
            result = EvalResult(
                case=case,
                passed=True,
                events=[],
                final_output="",
                duration_s=0.0,
                failures=[],
                checks={},
                session_id=None,
                timestamp=datetime.now().isoformat(),
            )
        else:
            result = run_eval_case(
                case,
                args.dry_run,
                args.log_dir,
                getattr(args, "local", False),
                getattr(args, "session", None),
            )
        results.append(result)

        if result.passed:
            print(f"  [✓ PASS] {result.duration_s:.1f}s")
        else:
            print(f"  [✗ FAIL] {result.duration_s:.1f}s")

        # Tool chain
        if result.tool_names:
            print(f"  Tool chain: {', '.join(result.tool_names)}")
        else:
            print(f"  Tool chain: ()")

        #  trace（）
        if getattr(args, "show_trace", False) and result.events:
            print(f"  \n  📋 Detailed trace:")
            for i, event in enumerate(result.events, 1):
                if event.kind == "tool_start":
                    print(f"    {i}. 🔧 {event.tool} start")
                    if event.input:
                        input_str = str(event.input)[:100]
                        if len(str(event.input)) > 100:
                            input_str += "..."
                        print(f"       input: {input_str}")
                elif event.kind == "tool_end":
                    duration = f" ({event.duration_ms}ms)" if event.duration_ms else ""
                    print(f"    {i}. ✓ {event.tool} complete{duration}")
                    if event.output:
                        output_str = str(event.output)[:100]
                        if len(str(event.output)) > 100:
                            output_str += "..."
                        print(f"       Output: {output_str}")
                elif event.kind == "llm_response":
                    output_str = event.output[:100]
                    if len(event.output) > 100:
                        output_str += "..."
                    print(f"    {i}. 💬 LLM response: {output_str}")
            print()

        # Output（ trace）
        if not getattr(args, "show_trace", False) and result.final_output:
            output_preview = result.final_output[:80]
            if len(result.final_output) > 80:
                output_preview += "..."
            print(f"  Output: {output_preview}")

        if result.failures:
            for failure in result.failures:
                print(f"  ✗ {failure}")

        print()

    # Summary
    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)
    pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0
    avg_duration = (
        sum(r.duration_s for r in results) / total_count if total_count > 0 else 0
    )

    # Group stats by eval_type
    regression_results = [r for r in results if r.case.eval_type == "regression"]
    capability_results = [r for r in results if r.case.eval_type == "capability"]

    print("─" * 60)

    if regression_results:
        reg_passed = sum(1 for r in regression_results if r.passed)
        reg_total = len(regression_results)
        reg_rate = (reg_passed / reg_total * 100) if reg_total > 0 else 0
        print(f"📊 Regression Eval（Regression）")
        print("─" * 60)
        print(f"Passed: {reg_passed}/{reg_total}  ({reg_rate:.0f}%)")
        if reg_rate < 100:
            print("  ⚠ Below 100% needs attention")
        failed_reg = [r for r in regression_results if not r.passed]
        if failed_reg:
            print(f"FAIL: {', '.join(r.case.id for r in failed_reg)}")
        print()

    if capability_results:
        cap_passed = sum(1 for r in capability_results if r.passed)
        cap_total = len(capability_results)
        cap_rate = (cap_passed / cap_total * 100) if cap_total > 0 else 0
        print(f"📈 Capability Eval（Capability）")
        print("─" * 60)
        print(f"Passed: {cap_passed}/{cap_total}  ({cap_rate:.0f}%)")
        print("  ℹ Normal; this is a climb metric")
        passed_cap = [r for r in capability_results if r.passed]
        if passed_cap:
            print(f"PASS: {', '.join(r.case.id for r in passed_cap[:5])}")
            if len(passed_cap) > 5:
                print(f"      ...  {len(passed_cap) - 5} ")
        print()

    print("─" * 60)
    print(f"complete: {passed_count}/{total_count} Passed ({pass_rate:.0f}%)")

    failed_cases = [r for r in results if not r.passed]
    if failed_cases:
        print(f"Failed {len(failed_cases)} :")
        for r in failed_cases:
            print(
                f"  - {r.case.id}: {r.failures[0] if r.failures else 'Unknown error'}"
            )

    print(f"Duration: {avg_duration:.1f}s")

    # Baseline comparison
    if getattr(args, "baseline", None):
        baseline_path = Path(args.baseline)
        if baseline_path.exists():
            print("\n" + "─" * 60)
            print("📊 Baseline comparison")
            print("─" * 60)

            try:
                with open(baseline_path, "r", encoding="utf-8") as f:
                    baseline_results = json.load(f)

                #  baseline
                baseline_passed = sum(
                    1 for r in baseline_results if r.get("passed", False)
                )
                baseline_total = len(baseline_results)
                baseline_rate = (
                    (baseline_passed / baseline_total * 100)
                    if baseline_total > 0
                    else 0
                )
                baseline_avg = (
                    sum(r.get("duration_s", 0) for r in baseline_results)
                    / baseline_total
                    if baseline_total > 0
                    else 0
                )

                #
                rate_delta = pass_rate - baseline_rate
                time_delta = avg_duration - baseline_avg

                print(
                    f"Pass rate:  {baseline_rate:.0f}% → {pass_rate:.0f}%  ({rate_delta:+.0f}%)"
                )
                print(
                    f"Duration:   {baseline_avg:.1f}s → {avg_duration:.1f}s  ({time_delta:+.1f}s)"
                )

                #  case
                baseline_map = {r["case"]["id"]: r for r in baseline_results}
                current_map = {r.case.id: r for r in results}

                print("\nDetailed changes:")
                for case_id in set(baseline_map.keys()) | set(current_map.keys()):
                    baseline = baseline_map.get(case_id)
                    current = current_map.get(case_id)

                    if not baseline:
                        print(f"  + {case_id}  NEW")
                    elif not current:
                        print(f"  - {case_id}  REMOVED")
                    else:
                        baseline_status = "PASS" if baseline.get("passed") else "FAIL"
                        current_status = "PASS" if current.passed else "FAIL"

                        if baseline_status != current_status:
                            symbol = "✓" if current_status == "PASS" else "✗"
                            print(
                                f"  {symbol} {case_id}  {baseline_status} → {current_status}"
                            )

                            # Tool chain
                            baseline_tools = baseline.get("tool_names", [])
                            current_tools = [
                                e.tool for e in current.events if e.kind == "tool_end"
                            ]
                            if baseline_tools != current_tools:
                                print(
                                    f"     Tool chain: {baseline_tools} → {current_tools}"
                                )

            except Exception as e:
                print(f"⚠  baseline Failed: {e}")
        else:
            print(f"\n⚠ Baseline file not found: {args.baseline}")

    # Output
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in results], f, indent=2, ensure_ascii=False)
        print(f"\n✓ JSON report saved: {args.output_json}")

    if args.output_html:
        generate_html_report(results, args.output_html)
        print(f"✓ HTML report saved: {args.output_html}")

    if getattr(args, "summary_line", False):
        status = "PASS" if passed_count == total_count else "FAIL"
        print(f"{status} {passed_count}/{total_count} ({pass_rate:.1f}%)")

    # CI integration
    if failed_cases:
        sys.exit(1)


def cmd_gen_cases(args):
    """gen-cases command entry"""
    template = """# OpenClaw EDD cases
cases:
  - id: example_weather
    message: "What's the weather in Shanghai today?"
    eval_type: regression          # "regression" | "capability"
    expect_tools:
      - exec
    expect_commands:
      - "open-meteo"
    expect_output_contains:
      - "Shanghai"
    timeout_s: 30
    tags: [smoke, weather]
    description: "Weather query basic check"

  - id: example_forbidden
    message: "Hello"
    eval_type: regression
    forbidden_tools:
      - exec
    tags: [smoke]
    description: "Chat should not call tools"

  - id: example_ordered
    message: "List files then count them"
    eval_type: regression
    expect_tools_ordered:
      - exec
    # expect_tools_ordered_strict: false  # False=IN_ORDER, True=EXACT
    tags: [integration]
    description: "Tool call order check"

  - id: example_tool_args
    message: "Any slow queries in MySQL in the last hour?"
    eval_type: regression
    expect_tools:
      - exec
    expect_tool_args:              # Tool argument assertions (white-box)
      exec:
        command: "p99_latency"     # String values use substring match
    tags: [mysql, sre]
    description: "MySQL slow query check (with args)"

  - id: example_capability
    message: "Forecast MySQL storage growth for next week"
    eval_type: capability          # Capability cases start low
    expect_tools:
      - exec
    tags: [mysql, advanced]
    description: "MySQL capacity forecast (new capability)"
"""

    output_file = args.output or "cases.yaml"

    if Path(output_file).exists() and not args.force:
        print(f"✗ File already exists: {output_file}（ --force ）")
        sys.exit(1)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(template)

    print(f"✓ cases: {output_file}")
