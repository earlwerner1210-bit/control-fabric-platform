.PHONY: help install dev dev-down test test-unit test-api test-workflows lint format \
       migrate migrate-create seed bootstrap build clean

help:  ## Show this help message
	@echo "Control Fabric Platform"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Dependencies ─────────────────────────────────────────────────────────

install:  ## Install Python dependencies (editable + dev extras)
	pip install -e ".[dev]" 2>/dev/null || poetry install

# ── Development ──────────────────────────────────────────────────────────

dev:  ## Start all services via docker compose
	docker compose up -d

dev-down:  ## Stop all docker compose services
	docker compose down

# ── Testing ──────────────────────────────────────────────────────────────

test:  ## Run full test suite with coverage
	pytest tests/ -v --cov=. --cov-report=term-missing

test-unit:  ## Run unit tests only
	pytest tests/unit/ -v

test-api:  ## Run API tests only
	pytest tests/api/ -v

test-workflows:  ## Run workflow tests only
	pytest tests/workflows/ -v

test-regression:  ## Run regression / eval tests only
	pytest tests/regression/ -v

# ── Code Quality ─────────────────────────────────────────────────────────

lint:  ## Run ruff linter and mypy type checker
	ruff check . && mypy .

format:  ## Format code with ruff and black
	ruff format .
	black .

# ── Database ─────────────────────────────────────────────────────────────

migrate:  ## Run database migrations (alembic upgrade head)
	alembic upgrade head

migrate-create:  ## Create a new migration (alembic revision --autogenerate)
	alembic revision --autogenerate -m "$(MSG)"

# ── Data ─────────────────────────────────────────────────────────────────

seed:  ## Seed sample data into the database
	python data/seed/seed_data.py

# ── Bootstrap ────────────────────────────────────────────────────────────

bootstrap:  ## Run full environment bootstrap
	bash scripts/bootstrap.sh

# ── Docker ───────────────────────────────────────────────────────────────

build:  ## Build all Docker images
	docker compose build

# ── Cleanup ──────────────────────────────────────────────────────────────

clean:  ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage 2>/dev/null || true
