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
    WorkOrderIncidentLinker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def contract_objects() -> list[dict]:
    """Sample contract control objects."""
    return [
        {
            "id": str(uuid.uuid4()),
            "control_type": "billable_event",
            "activity": "standard_maintenance",
            "label": "standard_maintenance",
            "rate": 125.0,
            "unit": "hour",
        },
        {
            "id": str(uuid.uuid4()),
            "control_type": "rate_card",
            "activity": "emergency_repair",
            "label": "emergency_repair",
            "rate": 187.50,
            "unit": "hour",
        },
        {
            "id": str(uuid.uuid4()),
            "control_type": "obligation",
            "clause_id": "CL-001",
            "description": "Provider shall deliver all scheduled network maintenance",
            "text": "Provider shall deliver all scheduled network maintenance",
        },
        {
            "id": str(uuid.uuid4()),
            "control_type": "penalty_condition",
            "clause_id": "CL-002",
            "description": "SLA breach penalty",
            "trigger": "failure to meet SLA response times",
        },
        {
            "id": str(uuid.uuid4()),
            "control_type": "scope_boundary",
            "description": "Network maintenance and equipment installation services",
        },
        {
            "id": str(uuid.uuid4()),
            "control_type": "contract_metadata",
            "effective_date": "2024-01-01",
            "expiry_date": "2026-12-31",
        },
    ]


@pytest.fixture
def work_order_objects() -> list[dict]:
    """Sample work order control objects."""
    return [
        {
            "id": str(uuid.uuid4()),
            "work_order_id": "WO-001",
            "activity": "standard maintenance",
            "description": "Scheduled fiber maintenance at central office",
            "scope": "network maintenance at site A",
            "status": "completed",
            "rate": 125.0,
            "hours": 4.0,
            "billed": True,
            "scheduled_date": "2025-06-15",
            "incident_id": "INC-001",
            "assigned_engineer": "ENG-001",
        },
        {
            "id": str(uuid.uuid4()),
            "work_order_id": "WO-002",
            "activity": "custom development work",
            "description": "Custom software development",
            "scope": "custom software development",
            "status": "completed",
            "rate": 200.0,
            "hours": 8.0,
            "billed": False,
            "scheduled_date": "2025-07-01",
            "incident_id": "INC-002",
            "assigned_engineer": "ENG-002",
        },
    ]


@pytest.fixture
def incident_objects() -> list[dict]:
    """Sample incident control objects."""
    return [
        {
            "id": str(uuid.uuid4()),
            "incident_id": "INC-001",
            "title": "Network degradation at site A",
            "description": "Intermittent packet loss on core network at site A",
            "state": "resolved",
            "affected_services": ["core_network"],
            "assigned_to": "ENG-001",
            "location": "site_a",
        },
        {
            "id": str(uuid.uuid4()),
            "incident_id": "INC-002",
            "title": "Service request for custom work",
            "description": "Custom development request",
            "state": "investigating",
            "affected_services": ["billing"],
            "assigned_to": "ENG-003",
            "location": "site_b",
        },
    ]


# ---------------------------------------------------------------------------
# Contract <-> Work Order linking
# ---------------------------------------------------------------------------


