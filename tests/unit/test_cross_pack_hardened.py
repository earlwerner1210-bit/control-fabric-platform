"""Tests for hardened cross-pack reconciliation (SPEN/Vodafone)."""

from __future__ import annotations

import pytest

from app.domain_packs.reconciliation import (
    CrossPlaneReconciler,
    FieldCompletionBillabilityLinker,
    MarginLeakageReconciler,
    SLAAccountabilityLinker,
    TicketClosureHandoverLinker,
)

# ---------------------------------------------------------------------------
# FieldCompletionBillabilityLinker tests
# ---------------------------------------------------------------------------


class TestFieldCompletionBillability:
    """Tests for the FieldCompletionBillabilityLinker."""

    def test_field_completion_billability_all_satisfied(self):
        """Complete + all gates satisfied -> billable."""
        linker = FieldCompletionBillabilityLinker()
        work_order = {
            "work_order_id": "WO-001",
            "category": "standard",
            "required_evidence_types": ["after_photo", "test_certificate"],
        }
        completion_evidence = [
            {"evidence_type": "after_photo", "provided": True},
            {"evidence_type": "test_certificate", "provided": True},
        ]
        billing_gates = [
            {"gate_type": "completion_certificate", "satisfied": True},
            {"gate_type": "purchase_order", "satisfied": True},
        ]

        result = linker.evaluate(work_order, completion_evidence, billing_gates)

        assert result["billable"] is True
        assert len(result["blockers"]) == 0
        assert len(result["leakage_triggers"]) == 0

    def test_field_completion_missing_evidence_non_billable(self):
        """Missing test cert -> non-billable."""
        linker = FieldCompletionBillabilityLinker()
        work_order = {
            "work_order_id": "WO-002",
            "category": "standard",
            "required_evidence_types": ["after_photo", "test_certificate", "safety_documentation"],
        }
        completion_evidence = [
            {"evidence_type": "after_photo", "provided": True},
            {"evidence_type": "safety_documentation", "provided": True},
            # test_certificate missing
        ]
        billing_gates = [
            {"gate_type": "purchase_order", "satisfied": True},
        ]

        result = linker.evaluate(work_order, completion_evidence, billing_gates)

        assert result["billable"] is False
        assert any(b["rule"] == "missing_completion_evidence" for b in result["blockers"])
        assert any(
            t["trigger_type"] == "incomplete_evidence_prevents_billing"
            for t in result["leakage_triggers"]
        )

    def test_field_reattendance_provider_fault_leakage(self):
        """Provider rework billed -> leakage trigger."""
        linker = FieldCompletionBillabilityLinker()
        work_order = {
            "work_order_id": "WO-003",
            "category": "standard",
            "required_evidence_types": [],
        }
        completion_evidence = []
        billing_gates = []
        reattendance_info = {"trigger": "provider_fault", "billed": True}

        result = linker.evaluate(work_order, completion_evidence, billing_gates, reattendance_info)

        assert result["billable"] is False
        assert any(b["rule"] == "reattendance_provider_fault" for b in result["blockers"])
        # When billed=True, it should flag a leakage trigger
        assert any(
            t["trigger_type"] == "reattendance_incorrectly_billed"
            for t in result["leakage_triggers"]
        )


# ---------------------------------------------------------------------------
# TicketClosureHandoverLinker tests
# ---------------------------------------------------------------------------


class TestTicketClosureHandover:
    """Tests for the TicketClosureHandoverLinker."""

    def test_ticket_closure_field_incomplete(self):
        """Ticket resolved but field evidence missing -> cannot close."""
        linker = TicketClosureHandoverLinker()
        incident = {
            "incident_id": "INC-001",
            "severity": "p3",
            "state": "resolved",
        }
        work_order = {"status": "completed"}
        completion_evidence = [
            # All provided=False
            {"evidence_type": "test_certificate", "provided": False},
            {"evidence_type": "after_photo", "provided": False},
        ]
        closure_gates = []

        result = linker.evaluate(incident, work_order, completion_evidence, closure_gates)

        assert result["can_close"] is False
        assert any(b["rule"] == "missing_completion_evidence" for b in result["blockers"])

    def test_ticket_closure_open_permits(self):
        """Open NRSWA permit -> cannot close."""
        linker = TicketClosureHandoverLinker()
        incident = {
            "incident_id": "INC-002",
            "severity": "p3",
            "state": "resolved",
        }
        work_order = {"status": "completed"}
        completion_evidence = [
            {"evidence_type": "after_photo", "provided": True},
        ]
        closure_gates = [
            {"prerequisite": "permit_closed_out", "satisfied": False, "mandatory": True},
        ]

        result = linker.evaluate(incident, work_order, completion_evidence, closure_gates)

        assert result["can_close"] is False
        assert any(b["rule"] == "open_permits" for b in result["blockers"])


