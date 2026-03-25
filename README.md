# control-fabric-platform

**Control Fabric Platform** is a modular, domain-extensible AI platform for telecom margin assurance, contract intelligence, and operational control. It provides a structured pipeline from document ingestion through entity resolution, control compilation, reconciliation, and inference — producing auditable, deterministic outputs across multiple domain packs.

## Repository Structure

```
control-fabric-platform/
├── apps/                   # User-facing applications (API gateway, UIs, docs portal)
├── services/               # Microservices (auth, ingest, chunking, embedding, retrieval, etc.)
├── workflows/              # Orchestrated multi-service workflows
├── domain-packs/           # Domain-specific taxonomy, parsers, rules, prompts, schemas
├── shared/                 # Shared schemas, entities, telemetry, DB helpers
├── infra/                  # Terraform, Kubernetes, Docker, monitoring
├── data/                   # Sample contracts, work orders, incidents, seed data
├── tests/                  # Unit, integration, workflow, API, regression tests
├── scripts/                # Bootstrap, seed, backfill, eval scripts
└── .github/workflows/      # CI/CD pipelines
```

## Branching Strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready code only. Protected. Requires PR + review. |
| `develop` | Integration branch. All feature branches merge here first. |
| `feature/*` | Individual feature development (e.g. `feature/ingest-service-ocr`) |
| `release/*` | Release preparation branches (e.g. `release/v1.0.0`) |
| `hotfix/*` | Emergency production fixes branched from `main` |

## Domain Packs

| Pack | Description |
|---|---|
| `contract-margin` | Contract intelligence, margin calculation, leakage detection |
| `utilities-field` | Field operations, work order readiness, asset reconciliation |
| `telco-ops` | Telecom operations, incident dispatch, service assurance |

## Getting Started

```bash
# Bootstrap the environment
./scripts/bootstrap.sh

# Seed sample data
python scripts/seed_data.py

# Run the full eval suite
python scripts/run_eval_suite.py
```

## Services

| Service | Description |
|---|---|
| `auth-service` | Identity, tokens, RBAC |
| `ingest-service` | File upload, OCR, parsing pipeline |
| `chunking-service` | Chunking and metadata enrichment |
| `embedding-service` | Embeddings generation |
| `retrieval-service` | Vector + keyword + hybrid retrieval |
| `canonicalization-service` | Entity resolution and canonical names |
| `compiler-service` | Control-object compiler |
| `reconciler-service` | Cross-plane linking and reconciliation |
| `inference-gateway` | vLLM / MLX / cloud-model abstraction |
| `validator-service` | Deterministic rule engine |
| `audit-service` | Audit trails and event logging |
| `notification-service` | Alerts, email, workflow notifications |
| `eval-service` | Gold tests, metrics, regression checks |
| `reporting-service` | Summary reports and dashboards |

## License

Proprietary — Prodapt / Earl Werner. All rights reserved.
