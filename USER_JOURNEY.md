# openclaw-edd User Journey: 7-Step EDD Loop

This guide is for any OpenClaw user. It assumes **no domain-specific skills** and focuses on the real OpenClaw tool model.

## Step 0: Discover Tool Names (2 min)
OpenClaw uses low-level primitives (`exec`, `read`, `write`, `process`, `session_status`), **not** semantic tools like `get_weather`.
This is the #1 gotcha for new users.

```bash
openclaw-edd watch
```
Send a message in your chat app and observe the tool names in the log. Use those names in your test cases.

## Step 1: Install (30 sec)
```bash
pip install openclaw-edd
```

## Step 2: Run Quickstart Eval (3 min)
```bash
openclaw-edd run --quickstart --agent main --output-json round1.json --summary-line
```
Built-in cases:
- Greeting
- Web search
- File creation
- Directory listing
- Multi-step reasoning
- Safety refusal

## Step 3: Inspect Failures (2 min)
```bash
python3 -m json.tool round1.json
openclaw-edd edd suggest --report round1.json  # needs ANTHROPIC_API_KEY
```
Common failure reasons:
- "Missing required tool calls" → `expect_tools` wrong or agent used a different approach
- "Output missing expected keywords" → wording mismatch (adjust keywords)
- "Forbidden tool was called" → safety concern

## Step 4: Fix Agent and Re-run (5 min)
```bash
openclaw-edd run --quickstart --agent main --output-json round2.json --summary-line
```

## Step 5: Compare Rounds (30 sec)
```bash
openclaw-edd edd diff --before round1.json --after round2.json
```

## Step 6: Write Custom Cases
```json
{
  "cases": [
    {
      "id": "my_task",
      "message": "natural language task description",
      "eval_type": "regression",
      "expect_tools": ["exec"],
      "expect_commands": ["command keyword to match"],
      "forbidden_commands": ["dangerous command pattern"],
      "expect_output_contains": ["keyword in response"],
      "forbidden_tools": ["exec"],
      "timeout_s": 60,
      "tags": ["my_domain"]
    }
  ]
}
```

Assertion priority guide:
1. `expect_output_contains` — most reliable, validates final result
2. `expect_commands` — whitebox, confirms agent ran correct command (substring match on `exec` `input.command`)
3. `forbidden_commands` — safety guardrail
4. `expect_tools` — coarse check (`exec`/`read`/`write` level)
5. `forbidden_tools` — for pure-chat cases

## Step 7: CI Integration
```bash
openclaw-edd run --cases my_cases.json --agent main \
  --threshold 0.8 --regression-threshold 1.0 \
  --output-json ci.json --summary-line --quiet
# exit 0 = pass, exit 1 = fail, exit 2 = config error
```

```
watch → run → suggest → fix → run → diff → custom cases → CI
```
