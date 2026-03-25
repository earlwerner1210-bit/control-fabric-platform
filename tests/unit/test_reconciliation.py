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


def _make_contract_data() -> dict:
    """Contract data dict as expected by CrossPlaneReconciler methods."""
    return {
        "rate_card": [
            {
                "id": "rc-001",
                "activity": "standard_maintenance",
                "rate": 125.0,
                "unit": "hour",
            },
            {
                "id": "rc-002",
                "activity": "emergency_repair",
                "rate": 187.50,
                "unit": "hour",
            },
        ],
        "obligations": [
            {
                "id": "ob-001",
                "clause_id": "CL-001",
                "description": "Provider shall deliver all scheduled maintenance",
                "status": "active",
            },
        ],
        "scope_boundaries": [
            {
                "id": "sb-001",
                "scope_type": "in_scope",
                "description": "Network maintenance and monitoring in scope",
                "activities": ["maintenance", "monitoring"],
            },
        ],
    }


def _make_work_order_dict() -> dict:
    """A single work order dict for linker methods that take a single WO."""
    return {
        "work_order_id": "WO-001",
        "work_order_type": "maintenance",
        "description": "Scheduled standard maintenance at Building A",
        "location": "Building A",
        "site_id": "SITE-A",
        "rate": 125.0,
        "status": "completed",
        "scheduled_date": "2024-04-01T08:00:00",
        "scheduled_end": "2024-04-01T16:00:00",
    }


def _make_work_order_dict_mismatch() -> dict:
    """Work order with rate mismatch vs contract rate for emergency_repair."""
    return {
        "work_order_id": "WO-002",
        "work_order_type": "repair",
        "description": "Emergency repair of fiber cabinet",
        "location": "Building B",
        "rate": 150.0,  # lower than contract rate of 187.50
        "status": "completed",
    }


def _make_incident_dicts() -> list[dict]:
    return [
        {
            "incident_id": "INC-001",
            "title": "Core network degradation",
            "description": "Core network experiencing packet loss",
            "severity": "p2",
            "state": "investigating",
            "affected_services": ["core_network", "voip"],
            "assigned_to": "senior_engineer",
            "created_at": "2024-04-01T10:00:00",
            "location": "Building A",
            "site_id": "SITE-A",
        },
    ]


# ---------------------------------------------------------------------------
# Tests: ContractWorkOrderLinker
# ---------------------------------------------------------------------------


class TestContractWorkOrderLinking:
    """test_contract_work_order_linking: Contract rate card links to WO activities."""

    def test_links_generated_by_activity_match(self):
        linker = ContractWorkOrderLinker()
        contract_data = _make_contract_data()

        # Flatten contract objects as the linker.link() expects
        contract_objects = []
        for rc in contract_data["rate_card"]:
            obj = dict(rc)
            obj.setdefault("type", "rate_card")
            contract_objects.append(obj)
        for ob in contract_data["obligations"]:
            obj = dict(ob)
            obj.setdefault("type", "obligation")
            contract_objects.append(obj)

        links = linker.link(contract_objects, _make_work_order_dict())

        assert len(links) > 0
        assert all(isinstance(l, CrossPlaneLink) for l in links)

        # At least one link should be between contract_margin and utilities_field
        domains = {(l.source_domain, l.target_domain) for l in links}
        assert ("contract_margin", "utilities_field") in domains

    def test_link_metadata_contains_activity(self):
        linker = ContractWorkOrderLinker()
        contract_objects = [
            {"type": "rate_card", "id": "rc-1", "activity": "standard_maintenance", "rate": 125.0},
        ]
        wo = _make_work_order_dict()

        links = linker.link(contract_objects, wo)

        rate_links = [l for l in links if l.link_type == "rate_card_to_activity"]
        assert len(rate_links) >= 1
        assert "activity" in rate_links[0].metadata

    def test_no_links_when_no_overlap(self):
        linker = ContractWorkOrderLinker()
        contract_objects = [
            {"type": "rate_card", "id": "rc-x", "activity": "zzz_no_match_xyz", "rate": 100.0},
        ]
        wo = {
            "work_order_id": "WO-X",
            "description": "completely unrelated plumbing in another city",
        }

        links = linker.link(contract_objects, wo)
        assert len(links) == 0


