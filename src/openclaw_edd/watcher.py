"""Real-time log watcher for OpenClaw sessions."""

from __future__ import annotations

import json
import os
import signal
import sys
from datetime import date
from pathlib import Path

from . import tracer, store, session_reader

# ============================================================================
#
# ============================================================================


def _cols() -> int:
    """， 100"""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 100


def _bar(duration_ms: int, max_ms: int, width: int = 16) -> str:
    """， max_ms"""
    if max_ms <= 0 or duration_ms <= 0:
        return "░" * width
    ratio = min(duration_ms / max_ms, 1.0)
    filled = round(ratio * width)
    return "█" * filled + "░" * (width - filled)


def _fmt_ms(ms: int) -> str:
    """"""
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    return f"{ms}ms"


def _truncate(text: str, maxlen: int) -> str:
    """"""
    text = str(text).strip()
    if len(text) > maxlen:
        return text[: maxlen - 3] + "..."
    return text


def _extract_args_summary(arguments: dict) -> str:
    """"""
    if not arguments:
        return ""
    #  command/query/path/message
    for key in ("command", "query", "path", "message", "text", "content"):
        if key in arguments:
            return str(arguments[key])
    #  JSON
    return json.dumps(arguments, ensure_ascii=False)


# ============================================================================
# Invocation
# ============================================================================


def _render_invocation(session_id: str, invocation: dict) -> None:
    """invocation（ +  + ）"""
    cols = _cols()

    user_text = invocation.get("user_text", "")
    start_ts = invocation.get("start_ts", "")
    events = invocation.get("events", [])  # list of dicts

    # （）
    total_ms = invocation.get("total_ms", 0)

    #  max_ms（）
    durations = [e["duration_ms"] for e in events if e.get("duration_ms", 0) > 0]
    max_ms = max(durations) if durations else 1

    # ──  ──────────────────────────────────────────────────────
    # ：HH:MM:SS（）
    time_str = ""
    if start_ts:
        try:
            from datetime import datetime, timezone

            dt = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
            dt_local = dt.astimezone()
            time_str = dt_local.strftime("%H:%M:%S")
        except Exception:
            time_str = start_ts[11:19]

    header_mid = f" session {session_id[:8]}  {time_str} "
    left_dashes = "─── "
    right_dashes = "─" * max(0, cols - len(left_dashes) - len(header_mid))
    print(f"{left_dashes}{header_mid}{right_dashes}")

    # invocation ： +
    user_display = _truncate(user_text, 60) if user_text else "(system)"
    total_str = _fmt_ms(total_ms) if total_ms > 0 else ""
    inv_line = f'invocation  "{user_display}"'
    if total_str:
        inv_line += f"  {total_str}"
    print(inv_line)
    print()

    # ──  ─────────────────────────────────────────────────
    print("  └─ invoke_agent  main")

    # （，）
    DUR_COL = 42

    for event in events:
        etype = event.get("type")
        tool = event.get("tool", "")
        duration_ms = event.get("duration_ms", 0)
        status = event.get("status", "")
        in_text = event.get("in_text", "")
        out_text = event.get("out_text", "")
        reply_text = event.get("reply_text", "")
        usage = event.get("usage", {})

        if etype == "tool":
            # call_llm （）
            print("       call_llm")

            # execute_tool
            tool_label = f"       └─ execute_tool  {tool}"
            if status == "running":
                # ⚠️ （2），
                pad = max(1, DUR_COL - len(tool_label))
                line = f"{tool_label}{' ' * pad}⚠️  async"
            else:
                dur_str = f"{duration_ms}ms"
                bar_str = _bar(duration_ms, max_ms)
                pad = max(1, DUR_COL - len(tool_label))
                line = f"{tool_label}{' ' * pad}{dur_str}  {bar_str}"
            print(line)

            if in_text:
                print(f"            in:  {_truncate(in_text, 60)}")
            if out_text and status != "running":
                # running  out  "Command still running..." ，
                print(f"            out: {_truncate(out_text, 80)}")
            print()

        elif etype == "llm_response":
            # call_llm ，（LLM ）
            left = "       call_llm"
            if duration_ms > 0:
                dur_str = f"{duration_ms}ms"
                bar_str = _bar(duration_ms, max_ms)
                pad = max(1, DUR_COL - len(left))
                line = f"{left}{' ' * pad}{dur_str}  {bar_str}"
            else:
                line = left
            print(line)

            if reply_text:
                #  3  200 （）
                lines = reply_text.split("\n")
                display_lines = []
                char_count = 0
                for i, line in enumerate(lines[:5]):  #  5
                    if char_count + len(line) > 200:
                        #  200 ， ...
                        remaining = 200 - char_count
                        if remaining > 10:
                            display_lines.append(line[:remaining] + "...")
                        break
                    display_lines.append(line)
                    char_count += len(line)
                    if i >= 2:  #  3
                        if i < len(lines) - 1:
                            display_lines.append("...")
                        break

                for idx, line in enumerate(display_lines):
                    if idx == 0:
                        print(f"            reply: {line}")
                    else:
                        print(f"                   {line}")
            if usage:
                tokens = f"in={usage.get('input', 0)} out={usage.get('output', 0)}"
                if usage.get("cacheRead"):
                    tokens += f" cache={usage.get('cacheRead', 0)}"
                print(f"            tokens: {tokens}")
            print()

    # ──  ───────────────────────────────────────────────────
    total_label = f" total {_fmt_ms(total_ms)} " if total_ms > 0 else " "
    suffix = "──────────"
    right_part = f"{total_label}{suffix}"
    left_dashes_end = "─" * max(0, cols - len(right_part))
    print(f"{left_dashes_end}{right_part}")
    print()


