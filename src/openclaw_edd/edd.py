"""
EDD loop commands

Responsibilities:
- suggest: Generate suggestions from failed cases
- apply: Apply suggestions to workspace
- diff: Compare two runs
- mine: Mine golden cases from logs
- export: Export golden dataset (JSONL)
"""

from __future__ import annotations

import csv
import difflib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, DefaultDict, Optional, TypedDict, cast

from .tracer import (
    _is_turn_end,
    extract_events,
    get_workspace,
    read_all_logs,
    sessions_from_logs,
)

# ============================================================================
# suggest
# ============================================================================


def analyze_failure(result: dict, workspace: Path) -> dict:
    """Analyze a failed result and propose fixes."""
    case_id = result["case"]["id"]
    message = result["case"]["message"]
    failures = result.get("failures", [])

    suggestion: dict = {
        "case_id": case_id,
        "message": message,
        "failures": failures,
        "recommendations": [],
    }

    for failure in failures:
        if "Missing required tool calls" in failure:
            import re

            match = re.search(r"Missing required tool calls: ([^()]+)", failure)
            if match:
                missing_tools = [t.strip() for t in match.group(1).split(",")]
                missing_tool = missing_tools[0] if missing_tools else ""
                if not missing_tool:
                    continue

                skills_dir = workspace / "skills"
                skill_file = skills_dir / f"{missing_tool}.md"

                if skill_file.exists():
                    suggestion["recommendations"].append(
                        {
                            "type": "modify_skill",
                            "file": f"skills/{missing_tool}.md",
                            "action": f"Add missing tool call steps: {missing_tool}",
                        }
                    )
                else:
                    suggestion["recommendations"].append(
                        {
                            "type": "create_skill",
                            "file": f"skills/{case_id}.md",
                            "action": (
                                f"Create a new skill that calls tool: {missing_tool}"
                            ),
                        }
                    )

        elif "Tool order mismatch" in failure:
            suggestion["recommendations"].append(
                {
                    "type": "modify_skill",
                    "file": f"skills/{case_id}.md",
                    "action": "Adjust tool call order",
                }
            )

        elif "Forbidden tool was called" in failure:
            suggestion["recommendations"].append(
                {"type": "modify_tools", "file": "TOOLS.md", "action": "Add rule"}
            )

        elif "Output missing expected keywords" in failure:
            suggestion["recommendations"].append(
                {
                    "type": "modify_skill",
                    "file": f"skills/{case_id}.md",
                    "action": "Specify output format requirements",
                }
            )

        elif "Tool argument mismatch" in failure:
            import re

            match = re.search(r"Tool argument mismatch: (\\w+)\\.(\\w+) =(\\S+)", failure)
            if match:
                tool_name, arg_key, expected = match.groups()
                suggestion["recommendations"].append(
                    {
                        "type": "modify_skill",
                        "file": f"skills/{case_id}.md",
                        "action": (
                            f"Clarify tool arguments: {tool_name} {arg_key}={expected}"
                        ),
                    }
                )

    return suggestion


def cmd_suggest(args: Any) -> None:
    """Suggest command entry."""
    if not Path(args.report).exists():
        print(f"✗ Report file not found: {args.report}")
        sys.exit(1)

    with open(args.report, "r", encoding="utf-8") as f:
        results = json.load(f)

    workspace = get_workspace(args.workspace)
    failed_results = [r for r in results if not r.get("passed", False)]

    if not failed_results:
        print("✓ All cases passed; no suggestions needed")
        return

    print(f"📋 Analyze {len(failed_results)} \n")

    for result in failed_results:
        suggestion = analyze_failure(result, workspace)

        print(f"=== case: {suggestion['case_id']} ===")
        print(f"Message: {suggestion['message']}")
        for failure in suggestion["failures"]:
            print(f"Failure reason: {failure}")

        for rec in suggestion["recommendations"]:
            print(f"Suggested file: {rec['file']}")
            print(f"Suggested change: {rec['action']}")

        print("─" * 60)
        print()


