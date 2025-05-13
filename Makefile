PROJECT_NAME := jayrah

all: test lint format coverage

sync:
	@uv sync

test: sync
	@echo "Running Tests"
	@echo "-------------"
	@uv run pytest -v

lint: sync
	@echo "Running linter"
	@echo "--------------"
	@uvx ruff check --unsafe-fixes --preview --fix

format: sync
	@echo "Running formatter"
	@echo "----------------"
	@uvx ruff format

coverage: sync
	@echo "Running coverage"
	@echo "---------------"
	@uv run pytest --cov=$(PROJECT_NAME) --cov-report=html --cov-report=term-missing 
