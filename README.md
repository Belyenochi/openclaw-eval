<p align="center">
  <img src="logo.jpg" alt="openclaw-edd logo" width="200">
</p>

# openclaw-edd

[![CI](https://github.com/Belyenochi/openclaw-edd/actions/workflows/ci.yml/badge.svg)](https://github.com/Belyenochi/openclaw-edd/actions)
[![PyPI version](https://badge.fury.io/py/openclaw-edd.svg)](https://pypi.org/project/openclaw-edd/)
[![npm version](https://badge.fury.io/js/openclaw-edd.svg)](https://www.npmjs.com/package/openclaw-edd)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Evaluation-Driven Development for OpenClaw agents — save golden cases from real interactions, catch regressions before they reach users.

[中文文档](README_CN.md)

## Design Philosophy

**Plugin — Golden cases grow from real usage, not upfront speculation.**

Traditional testing starts with imagined scenarios. But an Agent's
behavior space is too large to predict which tools it will pick,
in what order, or what output it will produce. The plugin inverts
this: use your agent normally, and when a result is good, `/edd save`
snapshots that turn as a golden case. Test cases are recordings of
real behavior, not guesses. After editing a skill, `/edd` replays
those recordings and tells you whether the good behaviors survived.

**CLI — Trust comes from reproducible evidence, not one-off manual checks.**

The plugin solves "I changed my skill, did I break something?" The
CLI solves "why should anyone else trust that this skill works?" The
same `edd.yaml` — built interactively with `/edd save` — runs unattended
in CI via `openclaw-edd run`. A PR that regresses a golden case gets
blocked. Skill quality stops depending on "the author says it works"
and starts depending on repeatable proof.

## Quick Start

Install the OpenClaw plugin:

```
openclaw plugins install openclaw-edd
```

After a good agent interaction, save it as a golden case:

```
/edd save
```

After modifying a skill, run all saved cases to check for regressions:

```
/edd
```

That's it. Cases are stored as human-readable YAML at `<workspace>/skills/<skill>/edd.yaml`.

## Test Case Format

Cases are saved automatically by `/edd save` and editable by hand:

```yaml
cases:
  - id: mysql_slow_query
    message: "Any slow queries in MySQL recently"
    expect_tools:
      - exec
    expect_commands:
      - "check_health"
    forbidden_commands:
      - "rm -rf"
    expect_output_contains:
      - "slow query"
    timeout_s: 30
    tags: [mysql, sre]
```

For the full field reference (`pass_at_k`, `expect_tool_args`, `eval_type`, `expect_plan_contains`, etc.), see the [User Guide](./USER_JOURNEY.md).

## CI / CLI Integration

For CI pipelines and local observability, install the Python CLI:

```bash
pip install openclaw-edd

# Run cases in CI
openclaw-edd run --cases edd.yaml --output-json report.json

# Watch live tool events
openclaw-edd watch

# Mine golden cases from session history
openclaw-edd edd mine --output mined.yaml
```

The plugin and CLI share the same `edd.yaml` format. See the [User Guide](./USER_JOURNEY.md) for the full EDD loop (`suggest` → `apply` → `diff` → `mine` → `judge` → `export`).

## License

MIT