# ============================================================================
# apply
# ============================================================================

READONLY_FILES = {"SOUL.md", "AGENTS.md", "USER.md", "BOOTSTRAP.md", "IDENTITY.md"}


class SessionStats(TypedDict):
    """Aggregated session statistics."""

    session_id: str
    first_ts: str
    last_ts: str
    tool_count: int
    turns: int
    agent: str


def apply_suggestion(
    suggestion: dict, workspace: Path, auto_yes: bool = False
) -> None:
    """Apply a single suggestion."""
    for rec in suggestion["recommendations"]:
        file_path = workspace / rec["file"]

        #
        if file_path.name in READONLY_FILES:
            print(f"[SKIP] {file_path.name} is read-only; please edit manually")
            print(f"Suggested change: {rec['action']}")
            continue

        #
        if rec["type"] == "create_skill":
            content = f"""# {suggestion['case_id']}

## Trigger
{suggestion['message']}

## Steps
1. {rec['action']}

## Output format
Return a natural-language response with relevant details
"""
            if file_path.exists():
                print(f"[SKIP] {file_path} already exists")
                continue

            #  diff
            print(f"\n[CREATE] {file_path}")
            print(content)

            if not auto_yes:
                confirm = input("Confirm create? (y/n): ")
                if confirm.lower() != "y":
                    print("[SKIP]")
                    continue

            #
            file_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = file_path.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(content)
            tmp_file.rename(file_path)
            print(f"✓ Created: {file_path}")

        elif rec["type"] == "modify_tools":
            if not file_path.exists():
                print(f"[SKIP] {file_path} does not exist")
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                original = f.read()

            # Find "## Usage" section
            if "## Usage" in original:
                new_content = original + f"\n- {rec['action']}\n"
            else:
                new_content = original + f"\n\n## Usage\n- {rec['action']}\n"

            #  diff
            print(f"\n[MODIFY] {file_path}")
            diff = difflib.unified_diff(
                original.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=str(file_path),
                tofile=str(file_path),
            )
            print("".join(diff))

            if not auto_yes:
                confirm = input("Confirm update? (y/n): ")
                if confirm.lower() != "y":
                    print("[SKIP]")
                    continue

            #
            tmp_file = file_path.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            tmp_file.rename(file_path)
            print(f"✓ Updated: {file_path}")


def cmd_apply(args: Any) -> None:
    """Apply command entry."""
    if not Path(args.suggestion_file).exists():
        print(f"✗ Suggested filedoes not exist: {args.suggestion_file}")
        sys.exit(1)

    # Suggested file（， suggest Output）
    print("⚠ apply requires suggest output")
    print("This is a simplified implementation")


# ============================================================================
# diff
# ============================================================================


