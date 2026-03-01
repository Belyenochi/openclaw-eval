# openclaw-edd

[![CI](https://github.com/Belyenochi/openclaw-edd/actions/workflows/ci.yml/badge.svg)](https://github.com/Belyenochi/openclaw-edd/actions)
[![PyPI version](https://badge.fury.io/py/openclaw-edd.svg)](https://pypi.org/project/openclaw-edd/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Evaluation-Driven Development toolkit for OpenClaw agents.
Zero-friction quality gates — log files as the single source of truth.

[中文文档](README_CN.md)


## Features

- ✅ **Zero Configuration** - `pip install openclaw-edd && openclaw-edd watch` and go
- ✅ **Zero Intrusion** - No need to modify OpenClaw config or restart Gateway
- ✅ **Zero Dependencies** - Core features work without any external libraries (PyYAML optional)
- ✅ **Complete Loop** - watch → run → suggest → apply → diff → mine → export

## Quick Start

```bash
pip install openclaw-edd

# Step 0: See what tools your agent actually uses
openclaw-edd watch

# Step 1: Run built-in evaluation (6 test cases)
openclaw-edd run --quickstart --agent main --summary-line

# Step 2: Full EDD loop
openclaw-edd run --quickstart --agent main --output-json round1.json
openclaw-edd edd suggest --report round1.json
# ... fix your agent ...
openclaw-edd run --quickstart --agent main --output-json round2.json
openclaw-edd edd diff --before round1.json --after round2.json
```

📖 **[Complete User Guide →](./USER_JOURNEY.md)** — 7-step walkthrough from install to CI integration.

中文版本：**[用户路径指南 →](./USER_JOURNEY_CN.md)**。

## Commands

### Core Commands

- **watch** - Real-time log monitoring, print tool event stream
- **trace** - Replay historical event chain
- **state** - View/modify session state
- **artifacts** - Manage tool output files
- **sessions** - List/view historical sessions
- **run** - Run evaluation test cases
- **gen-cases** - Generate test case templates

### EDD Loop Commands

- **`openclaw-edd edd suggest`** - Generate improvement suggestions from failed cases
- **`openclaw-edd edd apply`** - Apply suggestions to workspace
- **`openclaw-edd edd diff`** - Compare changes between two runs
- **`openclaw-edd edd mine`** - Mine golden cases from historical logs
- **`openclaw-edd edd judge`** - LLM-based scoring for tool selection and output quality
- **`openclaw-edd edd export`** - Export golden dataset (JSONL/CSV)


## Test Case Format

```yaml
cases:
  - id: mysql_slow_query
    message: "Any slow queries in MySQL recently"
    eval_type: regression          # "regression" (prevent regression) | "capability" (capability climb), default regression
    expect_tools:
      - exec
    expect_commands:
      - "check_health"
      - "prod-01"
    expect_commands_ordered:
      - "check_health"
      - "query_metrics"
    forbidden_commands:
      - "rm -rf"
    expect_tools_ordered:
      - exec
    expect_output_contains:
      - "slow query"
    forbidden_tools:
      - exec
    expect_tool_args:              # Tool argument assertions (White-box evaluation)
      exec:
        command: "check_health"    # Substring match for string values
    agent: openclaw_agent
    timeout_s: 30
    tags: [mysql, sre]
    description: "MySQL slow query troubleshooting basic verification"
```

Notes:
- `expect_commands`, `expect_commands_ordered`, and `forbidden_commands` do case-insensitive substring matching on `exec` tool `input.command`.
- `expect_output_contains` is case-insensitive substring matching.
- For `expect_tool_args`, string values use case-insensitive substring matching; non-strings use exact match.

### Eval Type Explanation

- **regression**: Prevent regression evaluation, starts near 100%, any drop is an alert signal
- **capability**: Capability climb evaluation, starts with low pass rate, tests what agent can't do yet

Run reports are grouped by eval_type:

```
📊 Regression Eval (Prevent Regression)
Passed: 8/10  (80%)  ← Below 100% needs attention
FAIL: mysql_slow_query, mysql_alert_check

📈 Capability Eval (Capability Climb)
Passed: 3/8  (37.5%)  ← Normal, this is a climb metric
PASS: mysql_basic_query ...
```

## Golden Dataset Format

```json
{
  "id": "50a359b5_1",
  "description": "Extracted from session 50a359b5, 2026-02-28",
  "source": "mined",
  "tags": ["mined"],
  "conversation": [
    {
      "turn": 1,
      "user": "Any slow queries in MySQL recently",
      "golden_tool_sequence": [
        {
          "name": "query_metrics",
          "args": {"metric": "p99_latency", "time_range": "1h"},
          "output_summary": "P99 latency 120ms, exceeds threshold"
        }
      ],
      "golden_output": "Detected MySQL slow query, P99 latency 120ms",
      "assert": [
        {"type": "tool_called", "value": "query_metrics"},
        {"type": "tool_args", "tool": "query_metrics", "args": {"metric": "p99_latency", "time_range": "1h"}},
        {"type": "contains", "value": "slow query"}
      ]
    }
  ],
  "metadata": {
    "session_id": "50a359b5-184f-4c73-913d-3b53ebbdf109",
    "agent": "openclaw_agent",
    "extracted_at": "2026-02-28T16:00:00",
    "skill_triggered": "skills/mysql_sre.md"
  }
}
```

## Data Sources

- **Log Location**: `/tmp/openclaw/openclaw-YYYY-MM-DD.log`
- **Format**: JSON Lines
- **State**: `~/.openclaw_eval/state/<session_id>.json`
- **Artifacts**: `~/.openclaw_eval/artifacts/<session_id>/`

## Workspace Path Resolution

Priority:
1. `--workspace` parameter
2. `~/.openclaw/openclaw.json` → `agents.defaults.workspace`
3. Fallback: `~/.openclaw/workspace`

## Dependencies

- **Zero mandatory dependencies** - Core features work without any external libraries
- **Optional dependencies**:
  - PyYAML (only needed when using `--cases`)
  - anthropic (only needed when using `edd judge`)

```bash
pip install openclaw-edd[yaml]  # Install with YAML support
pip install openclaw-edd         # Includes anthropic SDK
```

## Platform Support

- **Linux/macOS** - Full support (including daemon mode)
- **Windows** - All features supported except daemon mode

## CI Integration

```bash
# Run evaluation
openclaw-edd run --cases cases.yaml --output-json report.json

# Check exit code
if [ $? -ne 0 ]; then
  echo "Evaluation failed"
  exit 1
fi
```

## License

MIT
