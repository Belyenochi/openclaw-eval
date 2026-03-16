# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.5.0] - 2026-03-15

### Added
- npm package `@belyenochi/openclaw-edd` now published to GitHub Packages on every release

## [0.4.3] - 2026-03-14

### Fixed
- Quickstart cases: `weather_query`/`file_listing` now use `expect_tools` instead of unreliable `expect_actions`; `safety_refusal` relies solely on `forbidden_commands` (removed fragile output keyword matching)
- `_check_plan_contains` searches `e.thinking` in addition to `e.plan_text`, fixing false negatives for kimi-k2.5 and other models that store reasoning in thinking blocks

### Docs
- All documentation (EN + CN) synced: `edd review`, `pass_at_k`, `expect_plan_contains`, `expect_output_contains` AND semantics
- `docs/JUDGE_COMMAND.md` command prefix corrected to `openclaw-edd`
- CHANGELOG now required for every release (enforced via pre-commit hook)

## [0.4.2] - 2026-03-14

### Fixed
- `_check_plan_contains` now also searches `e.thinking` blocks, fixing false failures for models like kimi-k2.5 that store reasoning in thinking rather than plan text
- Quickstart cases: replaced unreliable `expect_actions` with `expect_tools`; removed misleading `expect_output_contains` from `safety_refusal` (covered by `forbidden_commands`)
- Clarified `expect_output_contains` AND semantics in README and user guides

## [0.4.1] - 2026-03-13

### Added
- `edd review` command: interactive approve/reject workflow for mined golden datasets
- `run --only-approved`: skip unapproved records when loading a JSONL golden dataset
- `run --pass-at-k K`: Pass@K evaluation — run each case K times, passed if ≥1 attempt succeeds
- `EvalCase.pass_at_k` field for per-case K configuration
- `EvalResult` fields: `pass_at_k_k`, `pass_at_k_passes`, `pass_at_k_rate`, `pass_at_k_session_ids`

### Fixed
- mypy `[import-untyped]` error for PyYAML stubs suppressed via `disable_error_code`
- Pre-commit hook added: black + isort + mypy + pytest run before every commit

## [0.4.0] - 2026-03-11

### Changed
- Refactored Event model to match actual session structure
- Translated internal print statements from Chinese to English

## [0.2.0] - 2026-03-01

### Added
- Session isolation: per-case event filtering by time window
- Command-based assertions: `expect_commands`, `forbidden_commands`, `expect_commands_ordered`
- Substring matching for `expect_tool_args`
- `--quickstart` flag with built-in test cases
- `--summary-line` for CI
- JSON test case support (no PyYAML dependency needed for JSON)
- `USER_JOURNEY.md` — complete user guide
- `CONTRIBUTING.md`
- GitHub Actions CI workflow

### Changed
- Report schema includes `checks` breakdown per case
- `expect_tool_args` uses substring matching instead of exact match

### Removed
- `QUICKSTART.md` (replaced by `USER_JOURNEY.md`)

## [0.1.2] - 2026-02-28

### Added
- Initial release with `watch`, `run`, `edd suggest/apply/diff/mine/judge/export`
