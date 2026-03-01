"""Log parsing and event extraction utilities."""

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, DefaultDict, Generator, Optional, TypedDict, cast

from .models import Event

# ============================================================================
#
# ============================================================================

LOG_DIR = Path("/tmp/openclaw")
LOG_GLOB = "openclaw-*.log"

TOOL_START_MSGS = {"embedded run tool start", "tool_start", "run tool start"}
TOOL_END_MSGS = {"embedded run tool end", "tool_end", "run tool end"}
TURN_END_MSGS = {
    "run finished",
    "agent done",
    "run complete",
    "turn end",
    "response sent",
}


class SessionStats(TypedDict):
    """Aggregate stats for a session."""

    session_id: str
    first_ts: str
    last_ts: str
    tool_count: int
    turns: int
    agent: str

# （， JSON ）
TOOL_START_RE = re.compile(
    r'"msg"\s*:\s*"(?:embedded run tool start|tool_start|run tool start)"'
    r'|"event"\s*:\s*"agent\.run\.tool_start"'
)
TOOL_END_RE = re.compile(
    r'"msg"\s*:\s*"(?:embedded run tool end|tool_end|run tool end)"'
    r'|"event"\s*:\s*"agent\.run\.tool_end"'
)

# ANSI
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


# ============================================================================
#
# ============================================================================


def parse_line(line: str) -> Optional[dict[str, Any]]:
    """Parse a single JSON log line into a normalized dict."""
    line = ANSI_RE.sub("", line.strip())
    if not line:
        return None

    try:
        entry = json.loads(line)
        if not isinstance(entry, dict):
            return None

        if "_meta" not in entry:
            return cast(dict[str, Any], entry)

        msg_text = entry.get("1", "")
        if not msg_text:
            return None

        parsed: dict[str, Any] = {}

        #  sessionId
        if "sessionId=" in msg_text:
            import re

            match = re.search(r"sessionId=([a-f0-9\-]+)", msg_text)
            if match:
                parsed["session_id"] = match.group(1)

        #  runId（）
        if "runId=" in msg_text and "session_id" not in parsed:
            import re

            match = re.search(r"runId=([a-f0-9\-]+)", msg_text)
            if match:
                parsed["session_id"] = match.group(1)

        #  tool
        if "tool=" in msg_text:
            import re

            match = re.search(r"tool=(\w+)", msg_text)
            if match:
                parsed["tool"] = match.group(1)

        #  msg
        if "embedded run tool start" in msg_text:
            parsed["msg"] = "embedded run tool start"
        elif "embedded run tool end" in msg_text:
            parsed["msg"] = "embedded run tool end"
        elif "embedded run start" in msg_text:
            parsed["msg"] = "embedded run start"
        elif "embedded run done" in msg_text:
            parsed["msg"] = "embedded run done"
        elif "response sent" in msg_text:
            parsed["msg"] = "response sent"

        if "time" in entry:
            parsed["ts"] = entry["time"]
        elif "_meta" in entry and "date" in entry["_meta"]:
            parsed["ts"] = entry["_meta"]["date"]

        if "session_id" in parsed:
            return parsed

        return None

    except json.JSONDecodeError:
        return None


def read_all_logs(log_dir: Path = LOG_DIR, max_file_size_mb: int = 100) -> list[dict]:
    """
     openclaw-*.log，

    Args:
        log_dir:
        max_file_size_mb: （MB），

    Returns:
         dict
    """
    if not log_dir.exists():
        return []

    log_files = sorted(log_dir.glob(LOG_GLOB))
    entries = []
    max_bytes = max_file_size_mb * 1024 * 1024

    for log_file in log_files:
        try:
            file_size = log_file.stat().st_size
            if file_size > max_bytes:
                print(
                    f"⚠ : {log_file.name} ({file_size / 1024 / 1024:.1f}MB > {max_file_size_mb}MB)"
                )
                print(f"  :  --session  trace  session")
                continue

            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    entry = parse_line(line)
                    if entry:
                        entries.append(entry)
        except Exception as e:
            print(f"⚠ : {log_file} - {e}")

    return entries


def read_logs_for_session(log_dir: Path, session_id: str) -> list[dict]:
    """
     session （）

    Args:
        log_dir:
        session_id: Session ID

    Returns:
         session
    """
    if not log_dir.exists():
        return []

    log_files = sorted(log_dir.glob(LOG_GLOB))
    entries = []

    for log_file in log_files:
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    entry = parse_line(line)
                    if entry and entry.get("session_id", "").startswith(session_id):
                        entries.append(entry)
        except Exception as e:
            print(f"⚠ : {log_file} - {e}")

    return entries


def _is_tool_start(entry: dict) -> bool:
    """tool_start"""
    msg = entry.get("msg", "")
    event = entry.get("event", "")
    return msg in TOOL_START_MSGS or event == "agent.run.tool_start"


def _is_tool_end(entry: dict) -> bool:
    """tool_end"""
    msg = entry.get("msg", "")
    event = entry.get("event", "")
    return msg in TOOL_END_MSGS or event == "agent.run.tool_end"


def _is_turn_end(entry: dict) -> bool:
    """turn"""
    msg = entry.get("msg", "")
    return any(end_msg in msg for end_msg in TURN_END_MSGS)


