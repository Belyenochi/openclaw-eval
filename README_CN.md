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

<p align="center"><img src="docs/images/terminal-output.svg" width="680"/></p>

## 为什么需要

你改了一个 skill，但不知道有没有破坏别的东西。唯一的办法是再手动跑一遍 agent——每次都这样。openclaw-edd 解决这个问题：把真实 session 变成测试用例，按需回放。Skill 质量不再依赖"作者说它能用"，而是依赖任何人都能复现的证明。

## 工作原理

<p align="center"><img src="docs/images/architecture.svg" width="680"/></p>

openclaw-edd 有两个入口，共享同一套 `edd.yaml` 格式：

- **插件**（`/edd save`、`/edd`）—— 运行在 OpenClaw 对话界面内。把一次好的交互保存为 golden case，修改 skill 后回放所有用例。
- **CLI**（`openclaw-edd`）—— 在任何地方运行：本地终端、团队 review 或 CI 流水线。从 session 历史挖掘用例、对比两次运行、用 LLM 打分。

Session 文件是唯一的数据来源。无需埋点、无需修改配置、无需重启 Gateway。

## 快速开始

**插件（在对话界面中）**

```
openclaw plugins install openclaw-edd
/edd save          # 把一次好的交互保存为 golden case
/edd               # 修改 skill 后回放所有用例
```

**CLI（在终端中）**

```bash
pip install openclaw-edd
openclaw-edd watch                          # 查看 agent 实际调用了哪些工具
openclaw-edd run --quickstart --agent main  # 运行 6 个内置用例
```

完整流程见[用户指南](./docs/USER_JOURNEY_CN.md)。

## EDD 闭环

<p align="center"><img src="docs/images/edd-loop.svg" width="680"/></p>

| 阶段 | 命令 |
|------|------|
| **Capture** | `/edd save` · `openclaw-edd edd mine --output mined.yaml` |
| **Evaluate** | `openclaw-edd run --cases edd.yaml --output-json report.json` |
| **Improve** | `openclaw-edd edd suggest --report report.json` · `edd apply` |
| **Harvest** | `openclaw-edd edd diff --before r1.json --after r2.json` · `edd export` |

## 用例格式

用例由 `/edd save` 自动生成，也可以手动编辑：

```yaml
cases:
  - id: mysql_slow_query
    message: "MySQL 最近有慢查询吗"
    expect_tools: [exec]
    expect_commands: ["check_health"]
    forbidden_commands: ["rm -rf"]
    expect_output_contains: ["慢查询"]
    timeout_s: 30
    tags: [mysql, sre]
```

完整字段说明（`pass_at_k`、`expect_tool_args`、`eval_type`、`expect_plan_contains` 等）见[用户指南](./docs/USER_JOURNEY_CN.md)。

## 参与贡献

欢迎提问、讨论和 Pull Request。如果有什么不对劲或可以做得更好，开一个 Issue 就行——来自真实使用的反馈是这个项目进步的方式。

## License

MIT — 详见 [LICENSE](LICENSE)。
