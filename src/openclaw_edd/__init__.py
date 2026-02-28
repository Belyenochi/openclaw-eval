"""
openclaw-edd: Evaluation-Driven Development toolkit for OpenClaw agents

零摩擦 EDD 工具包，不侵入 OpenClaw 本体，唯一数据源是日志文件。
"""

__version__ = "0.1.0"

from .models import Event, EvalCase, EvalResult

__all__ = ["Event", "EvalCase", "EvalResult", "__version__"]