def entry_to_event(entry: dict, raw_line: str = "") -> Optional[Event]:
    """
     dict  Event

    Args:
        entry:  dict
        raw_line: （）

    Returns:
        Event ， None
    """
    session_id = entry.get("session_id", "")
    ts = entry.get("ts", "")

    if _is_tool_start(entry):
        return Event(
            kind="tool_start",
            tool=entry.get("tool", ""),
            input=entry.get("input", {}),
            ts=ts,
            session_id=session_id,
            raw=entry,
        )

    elif _is_tool_end(entry):
        return Event(
            kind="tool_end",
            tool=entry.get("tool", ""),
            output=entry.get("output", ""),
            duration_ms=entry.get("duration"),
            ts=ts,
            session_id=session_id,
            raw=entry,
        )

    elif any(k in entry for k in ["response", "answer", "content"]):
        response_text = (
            entry.get("response") or entry.get("answer") or entry.get("content", "")
        )
        if response_text:
            return Event(
                kind="llm_response",
                output=str(response_text),
                ts=ts,
                session_id=session_id,
                raw=entry,
            )

    return None


def extract_events(entries: list[dict], session_id: str = "") -> list[Event]:
    """
    ， tool start/end

    Args:
        entries:
        session_id:  session （）

    Returns:
        Event
    """
    events = []
    pending = {}  # tool_name -> start_entry

    for entry in entries:
        sid = entry.get("session_id", "")

        #  session
        if session_id and not sid.startswith(session_id):
            continue

        if _is_tool_start(entry):
            tool = entry.get("tool", "")
            events.append(
                Event(
                    kind="tool_start",
                    tool=tool,
                    input=entry.get("input", {}),
                    ts=entry.get("ts", ""),
                    session_id=sid,
                    raw=entry,
                )
            )
            pending[tool] = entry

        elif _is_tool_end(entry):
            tool = entry.get("tool", "")
            start_entry = pending.pop(tool, {})
            events.append(
                Event(
                    kind="tool_end",
                    tool=tool,
                    input=start_entry.get("input", {}),
                    output=entry.get("output", ""),
                    duration_ms=entry.get("duration"),
                    ts=entry.get("ts", ""),
                    session_id=sid,
                    raw=entry,
                )
            )

        elif any(k in entry for k in ["response", "answer", "content"]):
            response_text = (
                entry.get("response") or entry.get("answer") or entry.get("content", "")
            )
            if response_text:
                events.append(
                    Event(
                        kind="llm_response",
                        output=str(response_text),
                        ts=entry.get("ts", ""),
                        session_id=sid,
                        raw=entry,
                    )
                )

    return events


def sessions_from_logs(log_dir: Path = LOG_DIR) -> list[SessionStats]:
    """Aggregate session stats from logs."""
    if not log_dir.exists():
        return []

    log_files = sorted(log_dir.glob(LOG_GLOB))
    sessions: DefaultDict[str, SessionStats] = defaultdict(
        lambda: {
            "session_id": "",
            "first_ts": "",
            "last_ts": "",
            "tool_count": 0,
            "turns": 0,
            "agent": "",
        }
    )

    for log_file in log_files:
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    entry = parse_line(line)
                    if not entry:
                        continue

                    session_id = entry.get("session_id", "")
                    if not session_id:
                        continue

                    session = sessions[session_id]
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

        except Exception as e:
            print(f"⚠ Failed to process log file: {log_file} - {e}")

    return sorted(sessions.values(), key=lambda x: x["last_ts"], reverse=True)


def tail_f(path: Path, from_end: bool = True) -> Generator[str, None, None]:
    """


    Args:
        path:
        from_end: （True ）

    Yields:

    """
    if not path.exists():
        #
        try:
            while not path.exists():
                time.sleep(0.5)
        except KeyboardInterrupt:
            return

    current_inode = os.stat(path).st_ino
    current_date = date.today()

    with open(path, "r", encoding="utf-8") as f:
        if from_end:
            f.seek(0, 2)  #

        try:
            while True:
                line = f.readline()
                if line:
                    yield line
                else:
                    #
                    time.sleep(0.05)

                    #
                    new_date = date.today()
                    if new_date != current_date:
                        #
                        new_path = (
                            path.parent
                            / f"openclaw-{new_date.strftime('%Y-%m-%d')}.log"
                        )
                        if new_path.exists():
                            path = new_path
                            current_date = new_date
                            current_inode = os.stat(path).st_ino
                            f.close()
                            f = open(path, "r", encoding="utf-8")
                            continue

                    #  inode
                    try:
                        new_inode = os.stat(path).st_ino
                        if new_inode != current_inode:
                            # ，
                            current_inode = new_inode
                            f.close()
                            f = open(path, "r", encoding="utf-8")
                    except FileNotFoundError:
                        # ，
                        time.sleep(0.5)
                        if path.exists():
                            current_inode = os.stat(path).st_ino
                            f.close()
                            f = open(path, "r", encoding="utf-8")
        except KeyboardInterrupt:
            return


def get_workspace(override: str = "") -> Path:
    """
    Workspace

    ：
    1. override （）
    2. ~/.openclaw/openclaw.json → agents.defaults.workspace
    3. fallback: ~/.openclaw/workspace

    Args:
        override:

    Returns:
        Workspace
    """
    if override:
        return Path(override).expanduser()

    #
    config_file = Path.home() / ".openclaw" / "openclaw.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                workspace = (
                    config.get("agents", {}).get("defaults", {}).get("workspace")
                )
                if workspace:
                    return Path(workspace).expanduser()
        except Exception:
            pass

    # Fallback
    return Path.home() / ".openclaw" / "workspace"
