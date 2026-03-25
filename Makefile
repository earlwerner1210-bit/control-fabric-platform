.PHONY: help install dev test lint format build clean bootstrap seed

help:
	@echo "Control Fabric Platform — available commands:"
	@echo ""
	@echo "  make install     Install all dependencies"
	@echo "  make dev         Start all services in development mode"
	@echo "  make test        Run full test suite"
	@echo "  make lint        Run ruff + mypy linters"
	@echo "  make format      Run black formatter"
	@echo "  make build       Build all Docker images"
	@echo "  make clean       Remove build artifacts"
	@echo "  make bootstrap   Run full environment bootstrap"
	@echo "  make seed        Seed sample data"

install:
	poetry install

dev:
	docker compose up --build

test:
	poetry run pytest tests/ -v --cov=. --cov-report=term-missing

lint:
	poetry run ruff check .
	poetry run mypy .

format:
	poetry run black .
	poetry run ruff check --fix .

build:
	docker compose build

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true

bootstrap:
	./scripts/bootstrap.sh

seed:
	poetry run python scripts/seed_data.py
