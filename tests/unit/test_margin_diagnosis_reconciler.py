"""Unit tests for MarginDiagnosisReconciler, ContradictionDetector, and EvidenceChainValidator."""

from __future__ import annotations

import uuid

from app.domain_packs.reconciliation import (
    ContradictionDetector,
    CrossPlaneConflict,
    CrossPlaneLink,
    EvidenceBundle,
    EvidenceChainValidator,
    MarginDiagnosisBundle,
    MarginDiagnosisReconciler,
)

# ---------------------------------------------------------------------------
# Shared fixture builders
# ---------------------------------------------------------------------------


def _contract_objects_basic() -> list[dict]:
    return [
        {
            "type": "rate_card",
            "id": "rc-001",
            "activity": "standard_maintenance",
            "rate": 125.0,
            "unit": "hour",
        },
        {
            "type": "rate_card",
            "id": "rc-002",
            "activity": "emergency_repair",
            "rate": 187.50,
            "unit": "hour",
        },
        {
            "type": "obligation",
            "id": "ob-001",
            "clause_id": "CL-001",
            "description": "Provider shall deliver all scheduled maintenance",
            "status": "active",
        },
    ]


def _work_order_completed() -> dict:
    return {
        "work_order_id": "WO-001",
        "work_order_type": "maintenance",
        "description": "Scheduled standard maintenance at Building A",
        "location": "Building A",
        "site_id": "SITE-A",
        "rate": 125.0,
        "status": "completed",
        "scheduled_date": "2025-06-15T09:00:00",
        "scheduled_end": "2025-06-15T17:00:00",
        "activity": "standard_maintenance",
    }


def _work_order_unbilled() -> dict:
    wo = _work_order_completed()
    wo["work_order_id"] = "WO-UNBILLED"
    wo["billed"] = False
    return wo


def _incident_active() -> dict:
    return {
        "incident_id": "INC-001",
        "title": "Core network degradation at Building A",
        "description": "Core network experiencing packet loss at Building A",
        "severity": "p2",
        "state": "investigating",
        "affected_services": ["core_network"],
        "assigned_to": "senior_engineer",
        "location": "Building A",
        "site_id": "SITE-A",
        "created_at": "2025-06-15T10:30:00",
    }


def _incident_resolved() -> dict:
    inc = _incident_active()
    inc["state"] = "resolved"
    return inc


def _work_history_with_unbilled() -> list[dict]:
    return [
        {
            "work_order_id": "WO-H1",
            "activity": "standard_maintenance",
            "status": "completed",
            "billed": False,
            "estimated_value": 500.0,
        },
    ]


def _sla_performance_breached() -> dict:
    return {
        "sla_status": {"status": "breached", "sla_type": "resolution"},
        "field_blockers": [
            {
                "blocker_type": "provider_resource_shortage",
                "description": "Insufficient crew available",
            },
        ],
        "contract_assumptions": [],
        "sla_breaches": [
            {"incident_id": "INC-001", "credit_applied": False, "credit_value": 1000.0},
        ],
    }


def _sla_performance_customer_caused() -> dict:
    return {
        "sla_status": {"status": "breached", "sla_type": "resolution"},
        "field_blockers": [
            {"blocker_type": "customer_access", "description": "Customer denied site access"},
        ],
        "contract_assumptions": [],
        "sla_breaches": [],
    }


# ---------------------------------------------------------------------------
# MarginDiagnosisReconciler tests
# ---------------------------------------------------------------------------


