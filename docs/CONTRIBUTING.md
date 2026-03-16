# Contributing to openclaw-edd

## Development Setup

```bash
git clone https://github.com/Belyenochi/openclaw-edd.git
cd openclaw-edd
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -v
pytest tests/ --cov=openclaw_edd --cov-report=term-missing
```

## Code Style

- All code, comments, and docstrings in English
- Type hints on all public functions
- Google-style docstrings
- Format with Black (line length 88)
- Sort imports with isort

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass: `pytest tests/ -v`
4. Update CHANGELOG.md
5. Submit PR with a clear description

## Test Case Contributions

We welcome new test cases. See [USER_JOURNEY.md](./USER_JOURNEY.md) Step 6 for the case format.
When contributing cases, please include:
- A clear `description` field
- Appropriate `eval_type` (regression or capability)
- Meaningful `tags` for filtering

## Reporting Issues

Please include:
- openclaw-edd version (`openclaw-edd --version`)
- OpenClaw version
- OS and Python version
- Full command and error output
