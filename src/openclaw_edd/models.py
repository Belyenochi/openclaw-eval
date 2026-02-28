"""
数据模型定义

包含所有 dataclass：Event, EvalCase, EvalResult
"""

from dataclasses import dataclass, field
from typing import Optional
import datetime


@dataclass
class Event:
    """单个事件（tool 调用或 LLM 响应）"""
    kind: str  # "tool_start" | "tool_end" | "llm_response"
    tool: str = ""
    input: dict = field(default_factory=dict)
    output: str = ""
    duration_ms: Optional[int] = None
    ts: str = ""
    session_id: str = ""
    raw: dict = field(default_factory=dict)  # 原始日志行，调试用

    def to_dict(self) -> dict:
        """转为 dict，过滤空值"""
        return {k: v for k, v in self.__dict__.items() if v not in (None, {}, "")}


@dataclass
class EvalCase:
    """单个评测用例"""
    id: str
    message: str
    expect_tools: list[str] = field(default_factory=list)
    expect_tools_ordered: list[str] = field(default_factory=list)
    expect_tools_ordered_strict: bool = False  # False=IN_ORDER（允许中间有其他工具），True=EXACT（必须完全一致）
    expect_output_contains: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    expect_tool_args: dict[str, dict] = field(default_factory=dict)  # {tool_name: {arg_key: expected_value}}
    eval_type: str = "regression"  # "regression" | "capability"
    agent: str = "openclaw_agent"
    timeout_s: int = 30
    tags: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class EvalResult:
    """评测结果"""
    case: EvalCase
    passed: bool
    events: list[Event]
    final_output: str
    duration_s: float
    failures: list[str] = field(default_factory=list)
    session_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    @property
    def tool_names(self) -> list[str]:
        """提取所有 tool_end 的工具名"""
        return [e.tool for e in self.events if e.kind == "tool_end"]