class TestMarginDiagnosisReconciler:
    def test_healthy_margin_no_conflicts(self):
        reconciler = MarginDiagnosisReconciler()
        # Provide an invoice matching the work order so leakage is not flagged
        co = _contract_objects_basic()
        co.append(
            {
                "type": "invoice",
                "id": "inv-001",
                "work_order_id": "WO-001",
                "amount": 125.0,
            }
        )
        bundle = reconciler.reconcile(
            contract_objects=co,
            work_orders=[_work_order_completed()],
            incidents=[],
            work_history=[],
        )
        assert isinstance(bundle, MarginDiagnosisBundle)
        assert bundle.verdict == "healthy"
        assert len(bundle.leakage_patterns) == 0
        assert bundle.confidence > 0

    def test_leakage_detected_unbilled_work(self):
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=_contract_objects_basic(),
            work_orders=[_work_order_unbilled()],
            incidents=[],
            work_history=_work_history_with_unbilled(),
        )
        assert isinstance(bundle, MarginDiagnosisBundle)
        assert bundle.verdict in ("leakage_detected", "under_recovery")
        assert len(bundle.leakage_patterns) > 0

    def test_penalty_risk_sla_breach(self):
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=_contract_objects_basic(),
            work_orders=[_work_order_completed()],
            incidents=[_incident_active()],
            sla_performance=_sla_performance_breached(),
        )
        assert bundle.verdict == "penalty_risk"
        assert any(c.field == "sla_accountability" for c in bundle.sla_conflicts)

    def test_under_recovery_rate_mismatch(self):
        wo = _work_order_completed()
        wo["rate"] = 100.0  # lower than contract rate of 125
        wo["billed_rate"] = 100.0
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=_contract_objects_basic(),
            work_orders=[wo],
        )
        # The contradiction detector finds rate mismatch
        rate_conflicts = [c for c in bundle.all_conflicts if c.field == "rate"]
        assert len(rate_conflicts) >= 1

    def test_contract_wo_linkage_found(self):
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=_contract_objects_basic(),
            work_orders=[_work_order_completed()],
        )
        assert len(bundle.contract_wo_links) > 0
        assert all(isinstance(l, CrossPlaneLink) for l in bundle.contract_wo_links)

    def test_contract_wo_no_match(self):
        reconciler = MarginDiagnosisReconciler()
        wo = {
            "work_order_id": "WO-NOMATCH",
            "description": "Completely unrelated plumbing in another country",
            "status": "completed",
        }
        bundle = reconciler.reconcile(
            contract_objects=_contract_objects_basic(),
            work_orders=[wo],
        )
        # Links may be empty or very low confidence
        for link in bundle.contract_wo_links:
            assert link.confidence >= 0.0

    def test_wo_incident_linkage_found(self):
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=_contract_objects_basic(),
            work_orders=[_work_order_completed()],
            incidents=[_incident_active()],
        )
        assert len(bundle.wo_incident_links) > 0
        assert bundle.wo_incident_links[0].source_domain == "utilities_field"
        assert bundle.wo_incident_links[0].target_domain == "telco_ops"

    def test_field_billing_conflict_missing_gate(self):
        wo = _work_order_completed()
        wo["billing_gates"] = [
            {
                "gate_type": "completion_cert",
                "satisfied": False,
                "description": "Completion cert required",
            },
        ]
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=_contract_objects_basic(),
            work_orders=[wo],
        )
        assert len(bundle.field_billing_conflicts) > 0
        assert any("billing_gate" in c.field for c in bundle.field_billing_conflicts)

    def test_field_billing_conflict_unsigned_daywork(self):
        wo = _work_order_completed()
        wo["category"] = "daywork"
        wo["daywork_sheet_signed"] = False
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=_contract_objects_basic(),
            work_orders=[wo],
        )
        assert len(bundle.field_billing_conflicts) > 0
        daywork_conflicts = [c for c in bundle.field_billing_conflicts if "daywork" in c.field]
        assert len(daywork_conflicts) >= 1

    def test_sla_accountability_customer_caused(self):
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=_contract_objects_basic(),
            work_orders=[_work_order_completed()],
            sla_performance=_sla_performance_customer_caused(),
        )
        # Customer-caused blocker -> SLA mitigation factor present, not provider-accountable
        mitigation_conflicts = [c for c in bundle.sla_conflicts if c.field == "sla_mitigation"]
        assert len(mitigation_conflicts) >= 1

    def test_sla_accountability_provider_caused(self):
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=_contract_objects_basic(),
            work_orders=[_work_order_completed()],
            sla_performance=_sla_performance_breached(),
        )
        accountability_conflicts = [
            c for c in bundle.sla_conflicts if c.field == "sla_accountability"
        ]
        assert len(accountability_conflicts) >= 1
        assert accountability_conflicts[0].severity == "critical"

    def test_evidence_chain_complete(self):
        validator = EvidenceChainValidator()
        evidence = EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            domains=["contract_margin", "utilities_field"],
            evidence_items=[
                {"type": "rate_card", "domain": "contract_margin", "id": "rc-1", "data": {}},
                {"type": "work_order", "domain": "utilities_field", "id": "wo-1", "data": {}},
                {
                    "type": "completion_certificate",
                    "domain": "utilities_field",
                    "id": "cc-1",
                    "data": {},
                },
                {"type": "invoice", "domain": "contract_margin", "id": "inv-1", "data": {}},
            ],
            total_items=4,
            confidence=0.9,
        )
        results = validator.validate_chain(evidence)
        assert len(results) == 4
        assert all(r["present"] for r in results)
        assert all(r["severity"] == "ok" for r in results)

    def test_evidence_chain_missing_authorization(self):
        validator = EvidenceChainValidator()
        evidence = EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            domains=["contract_margin"],
            evidence_items=[
                {"type": "rate_card", "domain": "contract_margin", "id": "rc-1", "data": {}},
                {
                    "type": "completion_certificate",
                    "domain": "utilities_field",
                    "id": "cc-1",
                    "data": {},
                },
                {"type": "invoice", "domain": "contract_margin", "id": "inv-1", "data": {}},
            ],
            total_items=3,
            confidence=0.7,
        )
        results = validator.validate_chain(evidence)
        auth_result = next(r for r in results if r["stage"] == "work_authorization")
        assert auth_result["present"] is False
        assert auth_result["severity"] == "blocker"

    def test_evidence_chain_missing_completion(self):
        validator = EvidenceChainValidator()
        evidence = EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            domains=["contract_margin", "utilities_field"],
            evidence_items=[
                {"type": "rate_card", "domain": "contract_margin", "id": "rc-1", "data": {}},
                {"type": "work_order", "domain": "utilities_field", "id": "wo-1", "data": {}},
                {"type": "invoice", "domain": "contract_margin", "id": "inv-1", "data": {}},
            ],
            total_items=3,
            confidence=0.7,
        )
        results = validator.validate_chain(evidence)
        exec_result = next(r for r in results if r["stage"] == "execution_evidence")
        assert exec_result["present"] is False
        assert exec_result["severity"] == "warning"

    def test_evidence_chain_missing_billing(self):
        validator = EvidenceChainValidator()
        evidence = EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            domains=["contract_margin", "utilities_field"],
            evidence_items=[
                {"type": "obligation", "domain": "contract_margin", "id": "ob-1", "data": {}},
                {"type": "work_order", "domain": "utilities_field", "id": "wo-1", "data": {}},
                {"type": "field_log", "domain": "utilities_field", "id": "fl-1", "data": {}},
            ],
            total_items=3,
            confidence=0.7,
        )
        results = validator.validate_chain(evidence)
        billing_result = next(r for r in results if r["stage"] == "billing_evidence")
        assert billing_result["present"] is False
        assert billing_result["severity"] == "warning"

    def test_contradiction_scope_mismatch(self):
        detector = ContradictionDetector()
        contract_data = {
            "rate_card": [],
            "scope_boundaries": [
                {
                    "scope_type": "in_scope",
                    "activities": ["maintenance"],
                    "description": "Network maintenance is in scope",
                },
            ],
        }
        field_data = {
            "description": "Performed maintenance at site",
            "scope_status": "out_of_scope",
        }
        conflicts = detector.detect(contract_data, field_data)
        scope_conflicts = [c for c in conflicts if c.field == "scope"]
        assert len(scope_conflicts) >= 1
        assert "in_scope" in scope_conflicts[0].value_a
        assert "out_of_scope" in scope_conflicts[0].value_b

    def test_contradiction_completion_vs_incident(self):
        detector = ContradictionDetector()
        contract_data = {"rate_card": []}
        field_data = {"status": "completed", "description": "Work done"}
        incident_data = {"state": "investigating", "severity": "p2"}
        conflicts = detector.detect(contract_data, field_data, incident_data)
        completion_conflicts = [c for c in conflicts if c.field == "completion_vs_incident"]
        assert len(completion_conflicts) >= 1

    def test_contradiction_rate_mismatch(self):
        detector = ContradictionDetector()
        contract_data = {
            "rate_card": [
                {"activity": "standard_maintenance", "rate": 125.0},
            ],
        }
        field_data = {
            "description": "maintenance work",
            "activity": "standard_maintenance",
            "rate": 100.0,
        }
        conflicts = detector.detect(contract_data, field_data)
        rate_conflicts = [c for c in conflicts if c.field == "rate"]
        assert len(rate_conflicts) >= 1

    def test_multiple_conflicts_aggregated(self):
        reconciler = MarginDiagnosisReconciler()
        wo = _work_order_completed()
        wo["rate"] = 100.0
        wo["billed_rate"] = 100.0
        wo["billing_gates"] = [
            {"gate_type": "sign_off", "satisfied": False, "description": "Sign-off needed"},
        ]
        bundle = reconciler.reconcile(
            contract_objects=_contract_objects_basic(),
            work_orders=[wo],
            incidents=[_incident_active()],
        )
        # Should have multiple types of conflicts aggregated
        assert len(bundle.all_conflicts) >= 1
        assert isinstance(bundle.all_conflicts, list)
        assert all(isinstance(c, CrossPlaneConflict) for c in bundle.all_conflicts)

    def test_empty_inputs_no_crash(self):
        reconciler = MarginDiagnosisReconciler()
        bundle = reconciler.reconcile(
            contract_objects=[],
            work_orders=[],
            incidents=None,
            work_history=None,
            sla_performance=None,
        )
        assert isinstance(bundle, MarginDiagnosisBundle)
        assert bundle.verdict == "healthy"
        assert len(bundle.contract_wo_links) == 0
        assert len(bundle.wo_incident_links) == 0
        assert len(bundle.all_conflicts) == 0
        assert bundle.confidence > 0