def cmd_diff(args: Any) -> None:
    """Diff command entry."""
    if not Path(args.before).exists() or not Path(args.after).exists():
        print("✗ Report file not found")
        sys.exit(1)

    with open(args.before, "r", encoding="utf-8") as f:
        before_results = json.load(f)
    with open(args.after, "r", encoding="utf-8") as f:
        after_results = json.load(f)

    #
    before_passed = sum(1 for r in before_results if r.get("passed", False))
    after_passed = sum(1 for r in after_results if r.get("passed", False))
    before_rate = before_passed / len(before_results) * 100 if before_results else 0
    after_rate = after_passed / len(after_results) * 100 if after_results else 0

    before_avg = (
        sum(r.get("duration_s", 0) for r in before_results) / len(before_results)
        if before_results
        else 0
    )
    after_avg = (
        sum(r.get("duration_s", 0) for r in after_results) / len(after_results)
        if after_results
        else 0
    )

    print("📊 EDD Diff")
    print(f"baseline : {args.before}")
    print(f"new      : {args.after}")
    print("─" * 60)

    #  eval_type
    before_regression = [
        r
        for r in before_results
        if r.get("case", {}).get("eval_type", "regression") == "regression"
    ]
    after_regression = [
        r
        for r in after_results
        if r.get("case", {}).get("eval_type", "regression") == "regression"
    ]
    before_capability = [
        r
        for r in before_results
        if r.get("case", {}).get("eval_type", "regression") == "capability"
    ]
    after_capability = [
        r
        for r in after_results
        if r.get("case", {}).get("eval_type", "regression") == "capability"
    ]

    if before_regression or after_regression:
        before_reg_rate = (
            (
                sum(1 for r in before_regression if r.get("passed", False))
                / len(before_regression)
                * 100
            )
            if before_regression
            else 0
        )
        after_reg_rate = (
            (
                sum(1 for r in after_regression if r.get("passed", False))
                / len(after_regression)
                * 100
            )
            if after_regression
            else 0
        )
        delta_reg = after_reg_rate - before_reg_rate
        symbol_reg = "✓" if delta_reg >= 0 else "✗"
        print(
            f"Regression: {before_reg_rate:.0f}% → {after_reg_rate:.0f}% {symbol_reg} ({delta_reg:+.0f}%)"
        )

    if before_capability or after_capability:
        before_cap_rate = (
            (
                sum(1 for r in before_capability if r.get("passed", False))
                / len(before_capability)
                * 100
            )
            if before_capability
            else 0
        )
        after_cap_rate = (
            (
                sum(1 for r in after_capability if r.get("passed", False))
                / len(after_capability)
                * 100
            )
            if after_capability
            else 0
        )
        delta_cap = after_cap_rate - before_cap_rate
        symbol_cap = "✓" if delta_cap >= 0 else "✗"
        print(
            f"Capability: {before_cap_rate:.0f}% → {after_cap_rate:.0f}% {symbol_cap} ({delta_cap:+.1f}%)"
        )

    print()
    print(
        f"Pass rate:  {before_rate:.0f}% → {after_rate:.0f}%  ({after_rate - before_rate:+.0f}%)"
    )
    print(
        f"Duration:       {before_avg:.1f}s → {after_avg:.1f}s  ({after_avg - before_avg:+.1f}s)"
    )
    print()

    #  case_id
    before_map = {r["case"]["id"]: r for r in before_results}
    after_map = {r["case"]["id"]: r for r in after_results}

    for case_id in set(before_map.keys()) | set(after_map.keys()):
        before = before_map.get(case_id)
        after = after_map.get(case_id)

        if not before:
            print(f"{case_id}   NEW")
        elif not after:
            print(f"{case_id}   REMOVED")
        else:
            before_status = "PASS" if before.get("passed") else "FAIL"
            after_status = "PASS" if after.get("passed") else "FAIL"

            if before_status != after_status:
                symbol = "✓" if after_status == "PASS" else "✗"
                print(f"{case_id}   {before_status} → {after_status}  {symbol}")

                # Tool chain change
                before_tools = before.get("tool_names", [])
                after_tools = after.get("tool_names", [])
                if before_tools != after_tools:
                    print(f"  : {before_tools} → {after_tools}")

                # Failure reason
                before_failures = before.get("failures", [])
                after_failures = after.get("failures", [])
                if before_failures and not after_failures:
                    print(f"  Failure reason: {before_failures[0]}")
                elif after_failures and not before_failures:
                    print(f"  Failure reason: {after_failures[0]}")
            else:
                print(f"{case_id}   {before_status} → {after_status}  (unchanged)")


# ============================================================================
# mine
# ============================================================================


