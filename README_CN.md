<p align="center">
  <img src="logo.png" alt="openclaw-edd logo" width="600">
</p>

# openclaw-edd

[![CI](https://github.com/Belyenochi/openclaw-edd/actions/workflows/ci.yml/badge.svg)](https://github.com/Belyenochi/openclaw-edd/actions)
[![PyPI version](https://badge.fury.io/py/openclaw-edd.svg)](https://pypi.org/project/openclaw-edd/)
[![npm version](https://badge.fury.io/js/openclaw-edd.svg)](https://www.npmjs.com/package/openclaw-edd)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

OpenClaw Agent 的评测驱动开发工具 —— 从真实交互中保存 golden cases，在变更上线前捕获退步。

[English Documentation](README.md)

## 设计理念

**CLI —— 信任来自可复现的证据，而非一次性的人工检查。**

插件解决的是"我改了 skill，有没有破坏什么？"CLI 更进一步：同一份 `edd.yaml` 可以在任何地方运行——本地终端、团队 review，或 CI 流水线。Skill 质量不再依赖"作者说它能用"，而是依赖任何人都能复现的证明。

**插件 —— Golden cases 从真实使用中生长，而非事先捏造。**

传统测试从想象的场景出发。但 Agent 的行为空间太大，难以预判它会选择哪些工具、以何种顺序调用、输出什么内容。插件将这个逻辑倒过来：正常使用你的 agent，当一次交互结果令人满意时，用 `/edd save` 将这一轮快照为 golden case。测试用例是真实行为的录像，而不是猜测。修改 skill 后，`/edd` 回放这些录像，告诉你好的行为是否还在。

## 快速开始

```bash
pip install openclaw-edd

openclaw-edd watch                          # 查看 agent 实际调用了哪些工具
openclaw-edd run --quickstart --agent main  # 运行 6 个内置用例
```

完整流程见[用户指南](./docs/USER_JOURNEY_CN.md)。

## 用例格式

用例由 `/edd save` 自动生成，也可以手动编辑：

```yaml
cases:
  - id: mysql_slow_query
    message: "MySQL 最近有慢查询吗"
    expect_tools:
      - exec
    expect_commands:
      - "check_health"
    forbidden_commands:
      - "rm -rf"
    expect_output_contains:
      - "慢查询"
    timeout_s: 30
    tags: [mysql, sre]
```

完整字段说明（`pass_at_k`、`expect_tool_args`、`eval_type`、`expect_plan_contains` 等）见[用户指南](./docs/USER_JOURNEY_CN.md)。

## CLI

```bash
pip install openclaw-edd
```

**核心命令**

```bash
openclaw-edd watch                                              # 实时监听工具事件
openclaw-edd run --cases edd.yaml --output-json report.json    # 运行用例
openclaw-edd run --quickstart --agent main --summary-line      # 运行 6 个内置用例
openclaw-edd sessions                                           # 查看历史 session
openclaw-edd trace                                              # 回放事件链
openclaw-edd gen-cases                                          # 生成用例模板
```

**EDD 闭环**

```bash
openclaw-edd edd mine --output mined.yaml                       # 从历史 session 挖掘 golden cases
openclaw-edd edd review --input mined.yaml                      # 交互式审核挖掘的用例
openclaw-edd edd suggest --report report.json                   # 生成改进建议
openclaw-edd edd apply                                          # 将建议应用到 workspace
openclaw-edd edd diff --before round1.json --after round2.json  # 对比两次运行
openclaw-edd edd judge --report report.json                     # LLM 评分
openclaw-edd edd export --input golden.jsonl --format csv       # 导出 golden dataset
```

插件和 CLI 共享同一套 `edd.yaml` 格式。完整流程见[用户指南](./docs/USER_JOURNEY_CN.md)。

## OpenClaw 插件

如果你使用 [OpenClaw](https://github.com/Belyenochi/openclaw)，插件可以让你在对话界面里直接管理 golden cases。

```
openclaw plugins install openclaw-edd
```

遇到一次好的 agent 交互后，将其保存为 golden case：

```
/edd save
```

修改 skill 后，回放所有已保存的用例，检查是否退步：

```
/edd
```

用例以可读的 YAML 格式保存在 `<workspace>/skills/<skill>/edd.yaml`——与 CLI 读取的格式完全相同。

## 参与贡献

欢迎提问、讨论和 Pull Request。如果有什么不对劲或可以做得更好，开一个 Issue 就行——来自真实使用的反馈是这个项目进步的方式。

## License

MIT — 详见 [LICENSE](LICENSE)。