class TestConflictDetectionRateMismatch:
    """test_conflict_detection_rate_mismatch: Detect rate differences."""

    def test_rate_mismatch_detected(self):
        linker = ContractWorkOrderLinker()
        contract_objects = [
            {"type": "rate_card", "id": "rc-er", "activity": "emergency_repair", "rate": 187.50, "unit": "hour"},
        ]
        wo = _make_work_order_dict_mismatch()

        # First generate links
        links = linker.link(contract_objects, wo)

        # Then detect conflicts using those links
        contract_data = {"rate_card": [{"activity": "emergency_repair", "rate": 187.50}]}
        conflicts = linker.detect_conflicts(links, contract_data, wo)

        rate_conflicts = [c for c in conflicts if c.field == "rate"]
        # WO rate 150 vs contract 187.50 -> mismatch
        assert len(rate_conflicts) >= 1

    def test_no_rate_mismatch_when_rates_match(self):
        linker = ContractWorkOrderLinker()
        contract_objects = [
            {"type": "rate_card", "id": "rc-sm", "activity": "standard_maintenance", "rate": 125.0},
        ]
        wo = _make_work_order_dict()  # rate=125.0

        links = linker.link(contract_objects, wo)
        conflicts = linker.detect_conflicts(links, {"rate_card": []}, wo)

        rate_conflicts = [c for c in conflicts if c.field == "rate"]
        assert len(rate_conflicts) == 0


# ---------------------------------------------------------------------------
# Tests: WorkOrderIncidentLinker
# ---------------------------------------------------------------------------


class TestWorkOrderIncidentLinking:
    """test_work_order_incident_linking: WO links to incident by service/location/time."""

    def test_service_and_location_link(self):
        linker = WorkOrderIncidentLinker()
        wo = {
            "work_order_id": "WO-LINK",
            "description": "core_network maintenance at Building A",
            "location": "Building A",
            "site_id": "SITE-A",
            "scheduled_date": "2024-04-01T08:00:00",
        }
        incidents = _make_incident_dicts()

        links = linker.link(wo, incidents)

        # Should link because WO description mentions core_network, location/site matches,
        # and time is close
        assert len(links) >= 1
        assert all(isinstance(l, CrossPlaneLink) for l in links)
        assert links[0].source_domain == "utilities_field"
        assert links[0].target_domain == "telco_ops"

    def test_no_link_when_no_match(self):
        linker = WorkOrderIncidentLinker()
        wo = {
            "work_order_id": "WO-NOMATCH",
            "description": "painting a fence in another country",
            "location": "Remote Village",
        }
        incidents = [{
            "incident_id": "INC-NOMATCH",
            "affected_services": ["billing"],
            "description": "billing issue",
            "location": "Data Center Z",
        }]

        links = linker.link(wo, incidents)
        assert len(links) == 0


# ---------------------------------------------------------------------------
# Tests: Evidence assembly
# ---------------------------------------------------------------------------


class TestMarginEvidenceAssembly:
    """test_margin_evidence_assembly: Evidence bundle has correct structure."""

    def test_bundle_has_items(self):
        assembler = MarginEvidenceAssembler()
        contract_objects = [
            {"type": "rate_card", "activity": "maintenance", "rate": 125.0},
        ]
        work_history = [
            {"work_order_id": "WO-1", "description": "maintenance", "status": "completed"},
        ]
        leakage_triggers = [
            {"trigger_type": "unbilled_work", "description": "Unbilled completed work", "severity": "warning"},
        ]

        bundle = assembler.assemble(contract_objects, work_history, leakage_triggers)

        assert isinstance(bundle, EvidenceBundle)
        assert bundle.total_items == 3  # 1 contract + 1 WO + 1 trigger
        assert len(bundle.evidence_items) == 3
        assert len(bundle.domains) >= 1

    def test_bundle_confidence_with_triggers(self):
        assembler = MarginEvidenceAssembler()
        bundle = assembler.assemble(
            [{"type": "rate_card", "activity": "maint"}],
            [{"work_order_id": "WO-1"}],
            [{"trigger_type": "unbilled", "description": "leak"}],
        )

        # With contract, work, and triggers, confidence should be significant
        assert bundle.confidence > 0.5

    def test_empty_inputs(self):
        assembler = MarginEvidenceAssembler()
        bundle = assembler.assemble([], [], [])

        assert isinstance(bundle, EvidenceBundle)
        assert bundle.total_items == 0
        assert bundle.confidence == 0.0


