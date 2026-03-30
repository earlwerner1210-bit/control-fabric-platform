"""
Release Governance Pack — Seed Data

Creates a complete, realistic release governance scenario:
  - A SOC2-regulated SaaS platform with 3 environments
  - 4 release policies (prod, staging, hotfix, rollback)
  - 6 compliance requirements (SOC2, change management)
  - 3 risk controls (deployment risk, rollback coverage, blast radius)
  - 4 release objects (2 governed, 2 intentionally ungoverned — for demo)
  - Evidence objects linking to CI/CD artefacts

Designed for: demo walkthroughs, counsel meetings, investor demos.
Reset with: python -m app.domain_packs.release_governance.seed_data
"""

from __future__ import annotations

import json

from app.core.domain_pack_loader import DomainPackLoader
from app.core.graph.domain_types import ControlEdge, ControlObjectState, RelationshipType
from app.core.graph.store import ControlGraphStore
from app.core.ingress.domain_types import ArtefactFormat, RawArtefact
from app.core.ingress.pipeline import IngestPipeline
from app.core.platform_action_release_gate import PlatformActionReleaseGate
from app.core.reconciliation.cross_plane_engine import CrossPlaneReconciliationEngine
from app.core.registry.object_registry import ObjectRegistry
from app.core.registry.schema_registry import SchemaRegistry
from app.domain_packs.release_governance.pack import RELEASE_GOVERNANCE_PACK


