"""Tests for the CrossPlaneReconciler from app.domain_packs.reconciliation."""

from __future__ import annotations

import pytest

from app.domain_packs.reconciliation import (
    ContractWorkOrderLinker,
    CrossPlaneConflict,
    CrossPlaneLink,
    CrossPlaneReconciler,
    EvidenceBundle,
    MarginEvidenceAssembler,
    OpsEvidenceAssembler,
    ReadinessEvidenceAssembler,
    WorkOrderIncidentLinker,
)


# ---------------------------------------------------------------------------
# Shared test data builders
# ---------------------------------------------------------------------------


def _make_contract_objects() -> list[dict]:
    return [
        {
            "control_type": "billable_event",
            "id": "be-001",
            "activity": "standard_maintenance",
            "label": "standard_maintenance",
            "rate": 125.0,
            "unit": "hour",
        },
        {
            "control_type": "billable_event",
            "id": "be-002",
            "activity": "emergency_repair",
            "label": "emergency_repair",
            "rate": 187.50,
            "unit": "hour",
        },
        {
            "control_type": "rate_card",
            "id": "rc-001",
            "activity": "standard_maintenance",
            "label": "standard_maintenance",
            "rate": 125.0,
            "unit": "hour",
        },
        {
            "control_type": "obligation",
            "id": "ob-001",
            "description": "Provider shall deliver all scheduled maintenance",
            "text": "Provider shall deliver all scheduled maintenance",
            "clause_id": "CL-001",
        },
        {
            "control_type": "penalty_condition",
            "id": "pc-001",
            "description": "Penalty for SLA breach",
            "trigger": "sla_breach response time",
            "clause_id": "CL-002",
        },
        {
            "control_type": "scope_boundary",
            "id": "sb-001",
            "description": "Network maintenance and monitoring in scope",
        },
    ]


def _make_work_order_objects() -> list[dict]:
    return [
        {
            "control_type": "work_order",
            "id": "wo-001",
            "work_order_id": "WO-001",
            "activity": "standard maintenance",
            "description": "Scheduled standard maintenance at Building A",
            "scope": "Scheduled standard maintenance at Building A",
            "status": "completed",
            "location": "Building A",
            "site_id": "SITE-A",
            "billed_rate": 125.0,
            "rate": 125.0,
            "hours": 4,
            "billed": True,
            "scheduled_date": "2024-04-01",
            "affected_services": ["core_network"],
        },
        {
            "control_type": "work_order",
            "id": "wo-002",
            "work_order_id": "WO-002",
            "activity": "emergency repair",
            "description": "Emergency repair of fiber cabinet",
            "scope": "Emergency repair of fiber cabinet",
            "status": "completed",
            "location": "Building B",
            "billed_rate": 150.0,  # lower than contract rate of 187.50
            "rate": 150.0,
            "hours": 3,
            "billed": True,
            "incident_id": "INC-001",
        },
    ]


def _make_incident_objects() -> list[dict]:
    return [
        {
            "control_type": "incident",
            "id": "inc-001",
            "incident_id": "INC-001",
            "title": "Core network degradation",
            "description": "Core network experiencing packet loss",
            "severity": "p2",
            "state": "investigating",
            "affected_services": ["core_network", "voip"],
            "assigned_to": "senior_engineer",
        },
    ]


# ---------------------------------------------------------------------------
# Tests: ContractWorkOrderLinker
# ---------------------------------------------------------------------------


class TestContractWorkOrderLinking:
    """test_contract_work_order_linking: Contract rate card links to WO activities."""

    def test_links_generated_by_activity_match(self):
        linker = ContractWorkOrderLinker()
        links = linker.link_contract_to_work_order(
            _make_contract_objects(),
            _make_work_order_objects(),
        )

        assert len(links) > 0
        assert all(isinstance(l, CrossPlaneLink) for l in links)

        # At least one link should be between contract_margin and utilities_field
        domains = {(l.source_domain, l.target_domain) for l in links}
        assert ("contract_margin", "utilities_field") in domains

    def test_link_metadata_contains_activity(self):
        linker = ContractWorkOrderLinker()
        links = linker.link_contract_to_work_order(
            _make_contract_objects(),
            _make_work_order_objects(),
        )

        maps_to_links = [l for l in links if l.link_type == "maps_to"]
        assert len(maps_to_links) > 0

    def test_no_links_when_no_overlap(self):
        linker = ContractWorkOrderLinker()
        links = linker.link_contract_to_work_order(
            [{"control_type": "billable_event", "activity": "zzz_no_match", "id": "x"}],
            [{"control_type": "work_order", "activity": "aaa_other", "description": "other", "scope": "other", "id": "y"}],
        )

        maps_to = [l for l in links if l.link_type == "maps_to"]
        assert len(maps_to) == 0


