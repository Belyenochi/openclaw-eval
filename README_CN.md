<p align="center">
  <img src="logo.jpg" alt="openclaw-edd logo" width="200">
</p>

# openclaw-edd

[![CI](https://github.com/Belyenochi/openclaw-edd/actions/workflows/ci.yml/badge.svg)](https://github.com/Belyenochi/openclaw-edd/actions)
[![PyPI version](https://badge.fury.io/py/openclaw-edd.svg)](https://pypi.org/project/openclaw-edd/)
[![npm version](https://badge.fury.io/js/openclaw-edd.svg)](https://www.npmjs.com/package/openclaw-edd)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

OpenClaw Agent 的评测驱动开发工具 —— 从真实交互中保存 golden cases，在变更上线前捕获退步。

[English Documentation](README.md)

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

## License

MIT
