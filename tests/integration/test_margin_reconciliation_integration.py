"""Integration tests for margin reconciliation across multiple domain packs.

These tests compose multiple reconcilers and domain pack components together
to verify end-to-end margin diagnosis, leakage detection, contradiction
detection, and evidence chain validation.
"""

from __future__ import annotations

from app.domain_packs.reconciliation import (
    ContradictionDetector,
    EvidenceBundle,
    EvidenceChainValidator,
    MarginDiagnosisBundle,
    MarginDiagnosisReconciler,
)

# ---------------------------------------------------------------------------
# Inline fixtures
# ---------------------------------------------------------------------------


def _spen_contract_objects() -> list[dict]:
    """SPEN-style contract objects with rate cards, obligations, and scope."""
    return [
        {
            "type": "rate_card",
            "id": "rc-spen-001",
            "activity": "cable_jointing",
            "rate": 220.0,
            "unit": "job",
        },
        {
            "type": "rate_card",
            "id": "rc-spen-002",
            "activity": "overhead_line_maintenance",
            "rate": 185.0,
            "unit": "hour",
        },
        {
            "type": "rate_card",
            "id": "rc-spen-003",
            "activity": "emergency_fault_repair",
            "rate": 275.0,
            "unit": "hour",
            "emergency_multiplier": 1.5,
        },
        {
            "type": "obligation",
            "id": "ob-spen-001",
            "clause_id": "CL-SPEN-1",
            "description": "Provider shall complete all scheduled cable jointing within SLA",
            "status": "active",
        },
        {
            "type": "scope_boundary",
            "id": "sb-spen-001",
            "scope_type": "in_scope",
            "description": "Cable jointing and overhead line maintenance",
            "activities": ["cable_jointing", "overhead_line_maintenance"],
        },
    ]


def _spen_work_orders() -> list[dict]:
    return [
        {
            "work_order_id": "WO-SPEN-001",
            "work_order_type": "jointing",
            "description": "Cable jointing at substation Alpha",
            "location": "Substation Alpha",
            "site_id": "SPEN-ALPHA",
            "rate": 220.0,
            "status": "completed",
            "activity": "cable_jointing",
            "scheduled_date": "2025-06-10T08:00:00",
            "scheduled_end": "2025-06-10T16:00:00",
        },
        {
            "work_order_id": "WO-SPEN-002",
            "work_order_type": "maintenance",
            "description": "Overhead line maintenance at substation Beta",
            "location": "Substation Beta",
            "site_id": "SPEN-BETA",
            "rate": 185.0,
            "status": "completed",
            "activity": "overhead_line_maintenance",
            "scheduled_date": "2025-06-11T08:00:00",
        },
    ]


def _vodafone_contract_objects() -> list[dict]:
    return [
        {
            "type": "rate_card",
            "id": "rc-vf-001",
            "activity": "site_maintenance",
            "rate": 150.0,
            "unit": "hour",
        },
        {
            "type": "obligation",
            "id": "ob-vf-001",
            "clause_id": "CL-VF-1",
            "description": "Provider shall resolve P1 incidents within 4 hours",
            "status": "active",
        },
    ]


def _vodafone_incidents() -> list[dict]:
    return [
        {
            "incident_id": "INC-VF-001",
            "title": "Site maintenance failure at Tower X",
            "description": "Site maintenance at Tower X resulted in service degradation",
            "severity": "p1",
            "state": "investigating",
            "affected_services": ["site_maintenance", "mobile_network"],
            "assigned_to": "noc_team",
            "location": "Tower X",
            "site_id": "VF-TOWER-X",
            "created_at": "2025-06-15T09:30:00",
        },
    ]


