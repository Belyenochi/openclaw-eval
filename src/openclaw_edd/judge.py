"""LLM-as-Judge for semantic evaluation.

Provides correctness, helpfulness, and faithfulness scoring
aligned with AWS AgentCore Evaluations' upper-layer metrics.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .models import EvalCase, Event


def build_judge_prompt(
    case: EvalCase,
    events: list[Event],
    final_output: str,
    criteria: list[str],
) -> str:
    """Build a judge prompt that covers AWS-aligned dimensions."""
    # Format trajectory
    trajectory_lines = []
    for e in events:
        if e.kind == "tool_end":
            cmd = (
                e.input.get("command", "")
                if isinstance(e.input, dict)
                else str(e.input)
            )
            status = getattr(e, "status", "completed")
            plan = f"  Plan: {e.plan_text}" if e.plan_text else ""
            trajectory_lines.append(
                f"  [{e.tool}] {cmd} → {status} ({e.duration_ms or '?'}ms){plan}"
            )
        elif e.kind == "llm_turn" and e.stop_reason == "stop":
            trajectory_lines.append(f"  [response] {e.text[:200]}...")

    trajectory_str = "\n".join(trajectory_lines) or "(no tool calls)"

    # Build criteria list
    criteria_str = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(criteria))

    return f"""You are an expert AI agent evaluator. Evaluate the following agent execution.

## Task
User request: {case.message}

## Agent Trajectory
{trajectory_str}

## Final Output
{final_output[:2000]}

## Evaluation Criteria
{criteria_str}

## Instructions
Score EACH criterion on a scale of 0.0 to 1.0.
Also provide an overall_pass (true/false) judgment and brief reasoning.

Respond ONLY with JSON (no markdown, no explanation outside JSON):
{{
  "scores": {{
    "criterion_1": <0.0-1.0>,
    "criterion_2": <0.0-1.0>,
    ...
  }},
  "overall_pass": true/false,
  "overall_score": <0.0-1.0>,
  "reasoning": "<one paragraph reasoning>"
}}"""


def call_judge(
    prompt: str,
    model: str,
    provider: str,
    api_key_env: str | None = None,
) -> dict[str, Any]:
    """Call LLM judge and parse response.

    Supports: anthropic, openai, deepseek, moonshot (kimi)

    Returns parsed JSON dict or {"error": "..."} on failure.
    """
    import os

    # Determine API key environment variable name
    env_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "moonshot": "MOONSHOT_API_KEY",
        "kimi": "MOONSHOT_API_KEY",
    }
    base_url_map = {
        "deepseek": "https://api.deepseek.com",
        "moonshot": "https://api.moonshot.cn/v1",
        "kimi": "https://api.moonshot.cn/v1",
    }

    env_var = api_key_env or env_map.get(provider, "OPENAI_API_KEY")
    api_key = os.environ.get(env_var)
    if not api_key:
        return {"error": f"Environment variable {env_var} not set"}

    try:
        if provider == "anthropic":
            from anthropic import Anthropic  # type: ignore[import-not-found]
            from anthropic.types import TextBlock  # type: ignore[import-not-found]

            client = Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            block = response.content[0]
            if isinstance(block, TextBlock):
                response_text = block.text
            else:
                response_text = str(block)
        else:
            from openai import OpenAI  # type: ignore[import-not-found]

            base_url = base_url_map.get(provider)
            client = (
                OpenAI(api_key=api_key, base_url=base_url)
                if base_url
                else OpenAI(api_key=api_key)
            )
            response = client.chat.completions.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.choices[0].message.content

        # Parse JSON
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        parsed: dict[str, Any] = (
            json.loads(json_match.group(0)) if json_match else json.loads(response_text)
        )
        return parsed

    except Exception as e:
        return {"error": str(e)}


def judge_case(
    case: EvalCase,
    events: list[Event],
    final_output: str,
) -> dict[str, Any]:
    """Run LLM judge for a single case. Returns judge result dict.

    Only runs if case.judge_criteria is non-empty AND judge_model is set.
    Returns empty dict if judge is not configured.
    """
    if not case.judge_criteria or not case.judge_model:
        return {}

    prompt = build_judge_prompt(case, events, final_output, case.judge_criteria)
    result = call_judge(
        prompt=prompt,
        model=case.judge_model,
        provider=case.judge_provider or "openai",
    )

    return {
        "passed": result.get("overall_pass", False),
        "overall_score": result.get("overall_score", 0),
        "scores": result.get("scores", {}),
        "reasoning": result.get("reasoning", ""),
        "model": case.judge_model,
        "provider": case.judge_provider,
        "error": result.get("error"),
    }
