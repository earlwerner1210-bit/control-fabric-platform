.DEFAULT_GOAL := help
SHELL := /bin/bash

# ── Variables ─────────────────────────────────────────────────────────────────
PYTHON   := python3
PIP      := pip
PYTEST   := pytest
RUFF     := ruff
MYPY     := mypy
ALEMBIC  := alembic
COMPOSE  := docker compose

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Setup ─────────────────────────────────────────────────────────────────────

.PHONY: install
install: ## Install Python dependencies via pip
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]" 2>/dev/null || $(PIP) install -e .
	$(PIP) install pytest pytest-asyncio pytest-cov httpx ruff mypy

.PHONY: bootstrap
bootstrap: ## Full bootstrap: install deps, start infra, migrate, seed
	bash infra/scripts/bootstrap.sh

# ── Docker / Dev ──────────────────────────────────────────────────────────────

.PHONY: dev
dev: ## Start all services via docker compose
	$(COMPOSE) up --build -d

.PHONY: dev-down
dev-down: ## Stop all docker compose services
	$(COMPOSE) down

# ── Testing ───────────────────────────────────────────────────────────────────

.PHONY: test
test: ## Run the full test suite with coverage
	$(PYTEST) --cov=app --cov-report=term-missing -v

.PHONY: test-unit
test-unit: ## Run unit tests only
	$(PYTEST) tests/unit -v

.PHONY: test-integration
test-integration: ## Run integration tests only
	$(PYTEST) tests/integration -v

.PHONY: test-api
test-api: ## Run API endpoint tests only
	$(PYTEST) tests/api -v

# ── Linting / Formatting ─────────────────────────────────────────────────────

.PHONY: lint
lint: ## Run ruff linter and mypy type checker
	$(RUFF) check app/ tests/
	$(MYPY) app/

.PHONY: format
format: ## Auto-format code with ruff
	$(RUFF) format app/ tests/
	$(RUFF) check --fix app/ tests/

# ── Database ──────────────────────────────────────────────────────────────────

.PHONY: migrate
migrate: ## Run pending Alembic migrations
	$(ALEMBIC) upgrade head

.PHONY: migrate-create
migrate-create: ## Create a new Alembic migration (usage: make migrate-create MSG="add foo table")
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

.PHONY: seed
seed: ## Seed sample data into the database
	$(PYTHON) infra/scripts/seed_data.py

# ── Build ─────────────────────────────────────────────────────────────────────

.PHONY: build
build: ## Build Docker images
	$(COMPOSE) build

.PHONY: clean
clean: ## Remove caches, coverage data, and build artefacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov dist build *.egg-info
