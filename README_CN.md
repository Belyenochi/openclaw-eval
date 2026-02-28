# openclaw-edd

**Evaluation-Driven Development toolkit for OpenClaw agents**


[English Documentation](README.md)
零摩擦 EDD 工具包，不侵入 OpenClaw 本体，唯一数据源是日志文件。

## 特性

- ✅ **零配置** - `pip install openclaw-edd && edd watch` 即用
- ✅ **零侵入** - 不需要改 OpenClaw 配置，不需要重启 Gateway
- ✅ **零依赖** - 核心功能无需任何外部库（PyYAML 可选）
- ✅ **完整闭环** - watch → run → suggest → apply → diff → mine → export

## 快速开始

```bash
# 安装
pip install openclaw-edd

# 实时观测
openclaw-edd watch

# 标准 EDD 闭环
openclaw-edd run --cases cases.yaml --output-json report_v1.json
openclaw-edd edd suggest --report report_v1.json > suggestion.txt
openclaw-edd edd apply --suggestion-file suggestion.txt
openclaw-edd run --cases cases.yaml --output-json report_v2.json
openclaw-edd edd diff --before report_v1.json --after report_v2.json

# 从生产日志挖掘 golden cases
openclaw-edd edd mine --output mined_cases.yaml
openclaw-edd run --cases mined_cases.yaml --output-json regression.json

# 导出 golden dataset
openclaw-edd edd export --output golden.jsonl
openclaw-edd edd export --format csv --output review.csv
```

## 命令列表

### 核心命令

- **watch** - 实时监听日志，打印 tool 事件流
- **trace** - 回放历史事件链
- **state** - 查看/修改 session 状态
- **artifacts** - 管理 tool 输出文件
- **sessions** - 列出/查看历史 session
- **run** - 运行评测用例集
- **gen-cases** - 生成用例模板

### EDD 闭环命令

- **edd suggest** - 从失败 cases 生成修改建议
- **edd apply** - 应用建议到 workspace
- **edd diff** - 对比两次 run 的变化
- **edd mine** - 从历史日志挖掘 golden cases
- **edd judge** - 用 LLM 对 tool 选择和 output 质量打分
- **edd export** - 导出 golden dataset（JSONL/CSV）

## 详细用法

### watch - 实时监听

```bash
# 基本用法
openclaw-edd watch

# 过滤特定 session
openclaw-edd watch --session <session_id前缀>

# 从文件头读（回放今天历史）
openclaw-edd watch --from-start

# 后台运行
openclaw-edd watch --daemon
kill $(cat /tmp/openclaw_edd_watch.pid)
```

### run - 运行评测

```bash
# 使用内置用例
openclaw-edd run

# 使用自定义用例
openclaw-edd run --cases cases.yaml

# 过滤 tags
openclaw-edd run --cases cases.yaml --tags smoke,mysql

# 单个用例（命令行指定）
openclaw-edd run --case "今天上海天气" --expect-tools get_weather

# 显示详细的工具调用 trace
openclaw-edd run --cases cases.yaml --show-trace

# 使用 --local 模式（确保日志写入本地）
openclaw-edd run --cases cases.yaml --agent main --local

# 输出报告
openclaw-edd run --output-json report.json
openclaw-edd run --output-html report.html

# Dry run（不发消息，只解析日志）
openclaw-edd run --dry-run
```

### edd suggest - 生成建议

```bash
openclaw-edd edd suggest --report report.json
openclaw-edd edd suggest --report report.json --workspace ~/.openclaw/workspace
openclaw-edd edd suggest --report report.json > suggestion.txt
```

### edd diff - 对比变化

```bash
openclaw-edd edd diff --before report_v1.json --after report_v2.json
openclaw-edd edd diff --before report_v1.json --after report_v2.json --format json
```

### edd mine - 挖掘用例

```bash
openclaw-edd edd mine
openclaw-edd edd mine --output mined_cases.yaml
openclaw-edd edd mine --min-tools 2
```

### edd judge - LLM 评估

