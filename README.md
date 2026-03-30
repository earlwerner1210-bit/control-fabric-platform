# Control Fabric Platform

A modular, domain-extensible control fabric platform for **telecom margin assurance**, **contract intelligence**, and **operational control**. It provides a structured pipeline from document ingestion through entity resolution, control compilation, reconciliation, and inference -- producing auditable, deterministic outputs across multiple domain packs.

## What This Is

The Control Fabric Platform is a control-native decision platform
with policy-bounded model-assisted reasoning.

It is NOT an AI platform. The AI is a subordinate utility.
The control fabric is the product.

Every output — human, automated, or AI-generated — passes through
the same deterministic validation chain and evidence-gated release
before it can affect platform state.

Core principle: cannot violate, not will not violate.

## Architecture

```
                         +------------------+
                         |   Operator UI    |  :3000
                         |   Admin Console  |  :3001
                         +--------+---------+
                                  |
                         +--------v---------+
                         |   API Gateway    |  :8000  (FastAPI)
                         +--------+---------+
                                  |
            +----------+----------+----------+----------+
            |          |          |          |          |
     +------v--+ +----v----+ +--v------+ +-v-------+ +v--------+
     | Ingest  | | Compile | | Retrieve| |Validate | |Inference|
     | Service | | Service | | Service | |Service  | |Gateway  |
     +---------+ +---------+ +---------+ +---------+ +---------+
            |          |          |          |          |
            +----------+----------+----------+----------+
                                  |
                    +-------------+-------------+
                    |             |             |
              +-----v----+ +-----v----+ +------v-----+
              | PostgreSQL| |  Redis   | |  Temporal  |
              | + pgvector| |          | |            |
              +----------+ +----------+ +------------+
                    :5432       :6379        :7233

     Domain Packs:
     +-------------------+  +-------------------+  +------------------+
     | contract-margin   |  | utilities-field   |  | telco-ops        |
     | - Clause parsing  |  | - Readiness rules |  | - Escalation     |
     | - Billability     |  | - Permit checks   |  | - Dispatch       |
     | - Leakage detect  |  | - Skill matching  |  | - Reconciliation |
     +-------------------+  +-------------------+  +------------------+
```

## Quick Start

```bash
# 1. Clone and bootstrap
git clone <repo-url> && cd control-fabric-platform
./scripts/bootstrap.sh

# 2. Start all services
make dev

# 3. Run the test suite
make test
```

The API will be available at `http://localhost:8000/docs`.

## Full Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose v2
- Node.js 20+ (for frontend apps)

### Step-by-step

```bash
# Install Python dependencies
make install

# Copy and edit environment variables
cp .env.example .env
# Edit .env with your API keys

# Start infrastructure (Postgres, Redis, Temporal)
docker compose up -d postgres redis temporal temporal-ui

# Run database migrations
make migrate

# Seed sample data
make seed

# Start the API in dev mode
make dev
```

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection (asyncpg driver) | `postgresql+asyncpg://postgres:postgres@localhost:5432/control_fabric` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `OPENAI_API_KEY` | OpenAI API key | -- |
| `ANTHROPIC_API_KEY` | Anthropic API key | -- |
| `JWT_SECRET` | JWT signing secret | `change-me-in-production` |
| `TEMPORAL_HOST` | Temporal server address | `localhost:7233` |
| `ENVIRONMENT` | Runtime environment | `dev` |

## Services

| Service | Port | Description |
|---|---|---|
| **API Gateway** | 8000 | FastAPI REST API -- routes, auth, cases, documents |
| **Operator UI** | 3000 | Next.js operator dashboard |
| **Admin Console** | 3001 | Next.js admin interface |
| **Temporal UI** | 8088 | Temporal workflow dashboard |
| **PostgreSQL** | 5432 | Primary database with pgvector extension |
| **Redis** | 6379 | Caching, sessions, task queues |
| **Temporal** | 7233 | Workflow orchestration engine |

### Internal Services

| Service | Description |
|---|---|
| `auth-service` | Identity, JWT tokens, RBAC |
| `ingest-service` | File upload, OCR, document parsing pipeline |
| `chunking-service` | Document chunking and metadata enrichment |
| `embedding-service` | Vector embedding generation |
| `retrieval-service` | Vector + keyword + hybrid retrieval |
| `canonicalization-service` | Entity resolution and canonical naming |
| `compiler-service` | Control object compiler (contracts, work orders, incidents) |
| `reconciler-service` | Cross-plane linking and reconciliation |
| `inference-gateway` | LLM provider abstraction (OpenAI, Anthropic, vLLM) |
| `validator-service` | Deterministic rule-based validation engine |
| `audit-service` | Audit trail and event logging |
| `eval-service` | Gold tests, metrics, regression checks |
| `notification-service` | Alerts, email, webhook notifications |
| `reporting-service` | Summary reports and dashboards |

