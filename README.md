# alembic-check

[![codecov](https://codecov.io/gh/phildp/alembic-check/branch/main/graph/badge.svg)](https://codecov.io/gh/phildp/alembic-check)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A pre-commit hook for Alembic migration tool that ensures database migration integrity and best practices.

## Features

- Validates Alembic migration files for common issues and best practices
- Helps maintain a clean and consistent migration history
- Easy integration with pre-commit framework
- Extensible design for adding new validation rules

## Installation

Add this to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/phildp/alembic-check
    rev: v0.1.0 # Use the latest release
    hooks:
      - id: alembic-check
        args: [src/config/alembic/migrations/] # Path to your migrations directory
```

## Development

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
```

## License

MIT
