"""Data models for evaluation events and results."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field


@dataclass
class Event:
    """A single event emitted by tools or the LLM."""

    kind: str  # "tool_start" | "tool_end" | "llm_response"
    tool: str = ""
    input: dict = field(default_factory=dict)
    output: str = ""
    duration_ms: int | None = None
    ts: str = ""
    session_id: str = ""
    raw: dict = field(default_factory=dict)
    plan_text: str = ""
    model: str = ""
    usage: dict = field(default_factory=dict)
    status: str = ""  # "completed" | "running" | ""
    exit_code: int | None = None  # process exit code

    def to_dict(self) -> dict:
        """Convert to dict and drop empty values."""
        return {k: v for k, v in self.__dict__.items() if v not in (None, {}, "")}


@dataclass
class EvalCase:
    """Single evaluation case definition."""

    id: str
    message: str
    expect_tools: list[str] = field(default_factory=list)
    expect_tools_ordered: list[str] = field(default_factory=list)
    expect_tools_ordered_strict: bool = False
    expect_commands: list[str] = field(default_factory=list)
    expect_commands_ordered: list[str] = field(default_factory=list)
    forbidden_commands: list[str] = field(default_factory=list)
    expect_output_contains: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    expect_tool_args: dict[str, dict] = field(default_factory=dict)
    eval_type: str = "regression"  # "regression" | "capability"
    agent: str = "main"
    timeout_s: int = 30
    tags: list[str] = field(default_factory=list)
    description: str = ""
    max_retries: int | None = None  # Max allowed consecutive identical tool calls


@dataclass
class EvalResult:
    """Evaluation result for a case."""

    case: EvalCase
    passed: bool
    events: list[Event]
    final_output: str
    duration_s: float
    failures: list[str] = field(default_factory=list)
    checks: dict = field(default_factory=dict)
    session_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    model: str = ""
    provider: str = ""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0

    @property
    def tool_names(self) -> list[str]:
        """Return tool names from tool_end events."""
        return [e.tool for e in self.events if e.kind == "tool_end"]
