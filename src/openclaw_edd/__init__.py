"""openclaw-edd: Evaluation-Driven Development toolkit for OpenClaw agents."""

from __future__ import annotations

from .models import EvalCase, EvalResult, Event

__all__ = ["Event", "EvalCase", "EvalResult", "__version__"]
__version__ = "0.2.3"
