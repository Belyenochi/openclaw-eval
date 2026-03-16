<p align="center">
  <img src="logo.png" alt="openclaw-edd logo" width="600">
</p>

# openclaw-edd

[![CI](https://github.com/Belyenochi/openclaw-edd/actions/workflows/ci.yml/badge.svg)](https://github.com/Belyenochi/openclaw-edd/actions)
[![PyPI version](https://badge.fury.io/py/openclaw-edd.svg)](https://pypi.org/project/openclaw-edd/)
[![npm version](https://badge.fury.io/js/openclaw-edd.svg)](https://www.npmjs.com/package/openclaw-edd)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Evaluation-Driven Development for OpenClaw agents — save golden cases from real interactions, catch regressions before they reach users.

[中文文档](README_CN.md)

## Design Philosophy

**CLI — Trust comes from reproducible evidence, not one-off manual checks.**

The plugin solves "I changed my skill, did I break something?" The
CLI takes that further: the same `edd.yaml` runs anywhere — a local
terminal session, a team review, or a CI pipeline. Skill quality
stops depending on "the author says it works" and starts depending
on repeatable proof that anyone can run.

**Plugin — Golden cases grow from real usage, not upfront speculation.**

Traditional testing starts with imagined scenarios. But an Agent's
behavior space is too large to predict which tools it will pick,
in what order, or what output it will produce. The plugin inverts
this: use your agent normally, and when a result is good, `/edd save`
snapshots that turn as a golden case. Test cases are recordings of
real behavior, not guesses. After editing a skill, `/edd` replays
those recordings and tells you whether the good behaviors survived.

## Quick Start

```bash
pip install openclaw-edd

openclaw-edd watch                          # see what tools your agent actually uses
openclaw-edd run --quickstart --agent main  # run 6 built-in cases against your agent
```

See the [User Guide](./USER_JOURNEY.md) for the full walkthrough.

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

## CLI

```bash
pip install openclaw-edd
```

**Core**

```bash
openclaw-edd watch                                              # watch live tool events
openclaw-edd run --cases edd.yaml --output-json report.json    # run your cases
openclaw-edd run --quickstart --agent main --summary-line      # run 6 built-in cases
openclaw-edd sessions                                           # list historical sessions
openclaw-edd trace                                              # replay event chain
openclaw-edd gen-cases                                          # generate case templates
```

**EDD Loop**

```bash
openclaw-edd edd mine --output mined.yaml                       # mine cases from session history
openclaw-edd edd review --input mined.yaml                      # interactively approve/reject mined cases
openclaw-edd edd suggest --report report.json                   # generate improvement suggestions
openclaw-edd edd apply                                          # apply suggestions to workspace
openclaw-edd edd diff --before round1.json --after round2.json  # compare runs
openclaw-edd edd judge --report report.json                     # LLM-based scoring
openclaw-edd edd export --input golden.jsonl --format csv       # export golden dataset
```

The plugin and CLI share the same `edd.yaml` format. See the [User Guide](./USER_JOURNEY.md) for the full walkthrough.

## OpenClaw Plugin

If you use [OpenClaw](https://github.com/Belyenochi/openclaw), the plugin gives you golden case management directly inside the chat interface.

```
openclaw plugins install openclaw-edd
```

After a good agent interaction, save it as a golden case:

```
/edd save
```

After editing a skill, replay all saved cases and check for regressions:

```
/edd
```

Cases are stored as human-readable YAML at `<workspace>/skills/<skill>/edd.yaml` — the same format the CLI reads.

## Contributing

Questions, ideas, and pull requests are welcome. If something doesn't work or could be better, open an issue — feedback from real usage is how this project improves.

## License

MIT — see [LICENSE](LICENSE) for details.
