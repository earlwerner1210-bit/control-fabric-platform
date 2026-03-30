#!/usr/bin/env python3
"""
Control Fabric Platform — Patent Demonstration Script

Runs the full platform pipeline and prints evidence of all 5 patent themes.
Run with: python demo.py

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import json

from app.core.domain_pack_loader import (
    DomainPackLoader,
    build_contract_margin_pack,
    build_telco_ops_pack,
)
from app.core.graph.domain_types import ControlEdge, ControlObjectState, RelationshipType
from app.core.graph.store import ControlGraphStore
from app.core.inference.core.engine import BoundedInferenceEngine
from app.core.inference.models.domain_types import HypothesisType, InferenceRequest
from app.core.ingress.domain_types import ArtefactFormat, RawArtefact
from app.core.ingress.pipeline import IngestPipeline
from app.core.reconciliation.cross_plane_engine import CrossPlaneReconciliationEngine
from app.core.registry.object_registry import ObjectRegistry
from app.core.registry.schema_registry import SchemaRegistry


def separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def info(msg: str) -> None:
    print(f"  → {msg}")


def main() -> None:
    print("\n" + "=" * 60)
    print("  CONTROL FABRIC PLATFORM")
    print("  Patent Demonstration — All 5 Themes")
    print("  March 2026 — CONFIDENTIAL")
    print("=" * 60)

    # ----------------------------------------------------------------
    # Initialise platform
    # ----------------------------------------------------------------
    schema_registry = SchemaRegistry()
    registry = ObjectRegistry(schema_registry=schema_registry)
    graph = ControlGraphStore()
    pipeline = IngestPipeline(registry=registry, graph=graph)
    domain_loader = DomainPackLoader(schema_registry=schema_registry)
    inference_engine = BoundedInferenceEngine(simulation_mode=True)

    # ----------------------------------------------------------------
    # THEME 5: Domain Pack Extensibility
    # ----------------------------------------------------------------
    separator("THEME 5 — Domain Pack Extensibility")
    info("Loading domain packs without modifying core architecture...")

    initial_ns = schema_registry.namespace_count
    domain_loader.load(build_telco_ops_pack())
    domain_loader.load(build_contract_margin_pack())

    ok(f"Loaded {domain_loader.pack_count} domain packs")
    ok(f"Schema namespaces: {initial_ns} (core) → {schema_registry.namespace_count} (with packs)")
    ok(f"Domain pack rules available: {len(domain_loader.get_all_rules())}")
    for pack in domain_loader.get_loaded_packs():
        info(f"  Pack: {pack.name} v{pack.version} — {len(pack.reconciliation_rules)} rules")

    # ----------------------------------------------------------------
    # THEME 1: Control Object Fabric — Artefact Ingestion
    # ----------------------------------------------------------------
    separator("THEME 1 — Control Object Fabric")
    info("Ingesting enterprise artefacts as typed control objects...")

    artefacts = [
        RawArtefact(
            source_system="gdpr-portal",
            format=ArtefactFormat.JSON,
            raw_content=json.dumps(
                {
                    "name": "GDPR Article 25",
                    "description": "Data protection by design regulation mandate",
                    "object_type": "regulatory_mandate",
                }
            ),
            submitted_by="compliance-officer",
        ),
        RawArtefact(
            source_system="security-scanner",
            format=ArtefactFormat.JSON,
            raw_content=json.dumps(
                {
                    "name": "TLS 1.3 Enforcement",
                    "description": "technical control security cipher enforcement",
                    "object_type": "technical_control",
                }
            ),
            submitted_by="security-engineer",
        ),
        RawArtefact(
            source_system="risk-system",
            format=ArtefactFormat.JSON,
            raw_content=json.dumps(
                {
                    "name": "Access Control Policy",
                    "description": "risk control access management",
                    "object_type": "risk_control",
                }
            ),
            submitted_by="risk-analyst",
        ),
        RawArtefact(
            source_system="vuln-scanner",
            format=ArtefactFormat.JSON,
            raw_content=json.dumps(
                {
                    "name": "CVE-2024-0001",
                    "description": "critical vulnerability in authentication module",
                    "object_type": "vulnerability",
                }
            ),
            submitted_by="security-engineer",
        ),
        RawArtefact(
            source_system="compliance-portal",
            format=ArtefactFormat.JSON,
            raw_content=json.dumps(
                {
                    "name": "GDPR Art 32 Requirement",
                    "description": "compliance requirement encryption in transit",
                    "object_type": "compliance_requirement",
                }
            ),
            submitted_by="compliance-officer",
        ),
    ]

    planes = ["compliance", "security", "risk", "risk", "compliance"]
    ingested_objects = []

    for artefact, plane in zip(artefacts, planes):
        result = pipeline.ingest(artefact, plane)
        obj = result.ingested_objects[0]
        ingested_objects.append(obj)
        ok(f"Ingested: '{obj.name}' → {obj.object_type.value} [{plane}]")
        info(f"  Object ID:      {obj.object_id[:16]}...")
        info(f"  Provenance hash: {obj.provenance.source_hash[:32]}...")
        history = registry.get_version_history(obj.object_id)
        info(f"  Version history: {len(history)} record(s) from moment of ingestion")

    ok(f"\nTotal objects in registry: {registry.object_count}")
    ok(f"Total nodes in graph:      {graph.node_count}")

    gdpr_mandate = ingested_objects[0]
    tls_control = ingested_objects[1]
    risk_control = ingested_objects[2]
    vulnerability = ingested_objects[3]
    compliance_req = ingested_objects[4]

    # Activate objects
    for obj in ingested_objects:
        registry.transition_state(
            obj.object_id,
            ControlObjectState.ACTIVE,
            transitioned_by="system",
            reason="demo activation",
        )
        graph.update_object(registry.get(obj.object_id))

    # ----------------------------------------------------------------
    # THEME 2: Control Graph — Typed Relationships + Reconciliation
    # ----------------------------------------------------------------
    separator("THEME 2 — Control Graph & Cross-Plane Reconciliation")
    info("Linking objects with typed semantic relationships...")

    edges_to_add = [
        (
            tls_control,
            compliance_req,
            RelationshipType.SATISFIES,
            "TLS satisfies GDPR Art 32 encryption requirement",
        ),
        (
            compliance_req,
            gdpr_mandate,
            RelationshipType.SATISFIES,
            "GDPR Art 32 requirement satisfies GDPR Article 25 mandate",
        ),
        (
            risk_control,
            vulnerability,
            RelationshipType.MITIGATES,
            "Access control mitigates CVE-2024-0001",
        ),
    ]

    for source, target, rel_type, description in edges_to_add:
        edge = ControlEdge(
            source_object_id=source.object_id,
            target_object_id=target.object_id,
            relationship_type=rel_type,
            asserted_by="compliance-officer",
            evidence_references=["audit-2026"],
        )
        graph.add_edge(edge)
        ok(f"Edge: '{source.name}' -[{rel_type.value}]→ '{target.name}'")
        info(f"  Enforcement weight: {edge.enforcement_weight}")
        info(f"  Edge hash: {edge.edge_hash[:32]}...")

    info("\nCross-plane path detection...")
    path = graph.find_path_between(tls_control.object_id, gdpr_mandate.object_id)
    if path:
        ok(f"Path found: security plane → compliance plane in {path.depth} hops")
        info(f"  Total enforcement weight: {path.total_enforcement_weight}")

    info("\nImpact analysis for compliance requirement...")
    impact = graph.get_impact_analysis(compliance_req.object_id)
    ok(f"Impact analysis: {impact['total_affected_objects']} objects affected")
    info(f"  Downstream: {len(impact['downstream_objects'])} objects")
    info(f"  Upstream:   {len(impact['upstream_objects'])} objects")
    info(f"  Critical relationships: {len(impact['critical_relationships'])}")

    info("\nRunning cross-plane reconciliation...")
    recon_engine = CrossPlaneReconciliationEngine(graph=graph)
    cases = recon_engine.run_full_reconciliation()
    ok(f"Reconciliation complete: {recon_engine.total_cases} cases detected")
    for case in cases[:3]:
        info(f"  [{case.severity.value.upper()}] {case.case_type.value}: {case.title[:60]}...")

    # ----------------------------------------------------------------
    # THEME 3: Bounded Inference — AI Cannot Produce Executable Output
    # ----------------------------------------------------------------
    separator("THEME 3 — Bounded Reasoning Layer")
    info("Submitting inference request through policy gate...")

    request = InferenceRequest(
        requesting_entity_id="compliance-officer",
        target_control_object_ids=[tls_control.object_id, compliance_req.object_id],
        target_operational_plane="compliance",
        hypothesis_type_requested=HypothesisType.COMPLIANCE_MAPPING,
        context_data={
            "control_objects": [
                {
                    "id": tls_control.object_id,
                    "name": tls_control.name,
                    "classification": "internal",
                },
                {
                    "id": compliance_req.object_id,
                    "name": compliance_req.name,
                    "classification": "internal",
                },
            ]
        },
    )

    response = inference_engine.infer(request)
    ok(f"Inference status: {response.status.value}")

    if response.hypothesis:
        ok(f"Hypothesis type: {response.hypothesis.hypothesis_type.value}")
        ok(f"Hypothesis title: {response.hypothesis.title}")
        info(f"  Confidence score:    {response.hypothesis.confidence_score}")
        info(f"  Findings count:      {len(response.hypothesis.findings)}")
        info(f"  Reasoning steps:     {len(response.hypothesis.reasoning_trace)}")
        ok(f"  is_executable:       {response.hypothesis.is_executable}  ← STRUCTURAL GUARANTEE")
        info(f"  Hypothesis hash:     {response.hypothesis.hypothesis_hash[:32]}...")

    if response.policy_gate_result:
        ok(f"Policy gate: {response.policy_gate_result.decision.value.upper()}")
        info(f"  Policy ID:       {response.policy_gate_result.policy_id}")
        info(f"  Gate signature:  {response.policy_gate_result.gate_signature[:32]}...")

    # ----------------------------------------------------------------
    # THEME 4: Evidence-Gated Action — Cryptographic Evidence Chain
    # ----------------------------------------------------------------
    separator("THEME 4 — Evidence-Gated Action & Provenance Chain")
    info("Inspecting cryptographic evidence record...")

    if response.evidence_record:
        ev = response.evidence_record
        ok(f"Evidence record committed: {ev.record_id[:16]}...")
        ok(f"Final status: {ev.final_status.value}")
        info(f"  Session ID:              {ev.session_id[:16]}...")
        info(f"  Request hash:            {ev.request_hash[:32]}...")
        info(f"  Policy gate signature:   {ev.policy_gate_signature[:32]}...")
        info(f"  Scope hash:              {ev.scope_hash[:32]}...")
        if ev.hypothesis_hash:
            info(f"  Hypothesis hash:         {ev.hypothesis_hash[:32]}...")
        info(f"  Chain hash:              {ev.chain_hash[:32]}...")
        info(f"  Inference duration:      {ev.inference_duration_ms}ms")
        ok(f"Chain integrity verified: {inference_engine.evidence_logger.verify_chain_integrity()}")
        ok(f"Total evidence records:   {inference_engine.evidence_logger.record_count}")

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    separator("DEMONSTRATION COMPLETE")
    print()
    print("  Patent Theme Coverage:")
    print("  ✓ Theme 1 — Control Object Fabric (typed objects, provenance, version history)")
    print("  ✓ Theme 2 — Control Graph + Reconciliation (semantic gap/conflict detection)")
    print("  ✓ Theme 3 — Bounded Reasoning (AI subordinated to policy gate + scope enforcer)")
    print("  ✓ Theme 4 — Evidence-Gated Actions (cryptographic evidence chain on every session)")
    print("  ✓ Theme 5 — Fabric-Native Extensibility (domain packs loaded without core changes)")
    print()
    print("  Platform Stats:")
    print(f"  → Registry objects:    {registry.object_count}")
    print(f"  → Graph nodes:         {graph.node_count}")
    print(f"  → Graph edges:         {graph.edge_count}")
    print(f"  → Domain packs loaded: {domain_loader.pack_count}")
    print(f"  → Evidence records:    {inference_engine.evidence_logger.record_count}")
    print(f"  → Reconciliation cases:{recon_engine.total_cases}")
    print()
    print("  Primary patent demonstration test:")
    print(
        "  → tests/integration/test_full_pipeline.py"
        "::TestFullPipeline::test_full_end_to_end_pipeline"
    )
    print()


if __name__ == "__main__":
    main()
