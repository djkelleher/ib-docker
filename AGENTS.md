# AGENTS.md

This file provides guidance to Codex when working with code in this repository.

## Build & Test Commands

```bash
# Run all tests
pytest

# Run single test file
pytest tests/unit/test_repository.py

# Run single test
pytest tests/unit/test_repository.py::test_function_name -v

# Run with coverage
pytest --cov=src

# Format code
black src/ tests/ --line-length 100

# Sort imports
isort src/ tests/ --profile black

# Lint
flake8 src/ tests/ --max-complexity 10
```

use all python features up to python 3.12

## Code Style

- Formatter: black (100 char lines)
- Import sorting: isort (black profile)
- Linting: flake8 (max complexity 10)
- Type hints required on all function signatures
- Docstrings: NumPy convention

## Naming Conventions

- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: leading underscore (`_method`)
- Enum values: lowercase string values (`OrderStatus.PENDING = "pending"`)

## Import Rules

- All imports at top of files - no lazy imports, no `try/except ImportError`
- Never use ImportError handling - assume all imports succeed
- No `__all__` definitions
- No backward compatibility re-exports or wrappers
- Order: stdlib → third-party → local

## General Rules

- Do not use `getattr` or `hasattr` - use direct attribute access
- Do not revert files to older git commits without asking first
- Do not create nested folders with only a single file
- Commit all changes after code is modified with detailed commit messages
- Whenever we make a bug fix, please create a unit test that will catch this bug if it ever shows up again. This way we don't create regressions.
