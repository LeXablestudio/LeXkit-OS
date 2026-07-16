# Contributing to LeXKit

## Setup

```bash
git clone https://github.com/lexable-studio/lexkit.git
cd lexkit
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Rules
- Python 3.11+ type hints on all public functions
- Deterministic only — no randomness, no timestamps in output
- No network calls
- Black + Ruff formatting

## Adding a Tool
1. Create lexkit/tools/mytool.py with a typer.Typer() app
2. Register in lexkit/cli/main.py
3. Add tests in tests/test_mytool.py
4. Document in README.md
