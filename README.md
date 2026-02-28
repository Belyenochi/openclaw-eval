# openclaw-edd

**Evaluation-Driven Development toolkit for OpenClaw agents**

[中文文档](README_CN.md)

Zero-friction EDD toolkit that doesn't intrude into OpenClaw core, with log files as the single source of truth.

## Features

- ✅ **Zero Configuration** - `pip install openclaw-edd && openclaw-edd watch` and go
- ✅ **Zero Intrusion** - No need to modify OpenClaw config or restart Gateway
- ✅ **Zero Dependencies** - Core features work without any external libraries (PyYAML optional)
- ✅ **Complete Loop** - watch → run → suggest → apply → diff → mine → export

## Quick Start

```bash
# Install
pip install openclaw-edd

# Real-time monitoring
openclaw-edd watch

# Standard EDD loop
openclaw-edd run --cases cases.yaml --output-json report_v1.json
openclaw-edd edd suggest --report report_v1.json > suggestion.txt
openclaw-edd edd apply --suggestion-file suggestion.txt
openclaw-edd run --cases cases.yaml --output-json report_v2.json
openclaw-edd edd diff --before report_v1.json --after report_v2.json

# Mine golden cases from production logs
openclaw-edd edd mine --output mined_cases.yaml
openclaw-edd run --cases mined_cases.yaml --output-json regression.json

# Export golden dataset
openclaw-edd edd export --output golden.jsonl
openclaw-edd edd export --format csv --output review.csv
```

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

- **edd suggest** - Generate improvement suggestions from failed cases
- **edd apply** - Apply suggestions to workspace
- **edd diff** - Compare changes between two runs
- **edd mine** - Mine golden cases from historical logs
- **edd judge** - LLM-based scoring for tool selection and output quality
- **edd export** - Export golden dataset (JSONL/CSV)

## Detailed Usage

### watch - Real-time Monitoring

```bash
# Basic usage
openclaw-edd watch

# Filter specific session
openclaw-edd watch --session <session_id_prefix>

# Read from file start (replay today's history)
openclaw-edd watch --from-start

# Run in background
openclaw-edd watch --daemon
kill $(cat /tmp/openclaw_edd_watch.pid)
```

### run - Run Evaluation

```bash
# Use built-in test cases
openclaw-edd run

# Use custom test cases
openclaw-edd run --cases cases.yaml

# Filter by tags
openclaw-edd run --cases cases.yaml --tags smoke,mysql

# Single test case (command line)
openclaw-edd run --case "What's the weather in Shanghai today" --expect-tools get_weather

# Show detailed tool call trace
openclaw-edd run --cases cases.yaml --show-trace

# Use --local mode (ensure logs written locally)
openclaw-edd run --cases cases.yaml --agent main --local

# Output reports
openclaw-edd run --output-json report.json
openclaw-edd run --output-html report.html

# Dry run (no messages sent, only parse logs)
openclaw-edd run --dry-run
```

### edd suggest - Generate Suggestions

```bash
openclaw-edd edd suggest --report report.json
openclaw-edd edd suggest --report report.json --workspace ~/.openclaw/workspace
openclaw-edd edd suggest --report report.json > suggestion.txt
```

### edd diff - Compare Changes

```bash
openclaw-edd edd diff --before report_v1.json --after report_v2.json
openclaw-edd edd diff --before report_v1.json --after report_v2.json --format json
```

### edd mine - Mine Test Cases

```bash
openclaw-edd edd mine
openclaw-edd edd mine --output mined_cases.yaml
openclaw-edd edd mine --min-tools 2
```

### edd judge - LLM Evaluation

```bash
# Use LLM for intelligent evaluation of test results
export ANTHROPIC_API_KEY=your_key
openclaw-edd edd judge --report report.json
openclaw-edd edd judge --report report.json --output judged_report.json
openclaw-edd edd judge --report report.json --model claude-opus-4-6

# View detailed documentation
cat docs/JUDGE_COMMAND.md
```

### edd export - Export Dataset

```bash
# Export JSONL
openclaw-edd edd export --output golden.jsonl

# Merge with run report for more accurate golden_output
openclaw-edd run --cases cases.yaml --output-json report.json
openclaw-edd edd export --merge-report report.json --output golden.jsonl

# Export CSV for expert review
openclaw-edd edd export --format csv --output review.csv
```

## Test Case Format

```yaml
cases:
  - id: mysql_slow_query
    message: "Any slow queries in MySQL recently"
    eval_type: regression          # "regression" (prevent regression) | "capability" (capability climb), default regression
    expect_tools:
      - query_metrics
      - get_alerts
    expect_tools_ordered:
      - query_metrics
      - get_alerts
    expect_output_contains:
      - "slow query"
    forbidden_tools:
      - execute_sql
    expect_tool_args:              # Tool argument assertions (White-box evaluation)
      query_metrics:
        time_range: "1h"           # Exact match: actual call must contain this parameter with equal value
        metric: "p99_latency"      # Unspecified parameters are not checked
    agent: openclaw_agent
    timeout_s: 30
    tags: [mysql, sre]
    description: "MySQL slow query troubleshooting basic verification"
```

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