class TestReadinessEvidenceAssembly:
    """test_readiness_evidence_assembly: Evidence bundle includes WO, engineer, blockers."""

    def test_readiness_bundle(self):
        assembler = ReadinessEvidenceAssembler()
        bundle = assembler.assemble(
            work_order={"work_order_id": "WO-1", "description": "maintenance"},
            engineer={"engineer_id": "ENG-1", "name": "Test Eng"},
            blockers=[],
            skill_fit={"fit": True, "matched_skills": ["fiber"]},
        )

        assert isinstance(bundle, EvidenceBundle)
        assert bundle.domains == ["utilities_field"]
        # WO + engineer + skill_fit = 3 items (no blockers)
        assert bundle.total_items == 3

    def test_readiness_with_blockers(self):
        assembler = ReadinessEvidenceAssembler()
        bundle = assembler.assemble(
            work_order={"work_order_id": "WO-1", "description": "repair"},
            engineer={"engineer_id": "ENG-1", "name": "Eng"},
            blockers=[
                {"blocker_type": "missing_skill", "description": "Missing gas_fitting", "severity": "error"},
            ],
            skill_fit={"fit": False},
        )

        assert bundle.total_items == 4  # WO + engineer + 1 blocker + skill_fit
        # Low confidence due to blocker and no fit
        assert bundle.confidence < 0.7


class TestOpsEvidenceAssembly:
    """test_ops_evidence_assembly: Evidence bundle includes incident + escalation."""

    def test_ops_bundle(self):
        assembler = OpsEvidenceAssembler()
        bundle = assembler.assemble(
            incident={"incident_id": "INC-1", "title": "Network outage", "severity": "p1"},
            service_states=[
                {"service_id": "svc-1", "service_name": "core_network", "state": "outage"},
            ],
            escalation={"level": "l3", "reason": "P1 severity requires L3"},
            next_action={"action": "investigate", "reason": "Begin investigation"},
        )

        assert isinstance(bundle, EvidenceBundle)
        assert bundle.domains == ["telco_ops"]
        # incident + 1 service_state + escalation + next_action = 4
        assert bundle.total_items == 4
        assert bundle.confidence > 0.7

    def test_ops_minimal(self):
        assembler = OpsEvidenceAssembler()
        bundle = assembler.assemble(
            incident={"incident_id": "INC-2", "title": "Minor issue"},
            service_states=[],
            escalation={},
            next_action={},
        )

        assert bundle.total_items == 1  # just the incident
        assert bundle.confidence >= 0.3


# ---------------------------------------------------------------------------
# Tests: Full reconciliation
# ---------------------------------------------------------------------------


class TestFullReconciliation:
    """test_full_reconciliation: End-to-end reconciliation across all 3 domains."""

    def test_full_reconciliation_returns_dict(self):
        reconciler = CrossPlaneReconciler()
        result = reconciler.full_reconciliation(
            contract_data=_make_contract_data(),
            wo_data=_make_work_order_dict(),
            incident_data={"incidents": _make_incident_dicts()},
        )

        assert isinstance(result, dict)
        assert "all_links" in result
        assert "all_conflicts" in result
        assert "aggregate_evidence" in result
        assert "contract_to_wo" in result
        assert "wo_to_incident" in result

    def test_contract_to_wo_links(self):
        reconciler = CrossPlaneReconciler()
        result = reconciler.reconcile_contract_to_work_order(
            contract_data=_make_contract_data(),
            wo_data=_make_work_order_dict(),
        )

        assert isinstance(result, dict)
        assert "links" in result
        assert "conflicts" in result
        assert "evidence" in result
        assert len(result["links"]) > 0

    def test_wo_to_incident_links(self):
        reconciler = CrossPlaneReconciler()
        wo = {
            "work_order_id": "WO-INC",
            "description": "core_network maintenance at Building A",
            "location": "Building A",
            "site_id": "SITE-A",
            "scheduled_date": "2024-04-01T08:00:00",
        }
        result = reconciler.reconcile_work_order_to_incident(
            wo_data=wo,
            incident_data={"incidents": _make_incident_dicts()},
        )

        assert isinstance(result, dict)
        assert "links" in result
        assert "evidence" in result

    def test_rate_mismatch_in_conflicts(self):
        reconciler = CrossPlaneReconciler()
        contract_data = {
            "rate_card": [
                {"activity": "emergency_repair", "rate": 187.50, "unit": "hour"},
            ],
        }
        wo_data = _make_work_order_dict_mismatch()

        result = reconciler.reconcile_contract_to_work_order(contract_data, wo_data)

        rate_conflicts = [
            c for c in result["conflicts"]
            if c.get("field") == "rate"
        ]
        assert len(rate_conflicts) >= 1

    def test_empty_inputs_no_crash(self):
        reconciler = CrossPlaneReconciler()
        result = reconciler.full_reconciliation(
            contract_data={},
            wo_data={},
            incident_data={},
        )

        assert isinstance(result, dict)
        assert len(result["all_links"]) == 0
        assert len(result["all_conflicts"]) == 0