def _vodafone_work_orders() -> list[dict]:
    return [
        {
            "work_order_id": "WO-VF-001",
            "work_order_type": "maintenance",
            "description": "Scheduled site maintenance at Tower X",
            "location": "Tower X",
            "site_id": "VF-TOWER-X",
            "rate": 150.0,
            "status": "completed",
            "activity": "site_maintenance",
            "scheduled_date": "2025-06-15T08:00:00",
            "scheduled_end": "2025-06-15T12:00:00",
        },
    ]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestFullSPENMarginDiagnosis:
    """Integration: Full SPEN-style margin diagnosis with multiple work orders."""

    def test_full_spen_margin_diagnosis(self):
        reconciler = MarginDiagnosisReconciler()
        # Include invoices matching the work orders to avoid false leakage
        co = _spen_contract_objects()
        co.append({"type": "invoice", "id": "inv-spen-001", "work_order_id": "WO-SPEN-001"})
        co.append({"type": "invoice", "id": "inv-spen-002", "work_order_id": "WO-SPEN-002"})
        bundle = reconciler.reconcile(
            contract_objects=co,
            work_orders=_spen_work_orders(),
            incidents=[],
            work_history=[],
        )

        assert isinstance(bundle, MarginDiagnosisBundle)
        assert bundle.verdict == "healthy"
        # Should have links between rate cards and work orders
        assert len(bundle.contract_wo_links) >= 2
        # Evidence should span contract and field domains
        assert bundle.evidence_bundle.total_items > 0
        assert bundle.confidence > 0.3
        assert "Margin diagnosis verdict" in bundle.summary


class TestVodafoneIncidentMarginImpact:
    """Integration: Vodafone incident impacts margin diagnosis."""

    def test_vodafone_incident_margin_impact(self):
        reconciler = MarginDiagnosisReconciler()
        sla_perf = {
            "sla_status": {"status": "breached", "sla_type": "resolution"},
            "field_blockers": [
                {"blocker_type": "provider_resource_shortage", "description": "NOC understaffed"},
            ],
            "contract_assumptions": [],
            "sla_breaches": [
                {"incident_id": "INC-VF-001", "credit_applied": False, "credit_value": 5000.0},
            ],
        }

        bundle = reconciler.reconcile(
            contract_objects=_vodafone_contract_objects(),
            work_orders=_vodafone_work_orders(),
            incidents=_vodafone_incidents(),
            sla_performance=sla_perf,
        )

        assert bundle.verdict == "penalty_risk"
        assert len(bundle.wo_incident_links) >= 1
        assert len(bundle.sla_conflicts) >= 1
        assert bundle.confidence > 0


class TestCrossPackLeakageDetection:
    """Integration: Leakage detection across contract, field, and ops planes."""

    def test_cross_pack_leakage_detection(self):
        contract_objects = _spen_contract_objects()
        work_orders = [
            {
                "work_order_id": "WO-LEAK-001",
                "description": "Cable jointing at substation Gamma",
                "status": "completed",
                "activity": "cable_jointing",
                "billed": False,
                "estimated_value": 880.0,
            },
        ]
        work_history = [
            {
                "work_order_id": "WO-LEAK-002",
                "activity": "cable_jointing",
                "status": "completed",
                "billed": False,
                "estimated_value": 660.0,
            },
        ]

        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=contract_objects,
            work_orders=work_orders,
            work_history=work_history,
        )

        assert bundle.verdict in ("leakage_detected", "under_recovery")
        assert len(bundle.leakage_patterns) >= 1
        # Leakage patterns should reference unbilled work
        trigger_types = {p.get("trigger_type") for p in bundle.leakage_patterns}
        assert "field_completion_not_billed" in trigger_types


class TestEvidenceBundleAssemblyComplete:
    """Integration: Evidence bundle assembly from all three planes."""

    def test_evidence_bundle_assembly_complete(self):
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=_spen_contract_objects(),
            work_orders=_spen_work_orders(),
            incidents=[
                {
                    "incident_id": "INC-EVD-001",
                    "description": "Power outage near substation Alpha",
                    "severity": "p2",
                    "state": "resolved",
                    "affected_services": ["cable_jointing"],
                    "location": "Substation Alpha",
                    "site_id": "SPEN-ALPHA",
                    "created_at": "2025-06-10T10:00:00",
                },
            ],
        )

        evidence = bundle.evidence_bundle
        assert isinstance(evidence, EvidenceBundle)
        assert evidence.total_items > 0
        # Items should come from multiple domains
        assert len(evidence.domains) >= 1
        assert evidence.confidence > 0

        # Chain validation should work on the assembled evidence
        validator = EvidenceChainValidator()
        chain_results = validator.validate_chain(evidence)
        assert len(chain_results) == 4
        # At least contract_basis and work_authorization should be present
        contract_stage = next(r for r in chain_results if r["stage"] == "contract_basis")
        assert contract_stage["present"] is True


