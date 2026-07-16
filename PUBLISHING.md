# Publishing LeXKit to PyPI

This guide covers the full release workflow.

## Prerequisites

```bash
pip install build twine
```

Set up PyPI token in `~/.pypirc`:

```ini
[pypi]
  username = __token__
  password = pypi-YOUR_TOKEN_HERE
```

## Version Bump Workflow

| Release Type | Before    | After     | When to use            |
|-------------|-----------|-----------|------------------------|
| Patch        | 1.0.0     | 1.0.1     | Bug fixes only         |
| Minor        | 1.0.0     | 1.1.0     | New features, backward compat |
| Major        | 1.0.0     | 2.0.0     | Breaking API changes   |

1. Edit `pyproject.toml` → `version = "X.Y.Z"`
2. Edit `lexkit/__init__.py` → `__version__ = "X.Y.Z"`
3. Update `CHANGELOG.md` with release notes
4. Run tests: `make test`

## Build & Publish

```bash
# Clean previous build artifacts
make clean

# Build source dist + wheel
make build
# → dist/lexkit-1.0.0.tar.gz
# → dist/lexkit-1.0.0-py3-none-any.whl

# Verify the distribution
twine check dist/*

# Upload to TestPyPI first (recommended)
make publish-test
pip install --index-url https://test.pypi.org/simple/ lexkit

# Upload to production PyPI
make publish
```

## GitHub Release

```bash
git add pyproject.toml lexkit/__init__.py CHANGELOG.md
git commit -m "chore: release v1.0.0"
git tag -a v1.0.0 -m "Release v1.0.0 — Stable"
git push origin main --tags
```

Then create a GitHub Release at:
https://github.com/lexable-studio/lexkit/releases/new

Attach the `dist/` artifacts to the release.

## Post-publish Verification

```bash
pip install lexkit==1.0.0
lexkit --version
# LeXKit v1.0.0 — Research OS
```