## API Reference

### Auth

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Authenticate and get JWT token |
| POST | `/api/v1/auth/register` | Register a new user |
| GET | `/api/v1/auth/me` | Get current user info |

### Documents

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/documents/upload` | Upload a document |
| POST | `/api/v1/documents/{id}/parse` | Trigger document parsing |
| POST | `/api/v1/documents/{id}/embed` | Trigger embedding generation |
| GET | `/api/v1/documents/{id}` | Get document by ID |
| GET | `/api/v1/documents` | List documents (paginated) |

### Cases (Workflows)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/cases/contract-compile` | Start contract compile workflow |
| POST | `/api/v1/cases/work-order-readiness` | Start readiness check workflow |
| POST | `/api/v1/cases/incident-dispatch-reconcile` | Start incident dispatch workflow |
| POST | `/api/v1/cases/margin-diagnosis` | Start margin diagnosis workflow |
| GET | `/api/v1/cases/{id}` | Get case by ID |
| GET | `/api/v1/cases/{id}/audit` | Get case audit trail |
| GET | `/api/v1/cases/{id}/validations` | Get case validation results |
| GET | `/api/v1/cases` | List cases (paginated, filterable) |

### Compile

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/contracts/{id}/compile` | Compile a contract into control objects |
| POST | `/api/v1/work-orders/{id}/compile` | Compile a work order |
| POST | `/api/v1/incidents/{id}/compile` | Compile an incident |

### Admin

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/admin/prompts` | List prompt templates |
| PUT | `/api/v1/admin/prompts/{id}` | Update a prompt template |
| GET | `/api/v1/admin/domain-packs` | List domain packs |
| GET | `/api/v1/admin/model-runs` | List model inference runs |

### Evals

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/evals/run` | Trigger an evaluation run |
| GET | `/api/v1/evals/{run_id}` | Get evaluation results |

### Infrastructure

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe (checks DB) |
| GET | `/metrics` | Basic runtime metrics |

## Testing

```bash
make test              # Full test suite with coverage
make test-unit         # Unit tests only
make test-api          # API integration tests
make test-workflows    # Workflow orchestration tests
make test-regression   # Eval case regression tests
```

Test structure:

```
tests/
  conftest.py           # Shared fixtures, test app, mock DB
  unit/
    test_contract_parser.py     # Contract parsing logic
    test_billability_rules.py   # Billability rule engine
    test_readiness_rules.py     # Work order readiness rules
    test_escalation_rules.py    # Incident escalation rules
    test_leakage_rules.py       # Margin leakage detection
    test_validator_service.py   # Deterministic validator
    test_inference_gateway.py   # LLM gateway + FakeProvider
  api/
    test_documents_api.py       # Document upload, parse, embed
    test_cases_api.py           # Case CRUD and audit trails
    test_auth_api.py            # Authentication endpoints
  workflows/
    test_contract_compile.py    # Contract compile workflow E2E
    test_work_order_readiness.py # Readiness workflow E2E
    test_incident_dispatch.py   # Incident dispatch workflow E2E
    test_margin_diagnosis.py    # Margin diagnosis workflow E2E
  regression/
    test_eval_cases.py          # Domain pack eval case regression
```

## Domain Packs

Domain packs are self-contained bundles of domain-specific logic. Each pack contains:

```
domain-packs/<pack-name>/
  parsers/       # Document parsing logic
  rules/         # Deterministic rule engines
  schemas/       # Pydantic models for domain objects
  taxonomy/      # Classification enums and hierarchies
  prompts/       # LLM prompt templates (version-controlled)
  evals/         # Gold test cases for regression testing
  templates/     # Report and output templates
```

| Pack | Domain | Key Capabilities |
|---|---|---|
| `contract-margin` | Contract intelligence | Clause extraction, billability rules, leakage detection, penalty tracking |
| `utilities-field` | Field operations | Work order readiness, permit validation, skill matching, material checks |
| `telco-ops` | Telecom operations | Incident escalation, dispatch rules, SLA monitoring, runbook execution |

Adding a new domain is as simple as creating a new directory under `domain-packs/` with the standard structure.

## Contributing

1. Create a feature branch from `develop`: `git checkout -b feature/my-feature develop`
2. Follow the existing service structure in `services/`
3. Add tests for all new functionality
4. Run `make lint` and `make test` before pushing
5. Open a PR against `develop`

### Key Conventions

- **Shared types** live in `shared/schemas/` -- never duplicate definitions
- **Domain packs** are self-contained -- adding a new domain = adding a new directory
- **Deterministic first** -- rule-based validation runs before any LLM output is surfaced
- **Audit everything** -- every control decision, inference call, and reconciliation event is logged
- **Never hardcode secrets** -- always use environment variables

## License

Proprietary -- Prodapt / Earl Werner. All rights reserved.