# ---------------------------------------------------------------------------
# SLAAccountabilityLinker tests
# ---------------------------------------------------------------------------


class TestSLAAccountability:
    """Tests for the SLAAccountabilityLinker."""

    def test_sla_accountability_customer_access_blocker(self):
        """Customer access issue -> SLA paused, not accountable."""
        linker = SLAAccountabilityLinker()
        sla_status = {"status": "warning", "elapsed_minutes": 50}
        field_blockers = [
            {
                "blocker_type": "customer_access",
                "description": "Customer did not provide site access",
            }
        ]
        contract_assumptions = []

        result = linker.evaluate(sla_status, field_blockers, contract_assumptions)

        assert result["accountable"] is False
        assert result["adjusted_sla_status"] == "paused"
        assert len(result["mitigation_factors"]) == 1
        assert result["mitigation_factors"][0]["blocker_type"] == "customer_access"

    def test_sla_accountability_provider_resource(self):
        """Provider shortage -> fully accountable."""
        linker = SLAAccountabilityLinker()
        sla_status = {"status": "breached"}
        field_blockers = [
            {
                "blocker_type": "provider_resource_shortage",
                "description": "No engineer available in region",
            }
        ]
        contract_assumptions = []

        result = linker.evaluate(sla_status, field_blockers, contract_assumptions)

        assert result["accountable"] is True
        # No mitigation for provider resource shortage
        assert len(result["mitigation_factors"]) == 0


# ---------------------------------------------------------------------------
# MarginLeakageReconciler tests
# ---------------------------------------------------------------------------


class TestMarginLeakageReconciler:
    """Tests for the MarginLeakageReconciler."""

    def test_margin_leakage_abortive_not_claimed(self):
        """Abortive visit unclaimed -> leakage."""
        reconciler = MarginLeakageReconciler()
        contract_data = {"invoices": [], "rate_card": []}
        field_data = {
            "work_orders": [
                {
                    "work_order_id": "WO-ABT-001",
                    "status": "completed",
                    "activity": "lv_fault_repair",
                    "abortive": True,
                    "abortive_claimed": False,
                    "abortive_value": 85.0,
                },
            ]
        }
        ops_data = {"sla_breaches": []}

        result = reconciler.reconcile(contract_data, field_data, ops_data)

        trigger_types = [t["trigger_type"] for t in result["leakage_triggers"]]
        assert "abortive_visit_not_claimed" in trigger_types
        assert result["total_at_risk_value"] >= 85.0

    def test_margin_leakage_emergency_base_rate(self):
        """Emergency at base rate -> leakage."""
        reconciler = MarginLeakageReconciler()
        contract_data = {
            "invoices": [
                {"work_order_id": "WO-EM-001"},
            ],
            "rate_card": [
                {"activity": "lv_fault_repair", "rate": 125.0, "emergency_multiplier": 1.5},
            ],
        }
        field_data = {
            "work_orders": [
                {
                    "work_order_id": "WO-EM-001",
                    "status": "completed",
                    "activity": "lv_fault_repair",
                    "is_emergency": True,
                    "billed_rate": 125.0,  # Should be 187.50
                    "value": 125.0,
                },
            ]
        }
        ops_data = {"sla_breaches": []}

        result = reconciler.reconcile(contract_data, field_data, ops_data)

        trigger_types = [t["trigger_type"] for t in result["leakage_triggers"]]
        assert "emergency_billed_at_base_rate" in trigger_types
        # The difference should be 187.50 - 125.0 = 62.50
        emergency_trigger = next(
            t
            for t in result["leakage_triggers"]
            if t["trigger_type"] == "emergency_billed_at_base_rate"
        )
        assert emergency_trigger["at_risk_value"] == pytest.approx(62.50, abs=0.01)

    def test_margin_leakage_permit_cost_absorbed(self):
        """NRSWA cost not recovered -> leakage."""
        reconciler = MarginLeakageReconciler()
        contract_data = {"invoices": [], "rate_card": []}
        field_data = {
            "work_orders": [
                {
                    "work_order_id": "WO-PER-001",
                    "status": "completed",
                    "activity": "civils_excavation",
                    "permit_cost": 350.0,
                    "permit_cost_recovered": False,
                    "value": 2200.0,
                },
            ]
        }
        ops_data = {"sla_breaches": []}

        result = reconciler.reconcile(contract_data, field_data, ops_data)

        trigger_types = [t["trigger_type"] for t in result["leakage_triggers"]]
        assert "permit_cost_not_recovered" in trigger_types
        assert result["total_at_risk_value"] >= 350.0