def build_demo_platform() -> dict:
    """
    Build the complete seeded demo platform.
    Returns all platform components for use in demos and tests.
    """
    schema_registry = SchemaRegistry()
    registry = ObjectRegistry(schema_registry=schema_registry)
    graph = ControlGraphStore()
    gate = PlatformActionReleaseGate()
    pipeline = IngestPipeline(registry=registry, graph=graph, release_gate=gate)
    loader = DomainPackLoader(schema_registry=schema_registry)
    loader.load(RELEASE_GOVERNANCE_PACK)

    ingested = {}

    def ingest(name: str, obj_type: str, plane: str, extra: dict | None = None) -> object:
        data = {"name": name, "object_type": obj_type, **(extra or {})}
        result = pipeline.ingest(
            RawArtefact(
                source_system="release-governance-seed",
                format=ArtefactFormat.JSON,
                raw_content=json.dumps(data),
                submitted_by="seed-script",
            ),
            operational_plane=plane,
        )
        obj = result.ingested_objects[0]
        registry.transition_state(
            obj.object_id,
            ControlObjectState.ACTIVE,
            transitioned_by="seed-script",
            reason="demo activation",
            release_gate=gate,
        )
        activated = registry.get(obj.object_id)
        graph.update_object(activated)
        ingested[name] = activated
        return activated

    def link(
        source_name: str,
        target_name: str,
        rel: RelationshipType,
        evidence: list | None = None,
    ) -> None:
        src = ingested[source_name]
        tgt = ingested[target_name]
        edge = ControlEdge(
            source_object_id=src.object_id,
            target_object_id=tgt.object_id,
            relationship_type=rel,
            asserted_by="seed-script",
            evidence_references=evidence or [],
        )
        graph.add_governed_edge(edge, asserted_by="seed-script", release_gate=gate)

    # Compliance requirements
    ingest(
        "SOC2 CC6.1 — Change Management",
        "compliance_requirement",
        "compliance",
        {
            "description": (
                "All production changes require documented approval and evidence of testing."
            )
        },
    )
    ingest(
        "SOC2 CC7.2 — System Monitoring",
        "compliance_requirement",
        "compliance",
        {"description": ("Changes to production must be monitored and anomalies detected.")},
    )
    ingest(
        "SOC2 CC8.1 — Change Management Controls",
        "compliance_requirement",
        "compliance",
        {"description": ("Change management controls must prevent unauthorised changes.")},
    )

    # Regulatory mandate
    ingest(
        "SOC2 Type II Mandate",
        "regulatory_mandate",
        "compliance",
        {"description": ("SOC2 Type II certification requires demonstrable change control.")},
    )

    # Risk controls
    ingest(
        "Deployment Risk Control",
        "risk_control",
        "risk",
        {"description": "Controls reducing risk of failed production deployments."},
    )
    ingest(
        "Rollback Coverage Control",
        "risk_control",
        "risk",
        {"description": "Every release must have a documented rollback procedure."},
    )
    ingest(
        "Blast Radius Control",
        "risk_control",
        "risk",
        {"description": ("High-blast-radius releases require additional approval steps.")},
    )

    # Release policies
    ingest(
        "Production Release Policy",
        "operational_policy",
        "operations",
        {
            "description": (
                "Governs all production environment releases. "
                "Requires 2 approvers, passing CI, security scan."
            )
        },
    )
    ingest(
        "Staging Release Policy",
        "operational_policy",
        "operations",
        {"description": ("Governs staging environment releases. Requires 1 approver, passing CI.")},
    )
    ingest(
        "Hotfix Release Policy",
        "operational_policy",
        "operations",
        {
            "description": (
                "Emergency hotfix policy. Requires CISO sign-off and post-release review."
            )
        },
    )

    # Link policies to compliance
    link(
        "Production Release Policy",
        "SOC2 CC6.1 — Change Management",
        RelationshipType.IMPLEMENTS,
    )
    link(
        "Production Release Policy",
        "SOC2 CC8.1 — Change Management Controls",
        RelationshipType.IMPLEMENTS,
    )
    link(
        "Staging Release Policy",
        "SOC2 CC6.1 — Change Management",
        RelationshipType.IMPLEMENTS,
    )
    link(
        "Hotfix Release Policy",
        "SOC2 CC6.1 — Change Management",
        RelationshipType.IMPLEMENTS,
    )

    # Link compliance to mandate
    link(
        "SOC2 CC6.1 — Change Management",
        "SOC2 Type II Mandate",
        RelationshipType.SATISFIES,
    )
    link(
        "SOC2 CC8.1 — Change Management Controls",
        "SOC2 Type II Mandate",
        RelationshipType.SATISFIES,
    )

    # GOVERNED releases — these will pass reconciliation
    ingest(
        "API Gateway v2.4.1 — Production Release",
        "domain_pack_extension",
        "operations",
        {
            "description": "Governed production release with full evidence chain.",
            "release_type": "standard",
            "target_environment": "production",
            "risk_tier": "high",
        },
    )
    ingest(
        "Auth Service v1.9.0 — Staging Release",
        "domain_pack_extension",
        "operations",
        {
            "description": "Governed staging release with CI evidence.",
            "release_type": "standard",
            "target_environment": "staging",
            "risk_tier": "medium",
        },
    )

    # Link governed releases to policies
    link(
        "API Gateway v2.4.1 — Production Release",
        "Production Release Policy",
        RelationshipType.SATISFIES,
    )
    link(
        "Auth Service v1.9.0 — Staging Release",
        "Staging Release Policy",
        RelationshipType.SATISFIES,
    )

    # UNGOVERNED releases — intentionally missing policy links for demo gap detection
    ingest(
        "Payment Service v3.1.0 — Production Release",
        "domain_pack_extension",
        "operations",
        {
            "description": ("UNGOVERNED: missing policy link. Will trigger CRITICAL gap case."),
            "release_type": "standard",
            "target_environment": "production",
            "risk_tier": "critical",
        },
    )
    ingest(
        "Database Migration 2026-Q1 — Production",
        "domain_pack_extension",
        "operations",
        {
            "description": ("UNGOVERNED: no policy, no evidence. Maximum risk demo case."),
            "release_type": "migration",
            "target_environment": "production",
            "risk_tier": "critical",
        },
    )

    return {
        "registry": registry,
        "graph": graph,
        "gate": gate,
        "pipeline": pipeline,
        "loader": loader,
        "ingested": ingested,
    }


def run_demo_reconciliation(platform: dict) -> list:
    """Run reconciliation and return cases for demo."""
    engine = CrossPlaneReconciliationEngine(graph=platform["graph"])
    return engine.run_full_reconciliation()


if __name__ == "__main__":
    print("\nBuilding Release Governance demo platform...")
    platform = build_demo_platform()
    cases = run_demo_reconciliation(platform)

    print(f"\nObjects ingested: {platform['registry'].object_count}")
    print(f"Graph nodes: {platform['graph'].node_count}")
    print(f"Graph edges: {platform['graph'].edge_count}")
    print(f"Gate submissions: {platform['gate'].total_submitted}")
    print(f"\nReconciliation cases: {len(cases)}")
    for c in cases:
        print(f"  [{c.severity.value.upper()}] {c.case_type.value}: {c.title}")
    print("\nDemo platform ready.")