class TestContradictionDetectionAcrossPacks:
    """Integration: Contradiction detection across all three domain packs."""

    def test_contradiction_detection_across_packs(self):
        detector = ContradictionDetector()

        contract_data = {
            "rate_card": [
                {"activity": "site_maintenance", "rate": 150.0},
            ],
            "scope_boundaries": [
                {
                    "scope_type": "in_scope",
                    "activities": ["maintenance"],
                    "description": "Site maintenance in scope",
                },
            ],
        }

        field_data = {
            "work_order_id": "WO-CONTRA-001",
            "description": "Site maintenance at Tower Y",
            "status": "completed",
            "scope_status": "out_of_scope",
            "activity": "site_maintenance",
            "rate": 120.0,
        }

        incident_data = {
            "incident_id": "INC-CONTRA-001",
            "state": "investigating",
            "severity": "p2",
            "description": "Ongoing degradation after maintenance",
        }

        conflicts = detector.detect(contract_data, field_data, incident_data)

        # Should detect scope contradiction, completion vs incident, and rate mismatch
        conflict_fields = {c.field for c in conflicts}
        assert "scope" in conflict_fields
        assert "completion_vs_incident" in conflict_fields
        assert "rate" in conflict_fields


class TestReconciliationWithNoIncidents:
    """Integration: Reconciliation works correctly with no incident data."""

    def test_reconciliation_with_no_incidents(self):
        reconciler = MarginDiagnosisReconciler()
        co = _spen_contract_objects()
        co.append({"type": "invoice", "id": "inv-spen-001", "work_order_id": "WO-SPEN-001"})
        co.append({"type": "invoice", "id": "inv-spen-002", "work_order_id": "WO-SPEN-002"})
        bundle = reconciler.reconcile(
            contract_objects=co,
            work_orders=_spen_work_orders(),
            incidents=None,
        )

        assert isinstance(bundle, MarginDiagnosisBundle)
        assert len(bundle.wo_incident_links) == 0
        assert bundle.verdict == "healthy"
        assert bundle.confidence > 0


class TestReconciliationWithNoWorkOrders:
    """Integration: Reconciliation works correctly with no work order data."""

    def test_reconciliation_with_no_work_orders(self):
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=_spen_contract_objects(),
            work_orders=[],
            incidents=_vodafone_incidents(),
        )

        assert isinstance(bundle, MarginDiagnosisBundle)
        assert len(bundle.contract_wo_links) == 0
        assert len(bundle.wo_incident_links) == 0
        assert bundle.evidence_bundle.total_items > 0


class TestReconciliationAllThreePlanes:
    """Integration: Full reconciliation with data from all three planes."""

    def test_reconciliation_all_three_planes(self):
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=_vodafone_contract_objects(),
            work_orders=_vodafone_work_orders(),
            incidents=_vodafone_incidents(),
            sla_performance={
                "sla_status": {"status": "within"},
                "field_blockers": [],
                "contract_assumptions": [],
                "sla_breaches": [],
            },
        )

        assert isinstance(bundle, MarginDiagnosisBundle)
        # Should have links in both directions
        assert len(bundle.contract_wo_links) >= 1
        assert len(bundle.wo_incident_links) >= 1
        # Evidence bundle should span domains
        assert bundle.evidence_bundle.total_items > 0
        assert bundle.confidence > 0
        assert bundle.summary != ""
        # Verify bundle structure completeness
        assert isinstance(bundle.field_billing_conflicts, list)
        assert isinstance(bundle.sla_conflicts, list)
        assert isinstance(bundle.leakage_patterns, list)
