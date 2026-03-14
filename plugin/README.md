# openclaw-edd plugin

Evaluation-Driven Development for OpenClaw — save golden test cases from real interactions, then catch skill regressions before they reach users.

## Install

```
openclaw plugins install openclaw-edd
```

## Usage

After a good agent interaction, save it as a golden case:

```
/edd save
```

After modifying a skill, run all saved cases to check for regressions:

```
/edd
```

If no cases have been saved yet, `/edd` will prompt you to start building your test suite.

## Where cases are stored

Cases are saved to `<workspace>/skills/<skill-name>/edd.yaml` — one file per skill, human-readable and editable. Reports are written to `<workspace>/edd/reports/latest.json`.

## CI / CLI usage

For running evals in CI pipelines, see the [openclaw-edd CLI](https://github.com/Belyenochi/openclaw-edd). The plugin and CLI share the same `edd.yaml` and `report.json` formats.