# ---------------------------------------------------------------------------
# Full end-to-end reconciliation test
# ---------------------------------------------------------------------------


class TestFullReconciliation:
    """End-to-end cross-pack reconciliation test."""

    def test_full_reconciliation_spen_vodafone(self):
        """End-to-end reconciliation with all three planes: contract, field, ops."""
        # --- Contract plane (SPEN rate card) ---
        contract_data = {
            "rate_card": [
                {"activity": "cable_jointing", "rate": 850.0, "unit": "each"},
                {"activity": "lv_fault_repair", "rate": 125.0, "unit": "hour"},
            ],
            "obligations": [
                {
                    "clause_id": "CL-SPEN-001",
                    "description": "Provider shall perform all cable jointing works",
                    "status": "active",
                    "due_type": "ongoing",
                },
            ],
            "scope_boundaries": [
                {
                    "scope_type": "in_scope",
                    "description": "All cable jointing and LV fault repair",
                    "activities": ["cable", "jointing", "fault", "repair"],
                },
            ],
            "invoices": [
                {"work_order_id": "WO-SPEN-CJ-001"},
            ],
        }

        # --- Field plane (work order with completion state) ---
        field_data = {
            "work_orders": [
                {
                    "work_order_id": "WO-SPEN-CJ-001",
                    "status": "completed",
                    "activity": "cable_jointing",
                    "description": "11kV cable jointing at substation Alpha",
                    "location": "Edinburgh North",
                    "site_id": "SITE-EDN-001",
                    "scheduled_date": "2026-03-20T08:00:00",
                    "value": 850.0,
                },
            ],
        }

        # --- Ops plane (Vodafone incident) ---
        ops_data = {
            "sla_breaches": [],
        }

        # Run full three-plane reconciliation
        reconciler = CrossPlaneReconciler()
        wo_data = field_data["work_orders"][0]
        incident_data = {
            "incident_id": "INC-VF-001",
            "title": "Power fault at substation Alpha",
            "description": "Reported power issue at Edinburgh North substation",
            "severity": "p2",
            "state": "resolved",
            "affected_services": ["power_distribution"],
            "location": "Edinburgh North",
            "site_id": "SITE-EDN-001",
            "created_at": "2026-03-20T09:00:00",
        }

        result = reconciler.full_reconciliation(contract_data, wo_data, incident_data)

        # Verify structure
        assert "all_links" in result
        assert "all_conflicts" in result
        assert "aggregate_evidence" in result
        assert "contract_to_wo" in result
        assert "wo_to_incident" in result

        # Verify evidence bundle has items from multiple domains
        agg = result["aggregate_evidence"]
        assert agg["total_items"] > 0
        assert len(agg["domains"]) >= 1

        # Run margin leakage reconciler on top
        margin_reconciler = MarginLeakageReconciler()
        leakage_result = margin_reconciler.reconcile(contract_data, field_data, ops_data)

        # WO-SPEN-CJ-001 is invoiced, so no field_completion_not_billed trigger
        billed_triggers = [
            t
            for t in leakage_result["leakage_triggers"]
            if t["trigger_type"] == "field_completion_not_billed"
        ]
        assert len(billed_triggers) == 0

        # Run field completion billability
        billability_linker = FieldCompletionBillabilityLinker()
        bill_result = billability_linker.evaluate(
            wo_data,
            completion_evidence=[
                {"evidence_type": "test_certificate", "provided": True},
                {"evidence_type": "after_photo", "provided": True},
            ],
            billing_gates=[
                {"gate_type": "completion_certificate", "satisfied": True},
            ],
        )
        assert bill_result["billable"] is True

        # Run SLA accountability check (no blockers = accountable)
        sla_linker = SLAAccountabilityLinker()
        sla_result = sla_linker.evaluate(
            sla_status={"status": "within"},
            field_blockers=[],
            contract_assumptions=[],
        )
        assert sla_result["accountable"] is True
        assert sla_result["adjusted_sla_status"] == "within"

        # Run ticket closure check
        closure_linker = TicketClosureHandoverLinker()
        closure_result = closure_linker.evaluate(
            incident=incident_data,
            work_order=wo_data,
            completion_evidence=[
                {"evidence_type": "test_certificate", "provided": True},
            ],
            closure_gates=[
                {"prerequisite": "rca_submitted", "satisfied": True},
                {"prerequisite": "service_restored", "satisfied": True},
            ],
        )
        assert closure_result["can_close"] is True
        assert len(closure_result["blockers"]) == 0