class TestContractWorkOrderLinking:
    """Tests for ContractWorkOrderLinker."""

    def test_contract_work_order_linking(
        self, contract_objects: list[dict], work_order_objects: list[dict]
    ):
        """Should find links between matching contract and work order activities."""
        linker = ContractWorkOrderLinker()
        links = linker.link_contract_to_work_order(contract_objects, work_order_objects)

        assert len(links) > 0
        assert all(isinstance(link, CrossPlaneLink) for link in links)

        # Standard maintenance should match to WO-001
        maintenance_links = [
            l for l in links
            if l.metadata.get("contract_activity", "").startswith("standard")
            or l.metadata.get("rate_card_activity", "").startswith("standard")
        ]
        assert len(maintenance_links) > 0

        # All links should have source=contract_margin, target=utilities_field
        for link in links:
            assert link.source_domain == "contract_margin"
            assert link.target_domain == "utilities_field"
            assert 0.0 < link.confidence <= 1.0

    def test_commercial_field_conflict_detection(
        self, contract_objects: list[dict], work_order_objects: list[dict]
    ):
        """Should detect conflicts like unbilled work and scope conflicts."""
        linker = ContractWorkOrderLinker()
        conflicts = linker.detect_commercial_field_conflicts(
            contract_objects, work_order_objects
        )

        assert len(conflicts) > 0
        assert all(isinstance(c, CrossPlaneConflict) for c in conflicts)

        # WO-002 "custom development" is completed but not billed and out of scope
        conflict_types = [c.conflict_type for c in conflicts]
        assert "unbilled_work" in conflict_types or "scope_conflict" in conflict_types

        # All conflicts should have resolution suggestions
        for conflict in conflicts:
            assert conflict.domain_a
            assert conflict.domain_b
            assert conflict.severity in ("info", "warning", "error", "critical")

    def test_rate_mismatch_detected(self, contract_objects: list[dict]):
        """Should detect when work order rate differs from contract rate."""
        linker = ContractWorkOrderLinker()
        work_orders = [
            {
                "id": str(uuid.uuid4()),
                "work_order_id": "WO-RATE",
                "activity": "standard_maintenance",
                "description": "Standard maintenance",
                "scope": "maintenance",
                "status": "completed",
                "rate": 100.0,  # different from contract rate of 125
                "billed_rate": 100.0,
            },
        ]
        conflicts = linker.detect_commercial_field_conflicts(contract_objects, work_orders)

        rate_mismatches = [c for c in conflicts if c.conflict_type == "rate_mismatch"]
        assert len(rate_mismatches) >= 1
        assert "100" in rate_mismatches[0].description
        assert "125" in rate_mismatches[0].description

    def test_timeline_conflict_detected(self, contract_objects: list[dict]):
        """Should detect work performed after contract expiry."""
        linker = ContractWorkOrderLinker()
        work_orders = [
            {
                "id": str(uuid.uuid4()),
                "work_order_id": "WO-EXPIRED",
                "activity": "standard_maintenance",
                "description": "Standard maintenance",
                "scope": "maintenance",
                "status": "completed",
                "completed_date": "2027-06-01",  # after contract expiry of 2026-12-31
            },
        ]
        conflicts = linker.detect_commercial_field_conflicts(contract_objects, work_orders)

        timeline_conflicts = [c for c in conflicts if c.conflict_type == "timeline_conflict"]
        assert len(timeline_conflicts) >= 1


# ---------------------------------------------------------------------------
# Work Order <-> Incident linking
# ---------------------------------------------------------------------------


class TestWorkOrderIncidentLinking:
    """Tests for WorkOrderIncidentLinker."""

    def test_work_order_incident_linking(
        self, work_order_objects: list[dict], incident_objects: list[dict]
    ):
        """Should link work orders to incidents by reference ID."""
        linker = WorkOrderIncidentLinker()
        links = linker.link_work_order_to_incident(
            work_order_objects, incident_objects
        )

        assert len(links) > 0
        assert all(isinstance(link, CrossPlaneLink) for link in links)

        # WO-001 should link to INC-001 via direct reference
        direct_links = [
            l for l in links
            if l.metadata.get("match_type") == "direct_reference"
        ]
        assert len(direct_links) >= 1
        assert direct_links[0].confidence == 1.0

    def test_field_ops_conflict_detection(
        self, work_order_objects: list[dict], incident_objects: list[dict]
    ):
        """Should detect status mismatches between work orders and incidents."""
        linker = WorkOrderIncidentLinker()
        conflicts = linker.detect_field_ops_conflicts(
            work_order_objects, incident_objects
        )

        assert len(conflicts) > 0
        conflict_types = {c.conflict_type for c in conflicts}

        # WO-002 completed but INC-002 still investigating
        assert "wo_completed_incident_active" in conflict_types

        # WO-001 engineer (ENG-001) matches INC-001 owner, but
        # WO-002 engineer (ENG-002) != INC-002 owner (ENG-003)
        assert "ownership_mismatch" in conflict_types

    def test_incident_resolved_wo_open_conflict(self):
        """Should detect incident resolved but work order still open."""
        linker = WorkOrderIncidentLinker()
        work_orders = [
            {
                "work_order_id": "WO-OPEN",
                "status": "in_progress",
                "incident_id": "INC-RESOLVED",
            },
        ]
        incidents = [
            {
                "incident_id": "INC-RESOLVED",
                "state": "resolved",
            },
        ]
        conflicts = linker.detect_field_ops_conflicts(work_orders, incidents)

        assert any(c.conflict_type == "incident_resolved_wo_open" for c in conflicts)

    def test_multiple_work_orders_for_same_incident(self):
        """Should detect multiple work orders linked to same incident."""
        linker = WorkOrderIncidentLinker()
        work_orders = [
            {"work_order_id": "WO-A", "status": "pending", "incident_id": "INC-DUP"},
            {"work_order_id": "WO-B", "status": "pending", "incident_id": "INC-DUP"},
        ]
        incidents = [
            {"incident_id": "INC-DUP", "state": "new"},
        ]
        conflicts = linker.detect_field_ops_conflicts(work_orders, incidents)

        assert any(c.conflict_type == "multiple_work_orders" for c in conflicts)

    def test_ownership_match_creates_link(self):
        """Should link work order and incident by shared engineer/owner."""
        linker = WorkOrderIncidentLinker()
        work_orders = [
            {
                "work_order_id": "WO-OWN",
                "assigned_engineer": "eng_smith",
                "description": "Fiber repair at site X",
            },
        ]
        incidents = [
            {
                "incident_id": "INC-OWN",
                "assigned_to": "eng_smith",
                "description": "Service issue at site Y",
            },
        ]
        links = linker.link_work_order_to_incident(work_orders, incidents)

        ownership_links = [l for l in links if l.metadata.get("match_type") == "ownership_match"]
        assert len(ownership_links) >= 1


