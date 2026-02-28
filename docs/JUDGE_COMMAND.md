# EDD Judge Command - LLM 评估功能

## 概述

`edd judge` 命令使用 LLM 对测试结果进行智能评估，从多个维度对 AI Agent 的表现打分。

支持多个 LLM 提供商：Anthropic Claude、OpenAI GPT、DeepSeek。

## 支持的 LLM 提供商

### Anthropic (默认)
- 模型: `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5`
- 环境变量: `ANTHROPIC_API_KEY`
- 安装: `pip install anthropic`

### OpenAI
- 模型: `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`
- 环境变量: `OPENAI_API_KEY`
- 安装: `pip install openai`

### DeepSeek
- 模型: `deepseek-chat`, `deepseek-coder`
- 环境变量: `DEEPSEEK_API_KEY`
- 安装: `pip install openai`

## 使用方法

```bash
# 使用 Anthropic Claude (默认)
export ANTHROPIC_API_KEY=your_key
edd edd judge --report report.json

# 使用 OpenAI GPT-4
export OPENAI_API_KEY=your_key
edd edd judge --report report.json --provider openai --model gpt-4o

# 使用 DeepSeek
export DEEPSEEK_API_KEY=your_key
edd edd judge --report report.json --provider deepseek --model deepseek-chat

# 指定输出文件
edd edd judge --report report.json --output judged_report.json

# 使用不同的 Claude 模型
edd edd judge --report report.json --model claude-opus-4-6
```

## 评估维度

1. **工具选择合理性** (0-10分): 选择的工具是否合适、必要
2. **工具调用顺序** (0-10分): 工具调用的顺序是否合理
3. **输出质量** (0-10分): 输出是否准确、完整、有用
4. **整体表现** (0-10分): 综合评价

## 输出格式

```json
{
  "case": {...},
  "passed": true,
  "llm_judgment": {
    "tool_selection_score": 9,
    "tool_order_score": 8,
    "output_quality_score": 9,
    "overall_score": 9,
    "reasoning": "工具选择合理，输出准确完整",
    "model": "claude-sonnet-4-6",
    "provider": "anthropic"
  }
}
```

## 典型工作流

```bash
# 1. 运行评测
edd run --cases cases.yaml --output-json report.json

# 2. LLM 评估
edd edd judge --report report.json --output judged.json

# 3. 查看统计
cat judged.json | jq '.[] | .llm_judgment.overall_score' | awk '{sum+=$1; count++} END {print "平均分:", sum/count}'
```
