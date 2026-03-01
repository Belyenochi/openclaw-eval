# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
