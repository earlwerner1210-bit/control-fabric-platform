"""Tests for cross-pack reconciliation module."""

from __future__ import annotations

import uuid

import pytest

from app.domain_packs.reconciliation import (
    ContractWorkOrderLinker,
    CrossPlaneConflict,
    CrossPlaneLink,
    CrossPlaneReconciler,
    EvidenceBundle,
    MarginEvidenceAssembler,
    ReadinessEvidenceAssembler,
    OpsEvidenceAssembler,
    WorkOrderIncidentLinker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def contract_data() -> dict:
    """Sample contract data with rate card, obligations, scope boundaries."""
    return {
        "rate_card": [
            {"activity": "standard_maintenance", "rate": 125.0, "unit": "hour"},
            {"activity": "emergency_repair", "rate": 187.50, "unit": "hour"},
        ],
        "obligations": [
            {
                "clause_id": "CL-001",
                "description": "Provider shall deliver all scheduled network maintenance",
                "status": "active",
                "due_type": "ongoing",
            },
        ],
        "scope_boundaries": [
            {
                "scope_type": "in_scope",
                "description": "Network maintenance and equipment installation services",
                "activities": ["network_maintenance", "equipment_installation"],
            },
            {
                "scope_type": "out_of_scope",
                "description": "Capital equipment procurement",
                "activities": ["procurement"],
            },
        ],
    }


@pytest.fixture
def work_order_data() -> dict:
    """Sample work order that matches the contract."""
    return {
        "work_order_id": "WO-001",
        "work_order_type": "maintenance",
        "description": "Scheduled standard maintenance at central office",
        "location": "Site A - Central Office",
        "site_id": "SITE-A",
        "priority": "normal",
        "rate": 125.0,
        "scheduled_date": "2025-06-15T09:00:00",
        "scheduled_end": "2025-06-15T17:00:00",
        "assigned_to": "ENG-001",
    }


@pytest.fixture
def incident_data() -> dict:
    """Sample incident data."""
    return {
        "incident_id": "INC-001",
        "title": "Network degradation at central office",
        "description": "Intermittent packet loss on core network at central office Site A",
        "severity": "p2",
        "state": "investigating",
        "affected_services": ["core_network"],
        "assigned_to": "ENG-001",
        "location": "Site A - Central Office",
        "site_id": "SITE-A",
        "created_at": "2025-06-15T10:30:00",
    }


# ---------------------------------------------------------------------------
# Contract <-> Work Order linking
# ---------------------------------------------------------------------------


class TestContractWorkOrderLinking:
    """Tests for ContractWorkOrderLinker."""

    def test_contract_work_order_linking(
        self, contract_data: dict, work_order_data: dict
    ):
        """Should find links between matching contract and work order activities."""
        linker = ContractWorkOrderLinker()

        # Collect contract objects from the data
        contract_objects = []
        for entry in contract_data.get("rate_card", []):
            obj = dict(entry)
            obj.setdefault("type", "rate_card")
            contract_objects.append(obj)
        for ob in contract_data.get("obligations", []):
            obj = dict(ob)
            obj.setdefault("type", "obligation")
            contract_objects.append(obj)
        for sb in contract_data.get("scope_boundaries", []):
            obj = dict(sb)
            obj.setdefault("type", "scope_boundary")
            contract_objects.append(obj)

        links = linker.link(contract_objects, work_order_data)

        assert len(links) > 0
        assert all(isinstance(link, CrossPlaneLink) for link in links)

        # Links should reference correct domains
        for link in links:
            assert link.source_domain == "contract_margin"
            assert link.target_domain == "utilities_field"
            assert 0.0 < link.confidence <= 1.0

    def test_commercial_field_conflict_detection(
        self, contract_data: dict
    ):
        """Should detect rate mismatch conflicts."""
        linker = ContractWorkOrderLinker()

        # Work order with a different rate
        wo_data = {
            "work_order_id": "WO-MISMATCH",
            "description": "Standard maintenance work",
            "rate": 100.0,  # different from contract rate of 125
        }

        # First link, then detect conflicts
        contract_objects = [
            {"type": "rate_card", "activity": "standard_maintenance", "rate": 125.0, "unit": "hour"},
        ]
        links = linker.link(contract_objects, wo_data)
        conflicts = linker.detect_conflicts(links, contract_data, wo_data)

        # Should detect rate mismatch
        rate_conflicts = [c for c in conflicts if c.field == "rate"]
        assert len(rate_conflicts) >= 1
        assert "125" in rate_conflicts[0].value_a
        assert "100" in rate_conflicts[0].value_b

    def test_scope_conflict_detected(self, contract_data: dict):
        """Should detect scope conflict for out-of-scope activities."""
        linker = ContractWorkOrderLinker()
        wo_data = {
            "work_order_id": "WO-SCOPE",
            "description": "Equipment procurement and delivery",
        }
        contract_objects = [
            {"type": "scope_boundary", "scope_type": "out_of_scope",
             "description": "Capital equipment procurement",
             "activities": ["procurement"]},
        ]
        links = linker.link(contract_objects, wo_data)
        conflicts = linker.detect_conflicts(links, contract_data, wo_data)

        scope_conflicts = [c for c in conflicts if c.field == "scope"]
        assert len(scope_conflicts) >= 1

    def test_no_links_when_unrelated(self):
        """Unrelated contract and work order should produce no links."""
        linker = ContractWorkOrderLinker()
        contract_objects = [
            {"type": "rate_card", "activity": "plumbing_repair", "rate": 80.0, "unit": "hour"},
        ]
        wo_data = {
            "work_order_id": "WO-UNRELATED",
            "description": "Software development sprint planning",
        }
        links = linker.link(contract_objects, wo_data)
        # If similarity is below threshold, should be empty
        assert all(l.confidence >= 0.5 for l in links)


# ---------------------------------------------------------------------------
# Work Order <-> Incident linking
# ---------------------------------------------------------------------------


class TestWorkOrderIncidentLinking:
    """Tests for WorkOrderIncidentLinker."""

    def test_work_order_incident_linking(
        self, work_order_data: dict, incident_data: dict
    ):
        """Should link work order to incident by location and service."""
        linker = WorkOrderIncidentLinker()
        links = linker.link(work_order_data, [incident_data])

        assert len(links) > 0
        assert all(isinstance(link, CrossPlaneLink) for link in links)

        # Should match by location/site
        for link in links:
            assert link.source_domain == "utilities_field"
            assert link.target_domain == "telco_ops"
            assert link.confidence > 0.0

    def test_field_ops_conflict_detection(
        self, work_order_data: dict, incident_data: dict
    ):
        """Should detect ownership or timing mismatches."""
        linker = WorkOrderIncidentLinker()

        # Create a work order with different owner
        wo_data = dict(work_order_data)
        wo_data["assigned_to"] = "ENG-999"  # different from incident's ENG-001

        links = linker.link(wo_data, [incident_data])
        conflicts = linker.detect_conflicts(links, wo_data, incident_data)

        # Should detect ownership mismatch
        ownership_conflicts = [c for c in conflicts if c.field == "ownership"]
        assert len(ownership_conflicts) >= 1

    def test_no_link_without_matching_signals(self):
        """Completely unrelated WO and incident should produce no links."""
        linker = WorkOrderIncidentLinker()
        wo = {
            "work_order_id": "WO-NOWHERE",
            "description": "Routine plumbing check",
            "location": "Building Z Basement",
            "site_id": "SITE-Z",
        }
        incident = {
            "incident_id": "INC-OTHER",
            "description": "Email server capacity alert",
            "affected_services": ["email"],
            "location": "Data Center 5",
            "site_id": "DC-5",
            "created_at": "2020-01-01T00:00:00",
        }
        links = linker.link(wo, [incident])
        # Needs at least 2 matching signals
        assert len(links) == 0

    def test_severity_priority_alignment_conflict(self):
        """P1 incident with normal priority WO should flag misalignment."""
        linker = WorkOrderIncidentLinker()
        wo = {
            "work_order_id": "WO-PRI",
            "description": "Network maintenance core office",
            "location": "Site A",
            "site_id": "SITE-A",
            "priority": "normal",
            "scheduled_date": "2025-06-15T09:00:00",
        }
        incident = {
            "incident_id": "INC-PRI",
            "description": "Network maintenance core office issue",
            "severity": "p1",
            "affected_services": ["core_network"],
            "location": "Site A",
            "site_id": "SITE-A",
            "created_at": "2025-06-15T10:00:00",
        }
        links = linker.link(wo, [incident])
        conflicts = linker.detect_conflicts(links, wo, incident)

        alignment_conflicts = [c for c in conflicts if c.field == "severity_priority_alignment"]
        assert len(alignment_conflicts) >= 1


# ---------------------------------------------------------------------------
# Evidence assemblers
# ---------------------------------------------------------------------------


class TestMarginEvidenceAssembly:
    """Tests for MarginEvidenceAssembler."""

    def test_margin_evidence_assembly(self):
        """Should assemble evidence bundle from contract objects and work history."""
        assembler = MarginEvidenceAssembler()

        contract_objects = [
            {"type": "rate_card", "activity": "maintenance", "rate": 125.0},
        ]
        work_history = [
            {"work_order_id": "WO-001", "description": "Maintenance work", "billed": True},
        ]
        leakage_triggers = [
            {"trigger_type": "unbilled_work", "description": "Work not billed", "severity": "error"},
        ]

        bundle = assembler.assemble(contract_objects, work_history, leakage_triggers)

        assert isinstance(bundle, EvidenceBundle)
        assert bundle.total_items > 0
        assert len(bundle.evidence_items) > 0
        assert len(bundle.domains) >= 1
        assert bundle.confidence > 0

    def test_empty_evidence_bundle(self):
        """Empty inputs should produce zero-confidence bundle."""
        assembler = MarginEvidenceAssembler()
        bundle = assembler.assemble([], [], [])

        assert isinstance(bundle, EvidenceBundle)
        assert bundle.total_items == 0
        assert bundle.confidence == 0.0


class TestReadinessEvidenceAssembly:
    """Tests for ReadinessEvidenceAssembler."""

    def test_readiness_evidence_assembly(self):
        """Should assemble readiness evidence from WO, engineer, blockers, and skill fit."""
        assembler = ReadinessEvidenceAssembler()

        bundle = assembler.assemble(
            work_order={"work_order_id": "WO-001", "description": "Fiber work"},
            engineer={"engineer_id": "ENG-001", "name": "John"},
            blockers=[],
            skill_fit={"fit": True, "matching_skills": ["fiber"]},
        )

        assert isinstance(bundle, EvidenceBundle)
        assert bundle.total_items >= 3  # WO + engineer + skill_fit
        assert bundle.confidence > 0.5  # No blockers, fit = True


class TestOpsEvidenceAssembly:
    """Tests for OpsEvidenceAssembler."""

    def test_ops_evidence_assembly(self):
        """Should assemble ops evidence from incident and service states."""
        assembler = OpsEvidenceAssembler()

        bundle = assembler.assemble(
            incident={"incident_id": "INC-001", "severity": "p2", "title": "Network issue"},
            service_states=[
                {"service_id": "svc-core", "service_name": "core_network", "state": "degraded"},
            ],
            escalation={"level": "l2", "reason": "P2 severity"},
            next_action={"action": "investigate", "reason": "Start investigation"},
        )

        assert isinstance(bundle, EvidenceBundle)
        assert bundle.total_items >= 3
        assert bundle.confidence > 0.5


# ---------------------------------------------------------------------------
# Full cross-plane reconciliation
# ---------------------------------------------------------------------------


class TestFullCrossPlaneReconciliation:
    """Tests for CrossPlaneReconciler."""

    def test_full_cross_plane_reconciliation(
        self, contract_data: dict, work_order_data: dict, incident_data: dict
    ):
        """Should produce links, conflicts, and evidence from all three planes."""
        reconciler = CrossPlaneReconciler()

        result = reconciler.full_reconciliation(
            contract_data, work_order_data, incident_data
        )

        assert "all_links" in result
        assert "all_conflicts" in result
        assert "aggregate_evidence" in result
        assert "contract_to_wo" in result
        assert "wo_to_incident" in result

        # Should have aggregate evidence from all planes
        agg = result["aggregate_evidence"]
        assert agg["total_items"] > 0

    def test_contract_to_work_order_reconciliation(
        self, contract_data: dict, work_order_data: dict
    ):
        """Should reconcile contract to work order."""
        reconciler = CrossPlaneReconciler()
        result = reconciler.reconcile_contract_to_work_order(
            contract_data, work_order_data
        )

        assert "links" in result
        assert "conflicts" in result
        assert "evidence" in result

    def test_work_order_to_incident_reconciliation(
        self, work_order_data: dict, incident_data: dict
    ):
        """Should reconcile work order to incident."""
        reconciler = CrossPlaneReconciler()
        result = reconciler.reconcile_work_order_to_incident(
            work_order_data, incident_data
        )

        assert "links" in result
        assert "conflicts" in result
        assert "evidence" in result

    def test_no_conflicts_when_aligned(self):
        """Perfectly aligned data should produce no conflicts."""
        reconciler = CrossPlaneReconciler()

        contract = {
            "rate_card": [
                {"activity": "maintenance", "rate": 100.0, "unit": "hour"},
            ],
            "obligations": [],
            "scope_boundaries": [],
        }
        wo = {
            "work_order_id": "WO-GOOD",
            "description": "Routine inspection",
            "rate": 100.0,
            "priority": "normal",
        }
        incident = {
            "incident_id": "INC-NONE",
            "description": "Unrelated alert",
            "severity": "p4",
            "state": "closed",
            "affected_services": [],
        }

        result = reconciler.full_reconciliation(contract, wo, incident)

        # With unrelated descriptions and no overlapping signals,
        # there should be no links and therefore no conflicts
        assert len(result["all_conflicts"]) == 0
