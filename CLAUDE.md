# CLAUDE.md — Control Fabric Platform

This file provides context and instructions for Claude Code when working in this repository.

## Project Overview

**Control Fabric Platform** is a modular AI platform for telecom margin assurance, contract intelligence, and operational control. It is built as a Python microservices monorepo with Next.js frontends.

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, Celery, Redis
- **Frontend:** Next.js 14, TypeScript, TailwindCSS
- **Database:** PostgreSQL 16 with pgvector extension
- **Infra:** Docker, Kubernetes, Terraform
- **AI/ML:** OpenAI, Anthropic Claude, vLLM (via inference-gateway)

## Monorepo Layout

```
apps/          → FastAPI gateway + Next.js UIs
services/      → Individual microservices
workflows/     → Multi-service orchestrated workflows
domain-packs/  → Domain-specific rules, prompts, schemas (contract-margin, utilities-field, telco-ops)
shared/        → Common schemas, entities, telemetry, DB helpers
infra/         → Terraform, Kubernetes, Docker configs
data/          → Sample data and seed scripts
tests/         → Unit, integration, workflow, API, regression tests
scripts/       → Bootstrap, seed, backfill, eval utilities
```

## Key Conventions

1. **Service structure:** Each service in `services/` follows the pattern: `main.py`, `router.py`, `service.py`, `models.py`, `schemas.py`, `tests/`.
2. **Shared types:** All cross-service Pydantic models live in `shared/schemas/`. Never duplicate type definitions.
3. **Domain packs:** Each pack in `domain-packs/` is self-contained. Adding a new domain = adding a new pack directory only.
4. **Deterministic first:** The `validator-service` enforces rule-based checks. LLM outputs are always validated before surfacing.
5. **Audit everything:** Every control decision, inference call, and reconciliation event must be logged via `audit-service`.

## Branching Strategy

- `main` → production only, protected, requires PR
- `develop` → integration branch, all features merge here
- `feature/*` → individual feature branches
- `release/*` → release preparation
- `hotfix/*` → emergency production fixes from `main`

## Running Locally

```bash
make install    # Install Python dependencies
make dev        # Start all services via docker compose
make test       # Run full test suite
make lint       # Run ruff + mypy
```

## Environment Variables

Copy `.env.example` to `.env` and fill in:
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `OPENAI_API_KEY` — OpenAI API key
- `ANTHROPIC_API_KEY` — Anthropic API key
- `JWT_SECRET` — JWT signing secret

## Important Notes for Claude Code

- When adding a new service, follow the existing service structure exactly.
- When modifying `shared/schemas/`, check all services that import those schemas.
- Domain pack prompts in `domain-packs/*/prompts/` are version-controlled — treat them as code.
- Never hardcode secrets. Always use environment variables.
- All new endpoints must have corresponding tests in `tests/api/`.
