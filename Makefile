PROJECT_NAME := jayrah

all: test lint format coverage

sync:
	@uv sync

test: sync
	@echo "Running Tests"
	@echo "-------------"
	@uv run pytest -v

ruff: sync
	@echo "Running Ruff"
	@echo "--------------"
	@uvx ruff check --unsafe-fixes --preview --fix

pylint: sync
	@echo "Running Pylint"
	@echo "--------------"
	@uv run pylint $(PROJECT_NAME)

lint: sync pylint ruff

format: sync
	@echo "Running formatter"
	@echo "----------------"
	@uvx ruff format

coverage: sync
	@echo "Running coverage"
	@echo "---------------"
	@uv run pytest --cov=$(PROJECT_NAME) --cov-report=html --cov-report=term-missing

web:
	@echo "Starting Jayrah Web UI at http://127.0.0.1:8000 ..."
	@uvicorn jayrah.ui.web.server:app --reload --reload-dir ./jayrah/ui/web
