# Contributing

## Development Setup

Use Python 3.12 for local development.

```bash
python -m pip install -r requirements-dev.txt
pre-commit install
pytest
```

## Checks

Run these before opening a pull request:

```bash
pytest
pre-commit run --all-files
```

For Docker changes, build at least the affected image locally when practical:

```bash
docker build -t ib-gateway-dev --build-arg PROGRAM=ibgateway build/
```

## Pull Requests

Keep changes scoped to one concern. Include tests for bug fixes and update
documentation when behavior, configuration, or supported workflows change.
