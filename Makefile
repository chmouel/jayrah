PROJECT_NAME := jayrah

all: test lint format coverage

sync:
	@uv sync

test: sync
	@echo "Running Tests"
	@echo "-------------"
	@pytest -vvv -s

lint: sync
	@echo "Running linter"
	@echo "--------------"
	@ruff check --unsafe-fixes --preview --fix

format: sync
	@echo "Running formatter"
	@echo "----------------"
	@ruff format

coverage: sync
	@echo "Running coverage"
	@echo "---------------"
	@pytest --cov=$(PROJECT_NAME) --cov-report=html --cov-report=term-missing 
