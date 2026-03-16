# EDD Judge Command

`edd judge` uses an LLM to evaluate test results across multiple dimensions, scoring your agent's tool selection and output quality.

Supports Anthropic Claude, OpenAI GPT, and DeepSeek.

## Providers

### Anthropic (default)
- Models: `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5`
- Env var: `ANTHROPIC_API_KEY`
- Install: `pip install anthropic`

### OpenAI
- Models: `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`
- Env var: `OPENAI_API_KEY`
- Install: `pip install openai`

### DeepSeek
- Models: `deepseek-chat`, `deepseek-coder`
- Env var: `DEEPSEEK_API_KEY`
- Install: `pip install openai`

## Usage

```bash
# Anthropic Claude (default)
export ANTHROPIC_API_KEY=your_key
openclaw-edd edd judge --report report.json

# OpenAI GPT-4
export OPENAI_API_KEY=your_key
openclaw-edd edd judge --report report.json --provider openai --model gpt-4o

# DeepSeek
export DEEPSEEK_API_KEY=your_key
openclaw-edd edd judge --report report.json --provider deepseek --model deepseek-chat

# Write output to file
openclaw-edd edd judge --report report.json --output judged_report.json

# Use a specific Claude model
openclaw-edd edd judge --report report.json --model claude-opus-4-6
```

## Scoring Dimensions

1. **Tool selection** (0–10): Were the right tools chosen?
2. **Tool order** (0–10): Was the call sequence logical?
3. **Output quality** (0–10): Is the output accurate, complete, and useful?
4. **Overall** (0–10): Holistic assessment

## Output Format

```json
{
  "case": {...},
  "passed": true,
  "llm_judgment": {
    "tool_selection_score": 9,
    "tool_order_score": 8,
    "output_quality_score": 9,
    "overall_score": 9,
    "reasoning": "Tool selection appropriate, output accurate and complete",
    "model": "claude-sonnet-4-6",
    "provider": "anthropic"
  }
}
```

## Typical Workflow

```bash
# 1. Run evaluation
openclaw-edd run --cases cases.yaml --output-json report.json

# 2. LLM scoring
openclaw-edd edd judge --report report.json --output judged.json

# 3. View average score
cat judged.json | jq '.[] | .llm_judgment.overall_score' | awk '{sum+=$1; count++} END {print "Average:", sum/count}'
```
