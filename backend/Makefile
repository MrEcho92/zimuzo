# Makefile

SRC_DIRS := app tests
TESTS_DIR := tests

.PHONY: help
help:
	@echo "Usage: make <command>"
	@echo ""
	@echo "Commands:"
	@echo "  install          Install dependencies and pre-commit hooks"
	@echo "  lint             Lint code with ruff"
	@echo "  format           Auto-format code with ruff"
	@echo "  clean            Remove caches and build artifacts"
	@echo "  test             Run tests with pytest"
	@echo "  help             Show this help message"
	@echo "  venv             Create a virtual environment"
	@echo "  run         	  Run FastAPI development server"

.PHONY: .uv  ## Check that uv is installed
.uv:
	@uv -V || echo 'Please install uv: https://docs.astral.sh/uv/getting-started/installation/'

.PHONY: .pre-commit  ## Check that pre-commit is installed
.pre-commit: .uv
	@uv run pre-commit -V || uv pip install pre-commit

.PHONY: .pre-commit-update  ## Check that pre-commit is installed
.pre-commit-update: .uv
	uv run pre-commit autoupdate

.PHONY: install  ## Install the package, dependencies, and pre-commit for local development
install: .uv
	uv sync
	uv pip install pre-commit
	uv run pre-commit install --install-hooks

.PHONY: rebuild-lockfiles  ## Rebuild lockfiles from scratch, updating all dependencies
rebuild-lockfiles: .uv
	uv lock --upgrade

.PHONY: format  ## Auto-format python source files
format: .uv
	uv run ruff check --fix $(SRC_DIRS)
	uv run ruff format $(SRC_DIRS)

.PHONY: lint  ## Lint python source files
lint: .uv
	uv run ruff check $(SRC_DIRS)
	uv run ruff format --check $(SRC_DIRS)

.PHONY: isort ## Run isort on python source files
isort: .uv
	uv run isort $(SRC_DIR)

.PHONY: venv
venv: .uv
	uv venv

.PHONY: tests
tests: .uv ## Run tests with pytest
	uv run pytest -v --cov=$(TESTS_DIR) --cov-report=term-missing

.PHONY: all  ## Run the standard set of checks performed in CI
all: lint format isort

.PHONY: start
start: ## Run FastAPI development server
	uv run ./start.sh

.PHONY: docker-compose-up
docker-compose-up: ## Run docker compose up
	docker-compose up -d

.PHONY: docker-compose-down
docker-compose-down: ## Run docker compose down
	docker-compose down

.PHONY: db-migrate
db-migrate: ## Create a new migration and run migrations
	@if [ -z "${MSG}" ]; then echo "Error: MSG variable is not set. Usage: make db-migrate MSG='your message'"; exit 1; fi
	uv run alembic revision --autogenerate -m ${MSG}

.PHONY: db-upgrade
db-upgrade: ## Apply all pending migrations
	uv run alembic upgrade head

.PHONY: clean  ## Clear local caches and build artifacts
clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]'`
	rm -f `find . -type f -name '*~'`
	rm -f `find . -type f -name '.*~'`
	rm -rf .cache
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf *.egg-info
	rm -f .coverage
	rm -f .coverage.*
	rm -rf build
	rm -rf dist
	rm -rf site
	rm -rf docs/_build
	rm -rf docs/.changelog.md docs/.version.md docs/.tmp_schema_mappings.html
	rm -rf backend/test.db
	rm -rf coverage.xml