class TestConflictDetectionRateMismatch:
    """test_conflict_detection_rate_mismatch: Detect rate differences."""

    def test_rate_mismatch_detected(self):
        linker = ContractWorkOrderLinker()
        conflicts = linker.detect_commercial_field_conflicts(
            _make_contract_objects(),
            _make_work_order_objects(),
        )

        rate_conflicts = [c for c in conflicts if c.conflict_type == "rate_mismatch"]
        # WO-002 billed at $150 vs contract $187.50 for emergency_repair
        assert len(rate_conflicts) >= 1
        assert any("emergency" in c.description.lower() for c in rate_conflicts)

    def test_no_rate_mismatch_when_rates_match(self):
        linker = ContractWorkOrderLinker()

        wo = [{
            "control_type": "work_order",
            "activity": "standard_maintenance",
            "description": "maintenance",
            "scope": "maintenance",
            "status": "completed",
            "rate": 125.0,
            "billed_rate": 125.0,
            "id": "wo-x",
        }]
        co = [{
            "control_type": "rate_card",
            "activity": "standard_maintenance",
            "rate": 125.0,
            "id": "rc-x",
        }]
        conflicts = linker.detect_commercial_field_conflicts(co, wo)
        rate_conflicts = [c for c in conflicts if c.conflict_type == "rate_mismatch"]
        assert len(rate_conflicts) == 0


# ---------------------------------------------------------------------------
# Tests: WorkOrderIncidentLinker
# ---------------------------------------------------------------------------


class TestWorkOrderIncidentLinking:
    """test_work_order_incident_linking: WO links to incident by service."""

    def test_direct_reference_link(self):
        linker = WorkOrderIncidentLinker()
        links = linker.link_work_order_to_incident(
            _make_work_order_objects(),
            _make_incident_objects(),
        )

        # WO-002 has incident_id = INC-001 which matches the incident
        direct = [l for l in links if l.metadata.get("match_type") == "direct_reference"]
        assert len(direct) >= 1

    def test_service_overlap_link(self):
        linker = WorkOrderIncidentLinker()

        # WO with affected_services matching incident
        wo = [{
            "id": "wo-svc",
            "work_order_id": "WO-SVC",
            "description": "service maintenance",
            "affected_services": ["core_network"],
        }]
        inc = [{
            "id": "inc-svc",
            "incident_id": "INC-SVC",
            "affected_services": ["core_network"],
        }]
        links = linker.link_work_order_to_incident(wo, inc)

        svc_links = [l for l in links if l.metadata.get("match_type") == "service_overlap"]
        assert len(svc_links) == 1

    def test_no_link_when_no_match(self):
        linker = WorkOrderIncidentLinker()

        wo = [{"id": "wo-x", "work_order_id": "WO-X", "description": "painting"}]
        inc = [{"id": "inc-x", "incident_id": "INC-X", "affected_services": ["billing"]}]
        links = linker.link_work_order_to_incident(wo, inc)

        assert len(links) == 0


# ---------------------------------------------------------------------------
# Tests: Evidence assembly
# ---------------------------------------------------------------------------


class TestMarginEvidenceAssembly:
    """test_margin_evidence_assembly: Evidence bundle has correct item count."""

    def test_bundle_has_all_objects(self):
        assembler = MarginEvidenceAssembler()
        bundle = assembler.assemble_margin_evidence(
            contract_objects=_make_contract_objects(),
            work_objects=_make_work_order_objects(),
            incident_objects=_make_incident_objects(),
        )

        assert isinstance(bundle, EvidenceBundle)
        assert bundle.bundle_type == "margin_evidence"
        assert len(bundle.contract_objects) == len(_make_contract_objects())
        assert len(bundle.field_objects) == len(_make_work_order_objects())
        assert len(bundle.ops_objects) == len(_make_incident_objects())

    def test_bundle_has_cross_links(self):
        assembler = MarginEvidenceAssembler()
        bundle = assembler.assemble_margin_evidence(
            _make_contract_objects(),
            _make_work_order_objects(),
            _make_incident_objects(),
        )

        assert len(bundle.cross_links) > 0