# ---------------------------------------------------------------------------
# Margin evidence assembly
# ---------------------------------------------------------------------------


class TestMarginEvidenceAssembly:
    """Tests for MarginEvidenceAssembler."""

    def test_margin_evidence_assembly(
        self,
        contract_objects: list[dict],
        work_order_objects: list[dict],
        incident_objects: list[dict],
    ):
        """Should assemble a complete evidence bundle."""
        assembler = MarginEvidenceAssembler()
        bundle = assembler.assemble_margin_evidence(
            contract_objects, work_order_objects, incident_objects
        )

        assert isinstance(bundle, EvidenceBundle)
        assert bundle.bundle_type == "margin_evidence"
        assert len(bundle.contract_objects) == len(contract_objects)
        assert len(bundle.field_objects) == len(work_order_objects)
        assert len(bundle.ops_objects) == len(incident_objects)
        assert len(bundle.cross_links) > 0
        # Should have some conflicts from the mismatched data
        assert len(bundle.conflicts) > 0

    def test_margin_impact_calculation(
        self,
        contract_objects: list[dict],
        work_order_objects: list[dict],
        incident_objects: list[dict],
    ):
        """Should calculate financial impact from evidence bundle."""
        assembler = MarginEvidenceAssembler()
        bundle = assembler.assemble_margin_evidence(
            contract_objects, work_order_objects, incident_objects
        )
        impact = assembler.calculate_margin_impact(bundle)

        assert "total_billed" in impact
        assert "total_billable" in impact
        assert "leakage_amount" in impact
        assert "penalty_exposure" in impact
        assert "recovery_potential" in impact

        # WO-001 is billed (125 * 4 = 500), WO-002 is not billed (200 * 8 = 1600)
        assert impact["total_billed"] == pytest.approx(500.0)
        assert impact["total_billable"] == pytest.approx(2100.0)  # 500 + 1600
        assert impact["leakage_amount"] == pytest.approx(1600.0)
        assert impact["recovery_potential"] > 0


# ---------------------------------------------------------------------------
# Full cross-plane reconciliation
# ---------------------------------------------------------------------------


class TestFullCrossPlaneReconciliation:
    """Tests for CrossPlaneReconciler."""

    def test_full_cross_plane_reconciliation(
        self,
        contract_objects: list[dict],
        work_order_objects: list[dict],
        incident_objects: list[dict],
    ):
        """Should produce links, conflicts, and summary."""
        reconciler = CrossPlaneReconciler()
        result = reconciler.reconcile_all(
            contract_objects, work_order_objects, incident_objects
        )

        assert "links" in result
        assert "conflicts" in result
        assert "has_conflicts" in result
        assert "summary" in result

        assert len(result["links"]) > 0
        assert len(result["conflicts"]) > 0
        assert result["has_conflicts"] is True

        summary = result["summary"]
        assert summary["total_links"] > 0
        assert summary["total_conflicts"] > 0
        assert "conflict_types" in summary
        assert "severity_counts" in summary

    def test_no_conflicts_when_aligned(self):
        """Aligned data should produce no conflicts."""
        reconciler = CrossPlaneReconciler()

        contract = [
            {
                "control_type": "billable_event",
                "activity": "maintenance",
                "label": "maintenance",
                "rate": 100.0,
            },
            {
                "control_type": "scope_boundary",
                "description": "maintenance services",
            },
        ]
        work_orders = [
            {
                "work_order_id": "WO-GOOD",
                "activity": "maintenance",
                "description": "maintenance",
                "scope": "maintenance services",
                "status": "pending",  # not completed, so no unbilled conflict
            },
        ]
        incidents: list[dict] = []

        result = reconciler.reconcile_all(contract, work_orders, incidents)

        # No completed work = no unbilled work conflict
        # No incidents = no field-ops conflicts
        assert result["has_conflicts"] is False
        assert len(result["conflicts"]) == 0
        assert result["summary"]["total_conflicts"] == 0
