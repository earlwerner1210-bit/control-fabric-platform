# Eval Fixtures — Control Fabric Platform

This directory contains evaluation fixtures for testing margin assurance, contract intelligence, and operational control scenarios. Each fixture is a self-contained JSON file representing a realistic SPEN/Vodafone domain scenario.

## Fixtures

| Fixture | Description |
|---------|-------------|
| `wave1_contract_margin.json` | Complete contract-to-margin scenario for SPEN HV switching work with billability and daywork sheet validation. |
| `wave1_margin_leakage.json` | Multiple margin leakage patterns across SPEN managed services: rate mismatches, abortive visits, missing change orders. |
| `wave1_penalty_scenario.json` | Multiple SLA breaches in one month hitting the 30% penalty cap, testing penalty accumulation and capping logic. |
| `wave1_scope_boundary_conflict.json` | Work orders with mixed in-scope and out-of-scope activities, testing scope conflict detection and conditional billability. |
| `wave1_spen_emergency_callout.json` | SPEN emergency HV switching callout with overtime/weekend multipliers, mobilisation charges, and billing gate enforcement. |
| `wave1_vodafone_p1_major_incident.json` | Vodafone P1 major incident with SLA breach, NOC/SOC escalation chain, service credits, and RCA penalty. |
| `wave1_reattendance_billing.json` | Provider-fault (non-billable) and customer-fault (billable) reattendance scenarios with evidence requirements. |
| `wave1_rate_card_expiry.json` | Expired and active rate cards side by side, testing expired rate detection, underbilling leakage, and resubmission recovery. |
| `wave1_cross_pack_full_chain.json` | Full evidence chain (contract, work order, field execution, billing) validated by the MarginDiagnosisReconciler across all 4 stages. |
| `wave1_subcontractor_margin.json` | Subcontractor pass-through with rates exceeding contracted rates, negative margin detection, and unapproved subcontractor breach. |

## Fixture Structure

Each fixture follows a consistent structure:

- **`scenario`** — Unique scenario identifier
- **`description`** — Human-readable description of what the fixture tests
- **`domain`** — Domain pack reference (contract-margin, utilities-field, telco-ops)
- **`contract`** — Contract metadata with clauses, SLA table, and rate card
- **`work_orders`** — Array of work orders with activities, billing, and completion evidence
- **`incidents`** — Related incidents (where applicable)
- **`expected_outcomes`** — Expected billability decisions, leakage triggers, and reconciliation results

## Usage

Fixtures are consumed by the test suite in `tests/` and by eval scripts in `scripts/`. To run evaluations against all fixtures:

```bash
make test-fixtures
```