# ============================================================================
#
# ============================================================================


def _find_latest_log(log_dir: Path) -> Path:
    """，fallback"""
    logs = sorted(
        log_dir.glob("openclaw-*.log"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if logs:
        return logs[0]
    return log_dir / f"openclaw-{date.today().strftime('%Y-%m-%d')}.log"


# ============================================================================
# Session
# ============================================================================


def _watch_session_files(args, running):
    """
    session （）

    session ， input/output
    invocation ： invocation
    """
    from datetime import datetime

    sessions_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    if not sessions_dir.exists():
        print(f"✗ Session : {sessions_dir}")
        return

    print(f"👁   session : {sessions_dir}")
    if args.session:
        print(f"    session: {args.session}")

    #  ID，
    processed_messages = set()

    #  session （）
    file_positions = {}

    #  session  invocation
    # session_id -> {user_text, start_ts, start_wall_ms, events, pending_tool_call}
    invocation_buffers = {}

    try:
        import time

        while running[0]:
            #  session
            session_files = sorted(
                sessions_dir.glob("*.jsonl"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            for session_file in session_files[:10]:  #  10  session
                session_id = session_file.stem

                #  session
                if args.session and not session_id.startswith(args.session):
                    continue

                #
                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        # ：，
                        if not args.from_start:
                            if session_file in file_positions:
                                f.seek(file_positions[session_file])
                            else:
                                f.seek(0, 2)  # ：
                                file_positions[session_file] = f.tell()
                                continue

                        for line in f:
                            line = line.strip()
                            if not line:
                                continue

                            try:
                                message = json.loads(line)
                                message_id = message.get("id")

                                #
                                if message_id in processed_messages:
                                    continue
                                processed_messages.add(message_id)

                                _process_message(
                                    message, session_id, args, invocation_buffers
                                )

                            except json.JSONDecodeError:
                                continue

                        #
                        file_positions[session_file] = f.tell()

                except FileNotFoundError:
                    continue

            time.sleep(0.1)  #

    except KeyboardInterrupt:
        pass

    print("\n✓ Watch ")


def _process_message(
    message: dict, session_id: str, args, invocation_buffers: dict
) -> None:
    """， invocation ，"""
    import time

    msg = message.get("message", {})
    role = msg.get("role", "")
    ts = message.get("timestamp", "")

    buf = invocation_buffers.get(session_id)

    # ── ： invocation ──────────────────────────────────
    if role == "user":
        # （ [message_id: ...] ）
        user_text = ""
        for item in msg.get("content", []):
            if item.get("type") == "text":
                import re

                raw = item.get("text", "")
                #  [message_id: xxx]
                raw = re.sub(r"\[message_id:[^\]]*\]", "", raw).strip()
                #  System: [...] （OpenClaw ）
                raw = re.sub(r"^System:.*?\n\n", "", raw, flags=re.DOTALL).strip()
                #  [Sun 2026-03-01 02:41 GMT+8]
                raw = re.sub(r"^\[.*?GMT[+-]\d+\]\s*", "", raw).strip()
                user_text = raw.strip()
                break

        invocation_buffers[session_id] = {
            "user_text": user_text,
            "start_ts": ts,
            "start_wall_ms": int(time.time() * 1000),
            "events": [],
            "pending_tool_call": None,  # {tool, in_text, ts_start}
        }
        return

    if buf is None:
        #  invocation，
        return

    # ── assistant：tool_call  llm_response ─────────────────────────
    if role == "assistant":
        content = msg.get("content", [])

        for item in content:
            if item.get("type") == "toolCall":
                # ：
                tool_name = item.get("name", "")
                arguments = item.get("arguments", {})
                in_text = _extract_args_summary(arguments)
                buf["pending_tool_call"] = {
                    "tool": tool_name,
                    "tool_call_id": item.get("id", ""),
                    "in_text": in_text,
                    "ts_start": ts,
                }
                return  #  tool_result  emit

        for item in content:
            if item.get("type") == "text" and item.get("text"):
                # LLM  →  invocation
                reply_text = item.get("text", "").strip()
                usage = msg.get("usage", {})

                #  LLM （ start_ts ，）
                llm_dur = 0

                buf["events"].append(
                    {
                        "type": "llm_response",
                        "reply_text": reply_text,
                        "usage": usage,
                        "duration_ms": llm_dur,
                    }
                )

                #
                total_ms = 0
                if buf.get("start_ts"):
                    try:
                        from datetime import datetime, timezone

                        t0 = datetime.fromisoformat(
                            buf["start_ts"].replace("Z", "+00:00")
                        )
                        t1 = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        total_ms = int((t1 - t0).total_seconds() * 1000)
                    except Exception:
                        pass

                buf["total_ms"] = total_ms

                #
                _render_invocation(session_id, buf)
                del invocation_buffers[session_id]
                return

    # ── toolResult： pending_tool_call ───────────────────────────
    elif role == "toolResult":
        tool_name = msg.get("toolName", "")
        details = msg.get("details", {})
        status = details.get("status", "")
        duration_ms = details.get("durationMs") or 0

        #
        out_text = ""
        for item in msg.get("content", []):
            if item.get("type") == "text":
                out_text = item.get("text", "").strip()
                break

        pending = buf.get("pending_tool_call")

        if status == "running":
            # ： events， running
            in_text = pending.get("in_text", "") if pending else ""
            buf["events"].append(
                {
                    "type": "tool",
                    "tool": tool_name,
                    "in_text": in_text,
                    "out_text": out_text,  #  "Command still running ..."
                    "duration_ms": 0,
                    "status": "running",
                }
            )
            #  pending_tool_call， completed
            return

        elif status in ("completed", "error", "") or status is None:
            # （）
            in_text = pending.get("in_text", "") if pending else ""

            #  durationMs  0  ts_start，
            if duration_ms == 0 and pending and pending.get("ts_start"):
                try:
                    from datetime import datetime, timezone

                    t0 = datetime.fromisoformat(
                        pending["ts_start"].replace("Z", "+00:00")
                    )
                    t1 = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    duration_ms = int((t1 - t0).total_seconds() * 1000)
                except Exception:
                    pass

            buf["events"].append(
                {
                    "type": "tool",
                    "tool": tool_name,
                    "in_text": in_text,
                    "out_text": out_text,
                    "duration_ms": duration_ms,
                    "status": status or "completed",
                }
            )

            #  artifact（ --save-artifacts ）
            if getattr(args, "save_artifacts", False) and out_text:
                artifact_path = store.artifacts_save(session_id, tool_name, out_text)
                if artifact_path:
                    pass  #  invocation ，

            buf["pending_tool_call"] = None
            return


# ============================================================================
#
# ============================================================================


def cmd_watch(args):
    """Watch"""

    if args.daemon:
        # Daemon
        if sys.platform == "win32":
            print("✗ Daemon  Linux/macOS")
            sys.exit(1)

        pid = os.fork()
        if pid > 0:
            # ： PID
            with open(args.pid_file, "w") as f:
                f.write(str(pid))
            print(f"✓ Watch daemon  (PID: {pid})")
            print(f"  : {args.daemon_log}")
            print(f"  : kill $(cat {args.pid_file})")
            sys.exit(0)

        os.setsid()
        sys.stdout = open(args.daemon_log, "a", encoding="utf-8")
        sys.stderr = sys.stdout

    running = [True]

    def signal_handler(signum, frame):
        """Handle termination signals for the watcher."""
        running[0] = False

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Use session file mode with full input/output/duration.
    _watch_session_files(args, running)
