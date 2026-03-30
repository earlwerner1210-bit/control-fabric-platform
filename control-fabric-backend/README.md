# Control Fabric Backend

AI-powered telecom margin assurance, contract intelligence, and operational control platform.

## Tech Stack

- **Runtime:** Python 3.12, FastAPI, Uvicorn
- **ORM / DB:** SQLAlchemy 2 (async), PostgreSQL 16 + pgvector
- **Orchestration:** Temporal (durable workflows)
- **Cache / Queues:** Redis 7
- **AI / Inference:** OpenAI, vLLM, MLX (pluggable via inference gateway)
- **Observability:** structlog, OpenTelemetry, Prometheus

## Quick Start

```bash
# 1. Install Python dependencies
make install

# 2. Copy environment variables
cp .env.example .env

# 3. Start all services (Postgres, Redis, Temporal, API, Worker)
make dev

# 4. Run the test suite
make test
```

The API will be available at `http://localhost:8000`. Temporal UI runs at `http://localhost:8088`.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        FastAPI Gateway                           │
│   /health  /documents  /workflows  /controls  /audit  /eval     │
├──────────────┬───────────────┬───────────────┬───────────────────┤
│  Ingest      │  Compiler     │  Validator    │  Reconciler       │
│  Service     │  Service      │  Service      │  Service          │
├──────────────┴───────────────┴───────────────┴───────────────────┤
│                      Temporal Workers                            │
│   contract_compile  ·  margin_diagnosis  ·  field_readiness      │
├──────────────────────────────────────────────────────────────────┤
│                       Domain Packs                               │
│   contract-margin  ·  utilities-field  ·  telco-ops              │
├──────────────────────────────────────────────────────────────────┤
│                     Shared Infrastructure                        │
│   Schemas  ·  Entities  ·  DB  ·  Telemetry  ·  Security        │
├──────────────┬───────────────┬───────────────────────────────────┤
│  PostgreSQL  │     Redis     │          Temporal                 │
│  + pgvector  │               │                                   │
└──────────────┴───────────────┴───────────────────────────────────┘
```

## Domain Packs

Each domain pack is a self-contained module providing rules, prompts, schemas, and evaluation
cases for a specific industry vertical:

| Pack               | Purpose                                              |
|--------------------|------------------------------------------------------|
| `contract-margin`  | Contract parsing, billability, leakage, penalties     |
| `utilities-field`  | Field ops readiness, dispatch, crew qualification     |
| `telco-ops`        | Incident management, SLA compliance, escalation       |

Adding a new domain = adding a new pack directory under `app/domain_packs/`.

## API Routes

| Method | Path                          | Description                        |
|--------|-------------------------------|------------------------------------|
| GET    | `/health`                     | Liveness probe                     |
| GET    | `/ready`                      | Readiness probe                    |
| GET    | `/metrics`                    | Prometheus-style metrics snapshot   |
| POST   | `/api/v1/documents/upload`    | Upload a document                  |
| POST   | `/api/v1/documents/{id}/parse`| Parse an uploaded document         |
| GET    | `/api/v1/documents`           | List documents                     |
| POST   | `/api/v1/workflows`           | Start a workflow case              |
| GET    | `/api/v1/workflows/{id}`      | Get workflow case status           |
| GET    | `/api/v1/controls`            | List control objects               |
| POST   | `/api/v1/controls`            | Create a control object            |
| GET    | `/api/v1/audit/{resource_id}` | Audit trail for a resource         |
| POST   | `/api/v1/eval/run`            | Execute an evaluation suite        |
| POST   | `/api/v1/auth/login`          | Authenticate and obtain JWT        |
| GET    | `/api/v1/auth/me`             | Current user profile               |

## Project Layout

```
app/
  api/           FastAPI routers, middleware, dependencies
  core/          Config, security, logging, telemetry, exceptions
  db/            SQLAlchemy base, session, models
  domain_packs/  Domain-specific rules, prompts, schemas
  schemas/       Pydantic v2 request/response schemas
  services/      Business-logic service modules
  workflows/     Temporal workflow definitions
alembic/         Database migrations
data/            Fixtures and seed data
infra/           Docker, scripts, Terraform
temporal_worker/ Temporal worker entrypoint
tests/           Unit, integration, API, workflow, regression tests
```

## Development

```bash
make lint       # Ruff + mypy
make format     # Auto-format with ruff
make test-unit  # Unit tests only
make test-api   # API tests only
make migrate    # Run pending Alembic migrations
make seed       # Seed sample data
```

## Environment Variables

See `.env.example` for the full list. Key variables:

- `DATABASE_URL` -- PostgreSQL async connection string
- `REDIS_URL` -- Redis connection string
- `JWT_SECRET` -- JWT signing secret (change in production!)
- `INFERENCE_PROVIDER` -- `vllm`, `mlx`, or `fake`
- `EMBEDDING_PROVIDER` -- `openai`, `local`, or `fake`
