"""State and artifact persistence utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVAL_HOME = Path.home() / ".openclaw_eval"
STATE_DIR = EVAL_HOME / "state"
ARTIFACTS_DIR = EVAL_HOME / "artifacts"

STATE_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def state_load(session_id: str) -> dict:
    """Load a session state file.

    Args:
        session_id: Session ID.

    Returns:
        State dict. Returns an empty dict if missing or invalid.
    """
    state_file = STATE_DIR / f"{session_id}.json"
    if not state_file.exists():
        return {}
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def state_save(session_id: str, data: dict) -> None:
    """Save session state atomically.

    Args:
        session_id: Session ID.
        data: State data.
    """
    state_file = STATE_DIR / f"{session_id}.json"
    tmp_file = state_file.with_suffix(".tmp")

    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    tmp_file.rename(state_file)


def state_set(session_id: str, key: str, value: Any) -> None:
    """Set a key in state, supporting dotted paths.

    Args:
        session_id: Session ID.
        key: Key path (supports a.b.c format).
        value: Value to set.
    """
    state = state_load(session_id)

    parts = key.split(".")
    current = state
    for part in parts[:-1]:
        current = current.setdefault(part, {})

    try:
        current[parts[-1]] = json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError):
        current[parts[-1]] = value

    state_save(session_id, state)


def artifacts_save(
    session_id: str, tool_name: str, content: str, version: int | None = None
) -> Path:
    """Save tool output as an artifact file.

    Args:
        session_id: Session ID.
        tool_name: Tool name.
        content: Output content.
        version: Optional version number. Auto-increments if None.

    Returns:
        The saved file path.
    """
    session_dir = ARTIFACTS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    if version is None:
        existing = list(session_dir.glob(f"{tool_name}_v*.txt"))
        version = len(existing)

    artifact_file = session_dir / f"{tool_name}_v{version}.txt"
    with open(artifact_file, "w", encoding="utf-8") as f:
        f.write(content)

    return artifact_file


def artifacts_list(session_id: str | None = None) -> list[Path]:
    """List artifact files.

    Args:
        session_id: Session ID. If None, list all artifacts.

    Returns:
        List of artifact paths.
    """
    if session_id:
        session_dir = ARTIFACTS_DIR / session_id
        if not session_dir.exists():
            return []
        return sorted(session_dir.glob("*.txt"))
    return sorted(ARTIFACTS_DIR.glob("*/*.txt"))
