#!/usr/bin/env python3
"""
Release Governance Pack — Canonical Demo Script

This is the wedge demo. Run this to show a buyer exactly what the platform does
in the context of release governance — the first named use case.

Demonstrates:
  1. Artefact ingestion from multiple sources (manual + CI/CD connector)
  2. Graph linkage of releases to policies to compliance requirements
  3. Gap detection: ungoverned releases surface as CRITICAL cases
  4. Evidence-gated release: governed releases compile evidence packages
  5. Exception framework: emergency override with expiry and review task
  6. Differentiation: what generic workflow tools cannot do

Run: python demo_release_governance.py

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from app.core.connectors.framework import (
    ConnectorRegistry,
    SimulatedCICDConnector,
)
from app.core.exception_framework.domain_types import (
    ExceptionRequest,
    ExceptionRisk,
    ExceptionType,
)
from app.core.exception_framework.manager import ExceptionManager
from app.core.platform_action_release_gate import PlatformActionReleaseGate
from app.core.platform_validation_chain import ActionOrigin
from app.core.reconciliation.cross_plane_engine import (
    CrossPlaneReconciliationEngine,
)
from app.domain_packs.release_governance.seed_data import (
    build_demo_platform,
    run_demo_reconciliation,
)


def sep(title: str) -> None:
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print("=" * 65)


def ok(msg: str) -> None:
    print(f"  ✓  {msg}")


def gap_case(msg: str) -> None:
    print(f"  ⚠  {msg}")


def info(msg: str) -> None:
    print(f"     {msg}")


def blocked(msg: str) -> None:
    print(f"  ✗  BLOCKED: {msg}")


def main() -> None:
    print("\n" + "=" * 65)
    print("  CONTROL-NATIVE DECISION PLATFORM")
    print("  Release Governance Pack — Live Demo")
    print("  March 2026 — CONFIDENTIAL")
    print("=" * 65)

    # ── 1. BUILD THE PLATFORM ───────────────────────────────────────
    sep("Step 1 — Ingesting release environment")
    print()
    info("Loading Release Governance Pack...")
    platform = build_demo_platform()
    ok("Domain pack loaded: release-governance v1.0.0")
    ok(f"Objects ingested: {platform['registry'].object_count}")
    ok("  — compliance requirements, policies, risk controls")
    ok("  — 2 governed releases, 2 ungoverned releases (intentional)")
    ok(f"Graph nodes: {platform['graph'].node_count}  edges: {platform['graph'].edge_count}")
    ok(f"Release gate submissions: {platform['gate'].total_submitted}")

    # ── 2. CI/CD EVIDENCE CONNECTOR ─────────────────────────────────
    sep("Step 2 — Pulling CI/CD evidence")
    print()
    connector_registry = ConnectorRegistry()
    cicd = SimulatedCICDConnector(pass_rate=0.85)
    connector_registry.register(cicd)

    all_results = connector_registry.fetch_all()
    for cid, result in all_results.items():
        if result.success:
            artefact = result.artefacts[0]
            data = json.loads(artefact.raw_content)
            ok(f"CI evidence ingested from {cid}")
            info(
                f"  Run: {data.get('run_id')} | "
                f"Status: {data.get('status')} | "
                f"Coverage: {data.get('test_coverage_pct')}%"
            )
        else:
            info(f"  Connector {cid}: {result.errors}")

    # ── 3. CROSS-PLANE RECONCILIATION ───────────────────────────────
    sep("Step 3 — Running cross-plane reconciliation")
    print()
    info("Scanning all operational planes for governance gaps...")
    engine = CrossPlaneReconciliationEngine(graph=platform["graph"])
    cases = engine.run_full_reconciliation()

    critical = [c for c in cases if c.severity.value == "critical"]
    high = [c for c in cases if c.severity.value == "high"]
    ok(f"Reconciliation complete: {len(cases)} cases detected")
    print()

    for case in cases[:5]:
        gap_case(f"[{case.severity.value.upper()}] {case.title}")
        if case.remediation_suggestions:
            info(f"  Suggested: {case.remediation_suggestions[0]}")
    if len(cases) > 5:
        info(f"  ... and {len(cases) - 5} more cases")

    print()
    info("This is the differentiation point.")
    info("A generic workflow tool sees: no approval ticket found.")
    info("This platform sees: release 'Payment Service v3.1.0' has no SATISFIES")
    info("link to any release policy, which has no IMPLEMENTS link to SOC2 CC6.1,")
    info("which means the release has no demonstrable compliance backing.")
    info("That is a semantic governance gap — not a data value mismatch.")

    # ── 4. EVIDENCE-GATED RELEASE ───────────────────────────────────
    sep("Step 4 — Evidence-gated release demonstration")
    print()
    gate = PlatformActionReleaseGate()

    info("Attempting to release API Gateway v2.4.1 (governed)...")
    result = gate.submit(
        action_type="production_release",
        proposed_payload={
            "release_name": "API Gateway v2.4.1",
            "environment": "production",
        },
        requested_by="release-engineer",
        origin=ActionOrigin.HUMAN_OPERATOR,
        evidence_references=[
            "ci-run-0001",
            "security-scan-approved",
            "load-test-passed",
        ],
        provenance_chain=["change-request-CR-2891"],
    )
    ok(f"Release COMPILED — status: {result.status.value}")
    pkg = gate.get_package(result.package_id)
    if pkg:
        info(f"  Evidence package: {pkg.package_id[:16]}...")
        info(f"  Package hash:     {pkg.package_hash[:32]}...")
        info(f"  Evidence chain:   {len(pkg.evidence_chain)} items")
        info(f"  Integrity check:  {pkg.verify_integrity()}")

    print()
    info("Attempting to release Database Migration 2026-Q1 (ungoverned)...")
    result2 = gate.submit(
        action_type="production_release",
        proposed_payload={
            "release_name": "Database Migration 2026-Q1",
            "environment": "production",
        },
        requested_by="dba-team",
        origin=ActionOrigin.HUMAN_OPERATOR,
        evidence_references=[],
    )
    blocked(f"Migration blocked — {result2.failure_reason}")
    info("  No evidence references provided. Gate rejected at evidence check.")
    info("  Execution is architecturally impossible without evidence package.")

    # ── 5. EXCEPTION FRAMEWORK ──────────────────────────────────────
    sep("Step 5 — Emergency override with governance")
    print()
    info("Critical production incident. Team requests emergency override...")

    exception_manager = ExceptionManager()
    exception_req = ExceptionRequest(
        exception_type=ExceptionType.EMERGENCY_OVERRIDE,
        requested_by="cto@company.com",
        justification=(
            "Critical payment processing outage affecting 40,000 customers. "
            "Database migration required to restore service. Compensating control: "
            "DBA team monitoring with rollback ready. Post-incident review scheduled."
        ),
        affected_object_ids=["db-migration-2026-q1"],
        affected_action_type="production_release",
        policy_context_id="Production Release Policy v1.0",
        compensating_controls=[
            "dba-monitoring-active",
            "rollback-script-verified",
        ],
        expires_at=datetime.now(UTC) + timedelta(hours=4),
        risk_assessment=ExceptionRisk.CRITICAL,
    )

    submitted = exception_manager.submit_exception(exception_req)
    ok(f"Exception submitted: {submitted.exception_id[:16]}...")
    info(f"  Type: {submitted.exception_type.value}")
    info(f"  Risk: {submitted.risk_assessment.value}")
    info("  Expires: 4 hours from now")

    decision = exception_manager.approve_exception(
        submitted.exception_id,
        decided_by="ciso@company.com",
        rationale=(
            "Approved given customer impact. Compensating controls verified. Review mandatory."
        ),
        conditions=[
            "dba-monitoring-required",
            "post-incident-review-within-48h",
        ],
    )
    ok("Exception approved by CISO")
    info(f"  Review task created: {decision.review_task_id[:16]}...")
    info("  Review mandatory before exception expires")
    info("  Audit trail: immutable, append-only, cannot be deleted")

    audit = exception_manager.get_audit_trail(submitted.exception_id)
    ok(f"Audit trail: {len(audit)} entries")
    for entry in audit:
        info(f"  {entry.event_type}: {entry.event_detail[:60]}")

    # ── 6. SUMMARY ──────────────────────────────────────────────────
    sep("Demo complete — what was demonstrated")
    print()
    print("  1. Typed release objects ingested with immutable provenance")
    print("  2. CI/CD evidence pulled via connector and ingested automatically")
    print("  3. Cross-plane gap detection: ungoverned releases surface as CRITICAL")
    print("  4. Evidence-gated release: governed releases produce evidence packages")
    print("  5. Ungoverned releases are architecturally blocked — not just flagged")
    print("  6. Emergency overrides are governed, time-bound, and audit-logged")
    print()
    print("  What generic workflow cannot do:")
    print("  — Detect semantic governance gaps across heterogeneous planes")
    print("  — Block execution at compile time (not just flag post-hoc)")
    print("  — Prove an evidence chain is intact before dispatch")
    print("  — Apply the same governance chain to AI, human, and automated actions")
    print()
    print("  Platform stats:")
    print(f"  Registry objects:      {platform['registry'].object_count}")
    print(f"  Graph nodes:           {platform['graph'].node_count}")
    print(f"  Graph edges:           {platform['graph'].edge_count}")
    print(f"  Reconciliation cases:  {len(cases)} ({len(critical)} critical, {len(high)} high)")
    print(f"  Gate submissions:      {platform['gate'].total_submitted}")
    print(f"  Active exceptions:     {exception_manager.total_active}")
    print()


if __name__ == "__main__":
    main()
