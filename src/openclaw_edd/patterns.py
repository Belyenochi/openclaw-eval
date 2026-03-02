"""Action pattern classification for exec commands.

Maps raw exec command strings to semantic action categories,
bridging the gap between OpenClaw's low-level exec primitive
and AWS-style tool_selection_accuracy evaluation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# 内置 SRE + 通用 pattern
BUILTIN_PATTERNS: dict[str, list[str]] = {
    # 系统诊断
    "health_check": [
        r"check_health",
        r"health\.sh",
        r"ping\s+",
        r"/health",
        r"systemctl\s+status",
        r"service\s+\S+\s+status",
    ],
    "metric_query": [
        r"curl.*metrics",
        r"prometheus.*query",
        r"query\?query=",
        r"open-meteo\.com",
        r"wttr\.in",
        r"api\..*weather",
    ],
    "log_analysis": [
        r"analyze.*log",
        r"grep.*error",
        r"tail.*log",
        r"journalctl",
        r"dmesg",
    ],
    "database_operation": [
        r"mysql\s+-",
        r"psql\s+-",
        r"mongo\s+",
        r"ceresdb-cli",
        r"redis-cli",
        r"mysqladmin",
    ],
    # 文件操作
    "list_files": [
        r"\bls\b",
        r"\bfind\b",
        r"\btree\b",
        r"\bdir\b",
        r"os\.listdir",
        r"glob\.",
        r"pathlib.*iterdir",
    ],
    "count_items": [
        r"\bwc\b",
        r"\bcount\b",
        r"\blen\(",
        r"统计",
        r"\.count\(",
        r"num_files",
        r"total.*files",
    ],
    "file_read": [
        r"\bcat\b",
        r"\bhead\b",
        r"\btail\b",
        r"\bless\b",
        r"open\(.*['\"]r",
        r"read_file",
    ],
    "file_write": [
        r"\btee\b",
        r">>\s",
        r"\bsed\b.*-i",
        r"write_file",
        r"open\(.*['\"]w",
    ],
    # 网络
    "http_request": [
        r"\bcurl\b",
        r"\bwget\b",
        r"requests\.(get|post)",
        r"http\.client",
        r"urllib",
    ],
    "weather_query": [
        r"wttr\.in",
        r"open-meteo\.com",
        r"weather",
        r"api\..*forecast",
    ],
    # 进程管理
    "process_management": [
        r"\bkill\b",
        r"\bpkill\b",
        r"\bps\b.*aux",
        r"systemctl\s+(start|stop|restart)",
    ],
}


class ActionClassifier:
    """Classify exec commands into semantic actions."""

    def __init__(
        self,
        builtin: bool = True,
        custom_patterns: dict[str, list[str]] | None = None,
        custom_file: str | None = None,
    ):
        self.patterns: dict[str, list[str]] = {}
        if builtin:
            self.patterns.update(BUILTIN_PATTERNS)
        if custom_patterns:
            self.patterns.update(custom_patterns)
        if custom_file:
            self.patterns.update(self._load_custom_file(custom_file))
        # 预编译正则
        self._compiled: dict[str, list[re.Pattern[str]]] = {
            action: [re.compile(r, re.IGNORECASE) for r in regexes]
            for action, regexes in self.patterns.items()
        }

    def classify(self, command: str) -> list[str]:
        """Classify a command string into semantic actions.

        Returns list of matched action names, or ["unknown"] if none match.
        """
        actions = []
        for action_name, compiled_regexes in self._compiled.items():
            if any(rx.search(command) for rx in compiled_regexes):
                actions.append(action_name)
        return actions or ["unknown"]

    def classify_events(self, events: list[Any]) -> list[dict[str, Any]]:
        """Classify all exec events in a list, return enriched dicts."""
        results = []
        for e in events:
            if getattr(e, "kind", "") != "tool_end":
                continue
            tool = getattr(e, "tool", "")
            inp = getattr(e, "input", {})
            command = inp.get("command", "") if isinstance(inp, dict) else ""
            actions = self.classify(command) if tool == "exec" and command else []
            results.append(
                {
                    "tool": tool,
                    "command": command,
                    "actions": actions,
                }
            )
        return results

    @staticmethod
    def _load_custom_file(path: str) -> dict[str, list[str]]:
        """Load custom patterns from YAML/JSON file."""
        p = Path(path)
        if not p.exists():
            return {}
        text = p.read_text(encoding="utf-8")
        if p.suffix in (".yaml", ".yml"):
            try:
                import yaml  # type: ignore[import-untyped]

                yaml_result: dict[str, list[str]] = yaml.safe_load(text) or {}  # type: ignore[assignment]
                return yaml_result
            except ImportError:
                return {}
        else:
            import json

            json_result: dict[str, list[str]] = json.loads(text)
            return json_result