```bash
# 使用 LLM 对测试结果进行智能评估
export ANTHROPIC_API_KEY=your_key
openclaw-edd edd judge --report report.json
openclaw-edd edd judge --report report.json --output judged_report.json
openclaw-edd edd judge --report report.json --model claude-opus-4-6

# 查看详细文档
cat docs/JUDGE_COMMAND.md
```

### edd export - 导出 dataset

```bash
# 导出 JSONL
openclaw-edd edd export --output golden.jsonl

# 结合 run report 补充更准确的 golden_output
openclaw-edd run --cases cases.yaml --output-json report.json
openclaw-edd edd export --merge-report report.json --output golden.jsonl

# 导出 CSV 给专家人工审查
openclaw-edd edd export --format csv --output review.csv
```

## 用例格式

```yaml
cases:
  - id: mysql_slow_query
    message: "MySQL 最近有慢查询吗"
    eval_type: regression          # "regression" (防退步) | "capability" (能力爬坡)，默认 regression
    expect_tools:
      - query_metrics
      - get_alerts
    expect_tools_ordered:
      - query_metrics
      - get_alerts
    expect_output_contains:
      - "慢查询"
    forbidden_tools:
      - execute_sql
    expect_tool_args:              # 工具参数断言（White-box 评测）
      query_metrics:
        time_range: "1h"           # 精确匹配：实际调用必须包含此参数且值相等
        metric: "p99_latency"      # 未指定的参数不检查
    agent: openclaw_agent
    timeout_s: 30
    tags: [mysql, sre]
    description: "MySQL 慢查询排查基础验证"
```

### Eval Type 说明

- **regression**: 防退步评测，从接近 100% 开始，任何下降都是报警信号
- **capability**: 能力爬坡评测，从低通过率开始，用来测试 agent 还不会做的事

运行报告会按 eval_type 分组显示：

```
📊 Regression Eval（防退步）
通过: 8/10  (80%)  ← 低于 100% 需要关注
FAIL: mysql_slow_query, mysql_alert_check

📈 Capability Eval（能力爬坡）
通过: 3/8  (37.5%)  ← 正常，这是爬坡指标
PASS: mysql_basic_query ...
```

## Golden Dataset 格式

```json
{
  "id": "50a359b5_1",
  "description": "从 session 50a359b5 提取，2026-02-28",
  "source": "mined",
  "tags": ["mined"],
  "conversation": [
    {
      "turn": 1,
      "user": "MySQL 最近有慢查询吗",
      "golden_tool_sequence": [
        {
          "name": "query_metrics",
          "args": {"metric": "p99_latency", "time_range": "1h"},
          "output_summary": "P99 延迟 120ms，超过阈值"
        }
      ],
      "golden_output": "检测到 MySQL 慢查询，P99 延迟 120ms",
      "assert": [
        {"type": "tool_called", "value": "query_metrics"},
        {"type": "tool_args", "tool": "query_metrics", "args": {"metric": "p99_latency", "time_range": "1h"}},
        {"type": "contains", "value": "慢查询"}
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

## 数据源

- **日志位置**: `/tmp/openclaw/openclaw-YYYY-MM-DD.log`
- **格式**: JSON Lines
- **State**: `~/.openclaw_eval/state/<session_id>.json`
- **Artifacts**: `~/.openclaw_eval/artifacts/<session_id>/`

## Workspace 路径解析

优先级：
1. `--workspace` 参数
2. `~/.openclaw/openclaw.json` → `agents.defaults.workspace`
3. Fallback: `~/.openclaw/workspace`

## 依赖说明

- **零强制依赖** - 核心功能无需任何外部库
- **可选依赖**:
  - PyYAML（仅在使用 `--cases` 时需要）
  - anthropic（仅在使用 `openclaw-edd judge` 时需要）

```bash
pip install openclaw-edd[yaml]  # 安装 YAML 支持
pip install openclaw-edd         # 包含 anthropic SDK
```

## 平台支持

- **Linux/macOS** - 完整支持（包括 daemon 模式）
- **Windows** - 支持除 daemon 外的所有功能

## CI 集成

```bash
# 运行评测
openclaw-edd run --cases cases.yaml --output-json report.json

# 检查退出码
if [ $? -ne 0 ]; then
  echo "评测失败"
  exit 1
fi
```

## License

MIT
