"""CLI entry point for openclaw-edd."""

from __future__ import annotations

import argparse
import sys

from . import edd, eval as eval_module, watcher


def main() -> None:
    """Run the CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="edd",
        description="OpenClaw EDD toolkit - Evaluation-Driven Development",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug output")
    parser.add_argument("--log-dir", default="/tmp/openclaw", help="Log directory")

    subparsers = parser.add_subparsers(dest="cmd", required=True, help="Subcommands")

    watch_parser = subparsers.add_parser("watch", help="Stream tool events")
    watch_parser.add_argument("--session", help="Filter by session ID prefix")
    watch_parser.add_argument("--from-start", action="store_true", help="Read from file start")
    watch_parser.add_argument(
        "--save-artifacts",
        action="store_true",
        help="Save tool outputs as artifacts",
    )
    watch_parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    watch_parser.add_argument(
        "--pid-file", default="/tmp/openclaw_edd_watch.pid", help="PID file"
    )
    watch_parser.add_argument(
        "--daemon-log", default="/tmp/openclaw_edd_watch.log", help="Daemon log file"
    )

    trace_parser = subparsers.add_parser("trace", help="Replay a session event chain")
    trace_parser.add_argument("--session", required=True, help="Session ID")
    trace_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )

    state_parser = subparsers.add_parser("state", help="View or modify session state")
    state_parser.add_argument("--session", required=True, help="Session ID")
    state_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )
    state_parser.add_argument("--set", action="append", help="Set key=value")
    state_parser.add_argument("--delete", action="append", help="Delete key")

    artifacts_parser = subparsers.add_parser("artifacts", help="Manage tool output files")
    artifacts_parser.add_argument("--session", help="Session ID")
    artifacts_parser.add_argument("--extract", action="store_true", help="Extract from logs")
    artifacts_parser.add_argument("--export", help="Export to directory")

    sessions_parser = subparsers.add_parser("sessions", help="List or view sessions")
    sessions_parser.add_argument("--limit", type=int, default=20, help="Limit count")
    sessions_parser.add_argument("--show", help="Show a single session")

    run_parser = subparsers.add_parser("run", help="Run evaluation cases")
    run_parser.add_argument("--cases", help="Case file (YAML/JSON/JSONL)")
    run_parser.add_argument("--quickstart", action="store_true", help="Use built-in quickstart cases")
    run_parser.add_argument("--tags", nargs="+", help="Filter by tags")
    run_parser.add_argument("--case", help="Single case message")
    run_parser.add_argument("--expect-tools", nargs="+", help="Expected tool names")
    run_parser.add_argument(
        "--expect-commands",
        nargs="+",
        help="Expected command keywords (exec.command substrings)",
    )
    run_parser.add_argument(
        "--expect-commands-ordered",
        nargs="+",
        help="Expected command keywords in order (exec.command substrings)",
    )
    run_parser.add_argument("--forbidden-tools", nargs="+", help="Forbidden tool names")
    run_parser.add_argument(
        "--forbidden-commands",
        nargs="+",
        help="Forbidden command keywords (exec.command substrings)",
    )
    run_parser.add_argument("--agent", default="main", help="Agent name")
    run_parser.add_argument(
        "--local", action="store_true", help="Run with --local mode"
    )
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Do not send messages"
    )
    run_parser.add_argument("--session", help="Session ID (dry-run)")
    run_parser.add_argument(
        "--show-trace", action="store_true", help="Show tool trace"
    )
    run_parser.add_argument(
        "--baseline", help="Baseline report file (JSON) for comparison"
    )
    run_parser.add_argument("--output-json", help="Write JSON report")
    run_parser.add_argument("--output-html", help="Write HTML report")
    run_parser.add_argument(
        "--summary-line", action="store_true", help="Print a single summary line"
    )

    gen_cases_parser = subparsers.add_parser("gen-cases", help="Generate case template")
    gen_cases_parser.add_argument("--output", help="Output file")
    gen_cases_parser.add_argument("--force", action="store_true", help="Overwrite file")

    edd_parser = subparsers.add_parser("edd", help="EDD loop commands")
    edd_subparsers = edd_parser.add_subparsers(
        dest="edd_cmd", required=True, help="EDD subcommands"
    )

    suggest_parser = edd_subparsers.add_parser(
        "suggest", help="Generate suggestions from failed cases"
    )
    suggest_parser.add_argument("--report", required=True, help="JSON report file")
    suggest_parser.add_argument("--workspace", default="", help="Workspace path")

    apply_parser = edd_subparsers.add_parser("apply", help="Apply suggestions")
    apply_parser.add_argument("--suggestion-file", required=True, help="Suggestion file")
    apply_parser.add_argument("--yes", action="store_true", help="Skip confirmation")
    apply_parser.add_argument("--workspace", default="", help="Workspace path")

    diff_parser = edd_subparsers.add_parser("diff", help="Compare two runs")
    diff_parser.add_argument("--before", required=True, help="Report before")
    diff_parser.add_argument("--after", required=True, help="Report after")
    diff_parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )

    mine_parser = edd_subparsers.add_parser(
        "mine", help="Mine golden cases from logs"
    )
    mine_parser.add_argument("--output", default="mined_cases.yaml", help="Output file")
    mine_parser.add_argument("--min-tools", type=int, default=1, help="Minimum tool calls")
    mine_parser.add_argument("--log-dir", help="Log directory")
    mine_parser.add_argument("--workspace", default="", help="Workspace path")

    judge_parser = edd_subparsers.add_parser(
        "judge", help="LLM-based evaluation of tool selection and output quality"
    )
    judge_parser.add_argument("--report", required=True, help="JSON report file")
    judge_parser.add_argument("--output", help="Output judged report (JSON)")
    judge_parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help=(
            "LLM model (claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5, "
            "gpt-4o, deepseek-chat)"
        ),
    )
    judge_parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic", "openai", "deepseek"],
        help="LLM provider",
    )

    export_parser = edd_subparsers.add_parser("export", help="Export golden dataset")
    export_parser.add_argument("--output", default="golden.jsonl", help="Output file")
    export_parser.add_argument("--min-tools", type=int, default=1, help="Minimum tool calls")
    export_parser.add_argument("--log-dir", help="Log directory")
    export_parser.add_argument("--workspace", default="", help="Workspace path")
    export_parser.add_argument("--merge-report", help="Merge report for final output")
    export_parser.add_argument(
        "--format", choices=["jsonl", "csv"], default="jsonl", help="Output format"
    )

    args = parser.parse_args()

    try:
        if args.cmd == "watch":
            watcher.cmd_watch(args)
        elif args.cmd == "trace":
            cmd_trace(args)
        elif args.cmd == "state":
            cmd_state(args)
        elif args.cmd == "artifacts":
            cmd_artifacts(args)
        elif args.cmd == "sessions":
            cmd_sessions(args)
        elif args.cmd == "run":
            eval_module.cmd_run(args)
        elif args.cmd == "gen-cases":
            eval_module.cmd_gen_cases(args)
        elif args.cmd == "edd":
            edd.cmd_edd(args)
    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user")
        sys.exit(130)
    except Exception as exc:  # pragma: no cover - top-level fallback
        if args.verbose:
            import traceback

            traceback.print_exc()
        else:
            print(f"✗ Error: {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Simplified command implementations (trace, state, artifacts, sessions)
# ---------------------------------------------------------------------------

def cmd_trace(args: argparse.Namespace) -> None:
    """Trace a session and print event details."""
    from pathlib import Path
    import json

    from .tracer import read_logs_for_session, extract_events

    log_dir = Path(args.log_dir)
    entries = read_logs_for_session(log_dir, args.session)
    events = extract_events(entries, args.session)

    if not events:
        print(f"✗ Session not found: {args.session}")
        sys.exit(1)

    if args.format == "json":
        output = [e.to_dict() for e in events]
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    print(f"Trace session={args.session} ({len(events)} events)")
    print("-" * 60)

    for i, event in enumerate(events, 1):
        if event.kind == "tool_start":
            print(f"#{i:02d} TOOL_START  {event.tool}  {event.ts}")
            if event.input:
                print(f"     input: {json.dumps(event.input, ensure_ascii=False)}")
        elif event.kind == "tool_end":
            duration_str = f"{event.duration_ms}ms" if event.duration_ms else ""
            print(f"#{i:02d} TOOL_END    {event.tool}  {duration_str}  {event.ts}")
            if event.output:
                output_str = event.output[:100] + "..." if len(event.output) > 100 else event.output
                print(f"     output: {output_str}")
        elif event.kind == "llm_response":
            output_str = event.output[:200] + "..." if len(event.output) > 200 else event.output
            print(f"#{i:02d} LLM_RESP    {event.ts}")
            print(f"     {output_str}")


def cmd_state(args: argparse.Namespace) -> None:
    """View or modify session state."""
    import json
    from pathlib import Path

    from .tracer import read_logs_for_session, extract_events
    from . import store

    log_dir = Path(args.log_dir)

    if args.set:
        for item in args.set:
            if "=" not in item:
                print(f"✗ Invalid --set value: {item}")
                sys.exit(1)
            key, value = item.split("=", 1)
            store.state_set(args.session, key, value)
        print("✓ State updated")

    if args.delete:
        state = store.state_load(args.session)
        for key in args.delete:
            if key in state:
                del state[key]
        store.state_save(args.session, state)
        print("✓ State updated")

    state = store.state_load(args.session)

    if args.format == "json":
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return

    print(f"State session={args.session}")
    print("-" * 60)
    print(json.dumps(state, indent=2, ensure_ascii=False))


def cmd_artifacts(args: argparse.Namespace) -> None:
    """Manage artifact files for a session."""
    import json
    from pathlib import Path

    from . import store

    if args.extract:
        from .tracer import read_logs_for_session, extract_events

        log_dir = Path(args.log_dir)
        entries = read_logs_for_session(log_dir, args.session)
        events = extract_events(entries, args.session)

        for event in events:
            if event.kind == "tool_end" and event.output:
                store.artifacts_save(args.session, event.tool, event.output)

        print("✓ Artifacts extracted")
        return

    artifacts = store.artifacts_list(args.session)
    if args.export:
        export_dir = Path(args.export)
        export_dir.mkdir(parents=True, exist_ok=True)
        for artifact in artifacts:
            target = export_dir / artifact.name
            target.write_text(artifact.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"✓ Exported {len(artifacts)} artifacts to {export_dir}")
        return

    print(json.dumps([str(p) for p in artifacts], indent=2, ensure_ascii=False))


def cmd_sessions(args: argparse.Namespace) -> None:
    """List or show sessions."""
    from .tracer import scan_sessions, read_logs_for_session, extract_events
    from pathlib import Path
    import json

    log_dir = Path(args.log_dir)

    if args.show:
        entries = read_logs_for_session(log_dir, args.show)
        events = extract_events(entries, args.show)
        if args.format == "json":
            print(json.dumps([e.to_dict() for e in events], indent=2, ensure_ascii=False))
        else:
            print(f"Session {args.show} ({len(events)} events)")
        return

    sessions = scan_sessions(log_dir)
    for s in sessions[: args.limit]:
        print(
            f"{s['session_id'][:8]}  tools={s['tool_count']}  turns={s['turns']}  last={s['last_ts']}  agent={s.get('agent', '')}"
        )
