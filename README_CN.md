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

**插件 —— Golden cases 从真实使用中生长，而非事先捏造。**

传统测试从想象的场景出发。但 Agent 的行为空间太大，难以预判它会选择哪些工具、以何种顺序调用、输出什么内容。插件将这个逻辑倒过来：正常使用你的 agent，当一次交互结果令人满意时，用 `/edd save` 将这一轮快照为 golden case。测试用例是真实行为的录像，而不是猜测。修改 skill 后，`/edd` 回放这些录像，告诉你好的行为是否还在。

**CLI —— 信任来自可复现的证据，而非一次性的人工检查。**

插件解决的是"我改了 skill，有没有破坏什么？"CLI 更进一步：同一份 `edd.yaml` 可以在任何地方运行——本地终端、团队 review，或 CI 流水线。Skill 质量不再依赖"作者说它能用"，而是依赖任何人都能复现的证明。

## 快速开始

安装 OpenClaw 插件：

```
openclaw plugins install openclaw-edd
```

遇到一次好的 agent 交互后，将其保存为 golden case：

```
/edd save
```

修改 skill 后，运行所有已保存的用例检查是否退步：

```
/edd
```

就这些。用例以可读的 YAML 格式保存在 `<workspace>/skills/<skill>/edd.yaml`。

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

完整字段说明（`pass_at_k`、`expect_tool_args`、`eval_type`、`expect_plan_contains` 等）见[用户指南](./USER_JOURNEY_CN.md)。

## CI / CLI 集成

CI 流水线和本地可观测性，安装 Python CLI：

```bash
pip install openclaw-edd

# 在 CI 中运行用例
openclaw-edd run --cases edd.yaml --output-json report.json

# 实时监听工具事件
openclaw-edd watch

# 从历史 session 挖掘 golden cases
openclaw-edd edd mine --output mined.yaml
```

插件和 CLI 共享同一套 `edd.yaml` 格式。完整 EDD 闭环（`suggest` → `apply` → `diff` → `mine` → `judge` → `export`）见[用户指南](./USER_JOURNEY_CN.md)。

## 参与贡献

欢迎提问、讨论和 Pull Request。如果有什么不对劲或可以做得更好，开一个 Issue 就行——来自真实使用的反馈是这个项目进步的方式。

## License

MIT — 详见 [LICENSE](LICENSE)。