class TestReadinessEvidenceAssembly:
    """test_readiness_evidence_assembly: Evidence bundle includes blockers."""

    def test_readiness_bundle(self):
        assembler = ReadinessEvidenceAssembler()
        bundle = assembler.assemble_readiness_evidence(
            work_order_objects=_make_work_order_objects(),
            engineer_objects=[{"engineer_id": "ENG-1", "skills": []}],
            contract_objects=_make_contract_objects(),
        )

        assert isinstance(bundle, EvidenceBundle)
        assert bundle.bundle_type == "readiness_evidence"
        # field_objects = work_orders + engineers
        assert len(bundle.field_objects) == len(_make_work_order_objects()) + 1


class TestOpsEvidenceAssembly:
    """test_ops_evidence_assembly: Evidence bundle includes escalation."""

    def test_ops_bundle(self):
        assembler = OpsEvidenceAssembler()
        bundle = assembler.assemble_ops_evidence(
            incident_objects=_make_incident_objects(),
            work_order_objects=_make_work_order_objects(),
            service_state_objects=[{
                "service_id": "svc-001",
                "service_name": "core_network",
                "state": "outage",
            }],
        )

        assert isinstance(bundle, EvidenceBundle)
        assert bundle.bundle_type == "ops_evidence"
        # ops_objects = incidents + service_states
        assert len(bundle.ops_objects) == len(_make_incident_objects()) + 1
        assert len(bundle.field_objects) == len(_make_work_order_objects())


# ---------------------------------------------------------------------------
# Tests: Full reconciliation
# ---------------------------------------------------------------------------


class TestFullReconciliation:
    """test_full_reconciliation: End-to-end reconciliation across all 3 domains."""

    def test_reconcile_all_returns_dict(self):
        reconciler = CrossPlaneReconciler()
        result = reconciler.reconcile_all(
            contract_objects=_make_contract_objects(),
            work_order_objects=_make_work_order_objects(),
            incident_objects=_make_incident_objects(),
        )

        assert isinstance(result, dict)
        assert "links" in result
        assert "conflicts" in result
        assert "has_conflicts" in result
        assert "summary" in result

    def test_links_span_both_planes(self):
        reconciler = CrossPlaneReconciler()
        result = reconciler.reconcile_all(
            _make_contract_objects(),
            _make_work_order_objects(),
            _make_incident_objects(),
        )

        links = result["links"]
        assert len(links) > 0

        # Should have contract-field and field-ops links
        cw_links = [l for l in links if l.source_domain == "contract_margin"]
        wi_links = [l for l in links if l.source_domain == "utilities_field"]
        assert len(cw_links) > 0
        assert len(wi_links) > 0

    def test_summary_counts(self):
        reconciler = CrossPlaneReconciler()
        result = reconciler.reconcile_all(
            _make_contract_objects(),
            _make_work_order_objects(),
            _make_incident_objects(),
        )

        summary = result["summary"]
        assert summary["total_links"] > 0
        assert summary["contract_work_order_links"] > 0
        assert summary["work_order_incident_links"] > 0
        assert isinstance(summary["total_conflicts"], int)

    def test_rate_mismatch_in_conflicts(self):
        reconciler = CrossPlaneReconciler()
        result = reconciler.reconcile_all(
            _make_contract_objects(),
            _make_work_order_objects(),
            _make_incident_objects(),
        )

        conflict_types = result["summary"].get("conflict_types", {})
        assert "rate_mismatch" in conflict_types

    def test_empty_inputs_no_crash(self):
        reconciler = CrossPlaneReconciler()
        result = reconciler.reconcile_all([], [], [])

        assert result["has_conflicts"] is False
        assert len(result["links"]) == 0
        assert len(result["conflicts"]) == 0
