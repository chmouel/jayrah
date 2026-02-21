# Repository Guidelines

## Rewrite In Progress (Mandatory)
- The repository is currently in a Python -> Rust Ratatui TUI rewrite.
- Before starting any rewrite-related task, always read `MIGRATION.md`.
- During rewrite work, always append step-by-step progress entries to `MIGRATION.md` as you go.
- During rewrite work, always append a `Remaining TODOs / uncertainties` update to `MIGRATION.md` for the current state (use `none` when there are no open items).
- Required log format: `YYYY-MM-DD HH:MM UTC | actor | area | action | result | next`
- If scope changes, add a `Decision` log entry before implementation.
- If blocked, add a `Blocker` log entry with clear unblock conditions.
- Keep the migration log append-only; never delete prior entries.

## Project Structure & Module Organization
- Source: `jayrah/` (entrypoint `jayrah.cli:main`). Key modules: `api/`, `commands/`, `ui/` (TUI + `ui/web/`), `config/`, `utils/`.
- Tests: `tests/` with `test_*.py` modules and `conftest.py`.
- Tooling: `pyproject.toml` (deps and scripts), `Makefile` (common tasks), `.pre-commit-config.yaml` (lint/test hooks).
- Config: user settings in `~/.config/jayrah/config.yaml`.

## Build, Test, and Development Commands
Use uv and Makefile targets:

```sh
make sync           # Install deps via uv
make test           # Run pytest (verbose)
make lint           # Run pylint + ruff check
make format         # Format with ruff
make coverage       # Pytest coverage (HTML in ./htmlcov)
uv run jayrah ...   # Run CLI locally (e.g., browse)
make web            # Start web UI at http://127.0.0.1:8000
```

## Coding Style & Naming Conventions
- Language: Python 3.12. Indent 4 spaces, UTF-8 files.
- Style: format with `ruff format`; lint with `ruff` and `pylint`.
- Naming: packages/modules `lower_snake_case`; classes `PascalCase`; functions/vars `snake_case`.
- Imports: prefer absolute within `jayrah.*`.
- Keep CLI user messages concise; centralize logic under `api/` and `utils/`.

## Testing Guidelines
- Framework: `pytest` (+ `pytest-asyncio`, `pytest-cov`).
- Location: add tests under `tests/` named `test_<area>.py`; test functions `test_<behavior>()`.
- Coverage: add regression tests for bugs; aim for meaningful coverage (see `make coverage`).
- Running examples:

```sh
uv run pytest -k mcp -vv
uv run pytest tests/test_commands.py::test_browse
```

## Commit & Pull Request Guidelines
- Commits: follow Conventional Commits seen in history (e.g., `feat: ...`, `fix: ...`, `refactor: ...`).
- PRs: clear description, linked issues, reproduction steps, and screenshots/GIFs for UI.
- CI hygiene: run `make lint test format` locally; ensure `pre-commit` passes.
- Scope: keep PRs focused; update README or docs when behavior changes.

## Security & Configuration Tips
- Secrets: never commit credentials; store Jira creds in `~/.config/jayrah/config.yaml` (supports Basic/Bearer).
- Web UI: local-only; do not expose `jayrah web` publicly.
- Paths: prefer `pathlib` and avoid hard-coded OS-specific paths.

## Architecture Overview
- CLI subcommands in `jayrah/commands/`; shared logic in `api/` and `utils/`.
- TUI/Web in `jayrah/ui/`; MCP server in `jayrah/mcp/` (`uv run jayrah mcp`).
