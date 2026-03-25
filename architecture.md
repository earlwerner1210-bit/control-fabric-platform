# Architecture

## Overview

Control Fabric Platform is built as a layered, event-driven microservices architecture. Each layer has a defined responsibility and communicates through well-typed interfaces.

```
┌─────────────────────────────────────────────────────────────────┐
│  apps/                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │  operator-ui │  │ admin-console│  │    docs-site       │    │
│  └──────┬───────┘  └──────┬───────┘  └────────────────────┘    │
│         └────────────┬────┘                                     │
│                ┌─────▼──────┐                                   │
│                │  api (GW)  │                                   │
│                └─────┬──────┘                                   │
└──────────────────────┼──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│  services/                                                      │
│  ingest → chunking → embedding → retrieval                      │
│  canonicalization → compiler → reconciler                       │
│  inference-gateway → validator → audit                          │
│  auth | notification | eval | reporting                         │
└─────────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│  domain-packs/                                                  │
│  contract-margin | utilities-field | telco-ops                  │
└─────────────────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│  shared/                                                        │
│  schemas | entities | templates | policy | telemetry | db       │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Principles

1. **Domain-pack extensibility** — new domains are added as self-contained packs without modifying core services.
2. **Deterministic outputs** — the validator-service enforces rule-based checks before any output is surfaced.
3. **Auditability** — every inference, reconciliation, and control decision is logged via audit-service.
4. **Multi-model inference** — inference-gateway abstracts vLLM, MLX, and cloud models behind a single interface.
5. **Separation of concerns** — ingest, chunking, embedding, and retrieval are independent, replaceable services.

## Data Flow

```
Document Upload
    → ingest-service (OCR, parse)
    → chunking-service (chunk + metadata)
    → embedding-service (vectors)
    → retrieval-service (index)
    → canonicalization-service (entity resolution)
    → compiler-service (control objects)
    → reconciler-service (cross-plane links)
    → inference-gateway (LLM reasoning)
    → validator-service (deterministic checks)
    → audit-service (log)
    → reporting-service (output)
```