def cmd_mine(args: Any) -> None:
    """Mine command entry."""
    from .tracer import (
        LOG_DIR,
        extract_events,
        read_logs_for_session,
        sessions_from_logs,
    )

    log_dir = Path(args.log_dir) if args.log_dir else LOG_DIR

    #  sessions（）
    print("📦 Scanning log files...")
    all_sessions = sessions_from_logs(log_dir)

    if not all_sessions:
        print("✗ No sessions found")
        return

    #  session
    successful_sessions = []
    for session in all_sessions:
        if session["tool_count"] >= args.min_tools and session["turns"] > 0:
            successful_sessions.append(session)

    if not successful_sessions:
        print("✗ No sessions matched criteria")
        return

    print(f"📦 From {len(successful_sessions)} sessions, extracting cases")

    # Read existing cases (dedupe)
    existing_messages = set()
    output_file = Path(args.output) if args.output else Path("mined_cases.yaml")
    if output_file.exists():
        try:
            import yaml  # type: ignore[import-untyped]

            with open(output_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "cases" in data:
                    for case in data.get("cases", []):
                        existing_messages.add(case.get("message", ""))
        except:
            pass

    # Extract new cases
    new_cases = []
    for session in successful_sessions:
        session_id = session["session_id"]

        # Read session logs
        entries = read_logs_for_session(log_dir, session_id)
        events = extract_events(entries, session_id)

        # Extract message
        message = None
        for entry in entries:
            if "user_message" in entry:
                message = entry["user_message"]
                break
            elif "input" in entry and isinstance(entry["input"], str):
                message = entry["input"]
                break
            elif "prompt" in entry:
                message = entry["prompt"]
                break

        if not message or message in existing_messages:
            continue

        # Extract tool sequence
        tool_names = [e.tool for e in events if e.kind == "tool_end"]

        case = {
            "id": f"mined_{session_id[:8]}",
            "message": message,
            "expect_tools": list(dict.fromkeys(tool_names)),  #
            "expect_tools_ordered": tool_names,
            "tags": ["mined"],
            "description": f"From session {session_id[:8]} ， {session['last_ts'][:10]}",
        }

        new_cases.append(case)
        existing_messages.add(message)

    if not new_cases:
        print("✓ No new cases to add")
        return

    #
    output_data = {"cases": new_cases}

    try:
        import yaml  # type: ignore[import-untyped]

        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump(output_data, f, allow_unicode=True, default_flow_style=False)
        print(f"✓ Generated {len(new_cases)} : {output_file}")
    except ImportError:
        print("✗ PyYAML is required: pip install pyyaml")
        sys.exit(1)


# ============================================================================
# export
# ============================================================================


def cmd_export(args: Any) -> None:
    """Export command entry - export golden dataset."""
    from .tracer import LOG_DIR, _is_tool_end, _is_turn_end, read_all_logs

    log_dir = Path(args.log_dir) if args.log_dir else LOG_DIR
    workspace = get_workspace(args.workspace)

    # （）
    print("📦 Scanning log files...")
    entries = read_all_logs(log_dir)

    if not entries:
        print("✗ No log entries found")
        return

    #  sessions
    sessions_dict: DefaultDict[str, SessionStats] = defaultdict(
        lambda: {
            "session_id": "",
            "first_ts": "",
            "last_ts": "",
            "tool_count": 0,
            "turns": 0,
            "agent": "",
        }
    )

    for entry in entries:
        session_id = entry.get("session_id", "")
        if not session_id:
            continue

        session = sessions_dict[session_id]
        session["session_id"] = session_id

        ts = entry.get("ts", "")
        if not session["first_ts"] or ts < session["first_ts"]:
            session["first_ts"] = ts
        if not session["last_ts"] or ts > session["last_ts"]:
            session["last_ts"] = ts

        if _is_tool_end(entry):
            session["tool_count"] += 1

        if _is_turn_end(entry):
            session["turns"] += 1

        if not session["agent"] and "agent" in entry:
            session["agent"] = entry["agent"]

    sessions = list(sessions_dict.values())

    #  merge report（）
    merge_data = {}
    if args.merge_report and Path(args.merge_report).exists():
        with open(args.merge_report, "r", encoding="utf-8") as f:
            report_results = json.load(f)
            for r in report_results:
                if r.get("passed"):
                    message = r["case"]["message"]
                    merge_data[message] = r.get("final_output", "")

    #  session
    successful_sessions = [
        s for s in sessions if s["tool_count"] >= args.min_tools and s["turns"] > 0
    ]

    if not successful_sessions:
        print("✗ No sessions matched criteria")
        return

    print(f"📦 From {len(successful_sessions)} sessions, export golden dataset")

    # ： session  skill
    session_data_list: list[dict[str, Any]] = []
    skill_to_tools: DefaultDict[str, set[str]] = defaultdict(set)  # skill_triggered ->  skill  session

    for session in successful_sessions:
        session_id = session["session_id"]

        # Read session logs
        from .tracer import read_logs_for_session

        entries = read_logs_for_session(log_dir, session_id)
        events = extract_events(entries, session_id)

        # Extract user message
        user_message = None
        for entry in entries:
            for key in ["user_message", "input", "prompt"]:
                if key in entry and isinstance(entry[key], str):
                    user_message = entry[key]
                    break
            if user_message:
                break

        if not user_message:
            continue

        # Build golden_tool_sequence
        golden_tools = []
        for event in events:
            if event.kind == "tool_end":
                golden_tools.append(
                    {
                        "name": event.tool,
                        "args": event.input,
                        "output_summary": event.output[:200] if event.output else "",
                    }
                )

        # Get golden_output
        golden_output = ""
        golden_output_source = "log"
        for event in reversed(events):
            if event.kind == "llm_response":
                golden_output = event.output
                break

        # From merge report Output
        if user_message in merge_data:
            golden_output = merge_data[user_message]
            golden_output_source = "report"

        # Match skill
        tool_names: list[str] = [str(t["name"]) for t in golden_tools]
        skill_triggered = None
        skills_dir = workspace / "skills"
        if skills_dir.exists():
            for skill_file in skills_dir.glob("*.md"):
                skill_name = skill_file.stem.replace("_", "").replace("-", "")
                for tool in tool_names:
                    tool_clean = tool.replace("_", "").replace("-", "")
                    if skill_name in tool_clean or tool_clean in skill_name:
                        skill_triggered = f"skills/{skill_file.name}"
                        break
                if skill_triggered:
                    break

        # Record data
        session_data = {
            "session": session,
            "session_id": session_id,
            "user_message": user_message,
            "golden_tools": golden_tools,
            "tool_names": tool_names,
            "golden_output": golden_output,
            "golden_output_source": golden_output_source,
            "skill_triggered": skill_triggered,
        }
        session_data_list.append(session_data)

        # Collect tools grouped by skill
        skill_key = skill_triggered if skill_triggered else "__no_skill__"
        skill_to_tools[skill_key].update(tool_names)

    # ：Generate records including not_tool_called
    records = []
    for session_data in session_data_list:
        session_id = session_data["session_id"]
        session = session_data["session"]
        user_message = session_data["user_message"]
        golden_tools = session_data["golden_tools"]
        tool_names = session_data["tool_names"]
        golden_output = session_data["golden_output"]
        golden_output_source = session_data["golden_output_source"]
        skill_triggered = session_data["skill_triggered"]

        # Generate assertions
        asserts: list[dict[str, Any]] = []
        for tool in tool_names:
            asserts.append({"type": "tool_called", "value": tool})
        if len(tool_names) > 1:
            asserts.append({"type": "tool_order", "value": tool_names, "strict": False})

        # Generate tool_args assertions
        for tool_data in golden_tools:
            if tool_data["args"]:
                asserts.append(
                    {
                        "type": "tool_args",
                        "tool": tool_data["name"],
                        "args": tool_data["args"],
                    }
                )

        # Extract keywords with simple frequency
        if golden_output:
            words = golden_output.split()
            word_freq = Counter(w for w in words if len(w) > 2)
            top_keywords = [w for w, _ in word_freq.most_common(3)]
            for kw in top_keywords:
                asserts.append({"type": "contains", "value": kw})

        # Generate not_tool_called
        skill_key = skill_triggered if skill_triggered else "__no_skill__"
        all_tools_in_skill: set[str] = skill_to_tools[skill_key]

        #  session  > 1 Generate not_tool_called
        if (
            len(
                [
                    s
                    for s in session_data_list
                    if (
                        s["skill_triggered"] if s["skill_triggered"] else "__no_skill__"
                    )
                    == skill_key
                ]
            )
            > 1
        ):
            #  session  session
            forbidden_tools = all_tools_in_skill - set(tool_names)
            for tool in sorted(forbidden_tools):
                asserts.append({"type": "not_tool_called", "value": tool})

        # Build record
        record = {
            "id": f"{session_id[:8]}_1",
            "description": f"From session {session_id[:8]} ，{session['last_ts'][:10]}",
            "source": "mined",
            "tags": ["mined"],
            "conversation": [
                {
                    "turn": 1,
                    "user": user_message,
                    "golden_tool_sequence": golden_tools,
                    "golden_output": golden_output,
                    "assert": asserts,
                }
            ],
            "metadata": {
                "session_id": session_id,
                "agent": session.get("agent", "main"),
                "extracted_at": datetime.now().isoformat(),
                "skill_triggered": skill_triggered,
                "golden_output_source": golden_output_source,
            },
        }

        records.append(record)

    # Output
    output_file = Path(args.output)

    if args.format == "csv":
        # CSV format
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "id",
                    "description",
                    "user",
                    "golden_tools",
                    "golden_output",
                    "skill_triggered",
                    "session_id",
                    "extracted_at",
                ],
            )
            writer.writeheader()

            for record in records:
                conv_list = cast(list[dict[str, Any]], record["conversation"])
                conv = conv_list[0]
                golden_tool_seq = cast(list[dict[str, Any]], conv["golden_tool_sequence"])
                tools_str = ", ".join(str(t["name"]) for t in golden_tool_seq)
                golden_output = cast(str, conv["golden_output"])
                metadata = cast(dict[str, Any], record["metadata"])
                writer.writerow(
                    {
                        "id": record["id"],
                        "description": record["description"],
                        "user": conv["user"],
                        "golden_tools": tools_str,
                        "golden_output": golden_output[:200],
                        "skill_triggered": metadata.get("skill_triggered") or "",
                        "session_id": metadata.get("session_id", ""),
                        "extracted_at": metadata.get("extracted_at", ""),
                    }
                )

        print(f"✓ Exported {len(records)}  CSV: {output_file}")

    else:
        # JSONL format
        with open(output_file, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(f"✓ Exported {len(records)}  JSONL: {output_file}")


# ============================================================================
# Main entry
# ============================================================================


def cmd_edd(args: Any) -> None:
    """EDD command dispatch."""
    if args.edd_cmd == "suggest":
        cmd_suggest(args)
    elif args.edd_cmd == "apply":
        cmd_apply(args)
    elif args.edd_cmd == "diff":
        cmd_diff(args)
    elif args.edd_cmd == "mine":
        cmd_mine(args)
    elif args.edd_cmd == "judge":
        cmd_judge(args)
    elif args.edd_cmd == "export":
        cmd_export(args)


# ============================================================================
# judge
# ============================================================================


def cmd_judge(args: Any) -> None:
    """Judge command entry - LLM scoring."""
    import os

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"✗ Report file not found: {args.report}")
        sys.exit(1)

    with open(report_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    #  LLM client
    provider = getattr(args, "provider", "anthropic")

    if provider == "anthropic":
        try:
            from anthropic import Anthropic  # type: ignore[import-not-found]

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                print("✗ ANTHROPIC_API_KEY not set")
                sys.exit(1)
            client = Anthropic(api_key=api_key)
            client_type = "anthropic"
        except ImportError:
            print("✗ anthropic is required: pip install anthropic")
            sys.exit(1)
    elif provider == "openai":
        try:
            from openai import OpenAI  # type: ignore[import-not-found]

            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                print("✗ OPENAI_API_KEY not set")
                sys.exit(1)
            client = OpenAI(api_key=api_key)
            client_type = "openai"
        except ImportError:
            print("✗ openai is required: pip install openai")
            sys.exit(1)
    elif provider == "deepseek":
        try:
            from openai import OpenAI  # type: ignore[import-not-found]

            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                print("✗ DEEPSEEK_API_KEY not set")
                sys.exit(1)
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            client_type = "openai"
        except ImportError:
            print("✗ openai is required: pip install openai")
            sys.exit(1)
    else:
        print(f"✗ Unsupported provider: {provider}")
        sys.exit(1)

    print(f"📊 Evaluating with LLM {len(results)} ...")
    print(f"Provider: {provider}")
    print(f"Model: {args.model}\n")

    judged_results = []

    for i, result in enumerate(results, 1):
        case_id = result["case"]["id"]
        message = result["case"]["message"]
        tool_names = result.get("tool_names", [])
        final_output = result.get("final_output", "")
        passed = result.get("passed", False)

        print(f"[{i}/{len(results)}] Evaluating {case_id}...")

        prompt = f"""Evaluate the AI agent execution result:

User input: {message}

Tool call sequence: {tool_names}

Final output: {final_output}

Test status: {"passed" if passed else "failed"}

Please score the following dimensions (0-10):
1. Tool selection: Were the selected tools appropriate and necessary?
2. Tool order: Was the tool call order reasonable?
3. Output quality: Is the output accurate, complete, and useful?
4. Overall performance: Overall assessment.

Return JSON:
{{
  "tool_selection_score": <0-10>,
  "tool_order_score": <0-10>,
  "output_quality_score": <0-10>,
  "overall_score": <0-10>,
  "reasoning": "<short rationale>"
}}"""

        try:
            #  LLM API
            if client_type == "anthropic":
                response = client.messages.create(
                    model=args.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = response.content[0].text
            else:  # openai or deepseek
                response = client.chat.completions.create(
                    model=args.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                )
                response_text = response.choices[0].message.content

            #  JSON
            import re

            json_match = re.search(r"\{[^}]+\}", response_text, re.DOTALL)
            if json_match:
                judgment = json.loads(json_match.group(0))
            else:
                #  JSON，
                judgment = json.loads(response_text)

            result_copy = result.copy()
            result_copy["llm_judgment"] = {
                **judgment,
                "model": args.model,
                "provider": provider,
                "raw_response": response_text,
            }
            judged_results.append(result_copy)

            print(f"  ✓ Overall score: {judgment.get('overall_score', 'N/A')}/10")

        except Exception as e:
            print(f"  ✗ Evaluating: {e}")
            result_copy = result.copy()
            result_copy["llm_judgment"] = {"error": str(e)}
            judged_results.append(result_copy)

    # Output
    print("\n" + "─" * 60)
    print("📊 Evaluating")
    print("─" * 60)

    valid_judgments = [
        r
        for r in judged_results
        if "llm_judgment" in r and "overall_score" in r["llm_judgment"]
    ]
    if valid_judgments:
        avg_overall = sum(
            r["llm_judgment"]["overall_score"] for r in valid_judgments
        ) / len(valid_judgments)
        avg_tool_selection = sum(
            r["llm_judgment"]["tool_selection_score"] for r in valid_judgments
        ) / len(valid_judgments)
        avg_tool_order = sum(
            r["llm_judgment"]["tool_order_score"] for r in valid_judgments
        ) / len(valid_judgments)
        avg_output_quality = sum(
            r["llm_judgment"]["output_quality_score"] for r in valid_judgments
        ) / len(valid_judgments)

        print(f"Overall score: {avg_overall:.1f}/10")
        print(f"Average tool selection: {avg_tool_selection:.1f}/10")
        print(f"Average tool order: {avg_tool_order:.1f}/10")
        print(f"Output: {avg_output_quality:.1f}/10")

    #
    output_path = (
        Path(args.output) if args.output else report_path.with_suffix(".judged.json")
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(judged_results, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Evaluating: {output_path}")
