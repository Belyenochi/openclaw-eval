# openclaw-edd 使用路径：7 步完成 EDD 闭环

本指南面向所有 OpenClaw 用户。无需任何领域技能，重点说明 OpenClaw 的真实工具模型。

## Step 0: 发现实际工具名称（2 分钟）
OpenClaw 使用低层原语（`exec`, `read`, `write`, `process`, `session_status`），**不是** `get_weather` 这类语义化工具名。
这是新用户最容易踩的坑。

```bash
openclaw-edd watch
```
在你的聊天应用里发一条消息，观察日志里的工具名。编写用例时要使用这些实际工具名。

## Step 1: 安装（30 秒）
```bash
pip install openclaw-edd
```

## Step 2: 运行 Quickstart 评测（3 分钟）
```bash
openclaw-edd run --quickstart --agent main --output-json round1.json --summary-line
```
内置 6 个用例：
- 问候
- Web 搜索
- 文件创建
- 目录列出
- 多步推理
- 安全拒绝

## Step 3: 查看失败原因（2 分钟）
```bash
python3 -m json.tool round1.json
openclaw-edd edd suggest --report round1.json  # 需要 ANTHROPIC_API_KEY
```
常见失败原因：
- “缺少必要工具调用” → `expect_tools` 写错或 agent 走了不同路径
- “输出缺少关键词” → 表达方式不同（调整关键词）
- “调用了禁止的工具” → 安全问题

## Step 4: 修复并重跑（5 分钟）
```bash
openclaw-edd run --quickstart --agent main --output-json round2.json --summary-line
```

## Step 5: 对比两轮结果（30 秒）
```bash
openclaw-edd edd diff --before round1.json --after round2.json
```

## Step 6: 编写自定义用例
```json
{
  "cases": [
    {
      "id": "my_task",
      "message": "自然语言任务描述",
      "eval_type": "regression",
      "expect_tools": ["exec"],
      "expect_commands": ["命令关键词"],
      "forbidden_commands": ["危险命令模式"],
      "expect_output_contains": ["回复中的关键词"],
      "forbidden_tools": ["exec"],
      "timeout_s": 60,
      "tags": ["my_domain"]
    }
  ]
}
```

断言优先级建议：
1. `expect_output_contains` — 最可靠，验证最终结果
2. `expect_commands` — 白盒验证，确认 agent 执行了正确命令（匹配 `exec` 的 `input.command` 子串）
3. `forbidden_commands` — 安全护栏
4. `expect_tools` — 粗粒度检查（`exec`/`read`/`write`）
5. `forbidden_tools` — 纯聊天场景

## Step 7: CI 集成
```bash
openclaw-edd run --cases my_cases.json --agent main \
  --threshold 0.8 --regression-threshold 1.0 \
  --output-json ci.json --summary-line --quiet
# exit 0 = pass, exit 1 = fail, exit 2 = config error
```

```
watch → run → suggest → fix → run → diff → custom cases → CI
```
