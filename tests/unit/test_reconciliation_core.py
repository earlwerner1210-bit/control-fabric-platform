"""Tests for reconciliation engine — mismatch detection, scoring, evidence bundles."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.control_link import ControlLinkCreate
from app.core.control_object import ControlObjectCreate
from app.core.graph.service import GraphService
from app.core.reconciliation.engine import ReconciliationEngine
from app.core.reconciliation.rules import (
    BillingWithoutCompletionRule,
    MissingEvidenceRule,
    ObligationUnmetRule,
    QuantityDiscrepancyRule,
    RateDeviationRule,
    ScopeMatchRule,
)
from app.core.reconciliation.scoring import score_mismatches
from app.core.reconciliation.types import (
    Mismatch,
    MismatchCategory,
    MismatchSeverity,
    ReconciliationStatus,
)
from app.core.types import (
    AuditContext,
    ControlLinkType,
    ControlObjectId,
    ControlObjectType,
    ControlState,
    EvidenceRef,
    PlaneType,
)

TENANT = uuid.uuid4()
AUDIT = AuditContext(actor="test", action="test", timestamp=datetime.now(UTC))


def _obj_create(label: str, plane: PlaneType, domain: str = "test", payload: dict = None):
    return ControlObjectCreate(
        object_type=ControlObjectType.OBLIGATION,
        plane=plane,
        domain=domain,
        label=label,
        payload=payload or {},
    )


class TestReconciliationRules:
    def test_rate_deviation_detected(self):
        svc = GraphService()
        src = svc.create_object(
            TENANT, _obj_create("Src", PlaneType.COMMERCIAL, payload={"rate": 100.0})
        )
        tgt = svc.create_object(
            TENANT, _obj_create("Tgt", PlaneType.FIELD, payload={"rate": 120.0})
        )
        rule = RateDeviationRule()
        mismatches = rule.evaluate(src, tgt)
        assert len(mismatches) == 1
        assert mismatches[0].category == MismatchCategory.RATE_DEVIATION
        assert mismatches[0].deviation == 20.0

    def test_rate_deviation_within_threshold(self):
        svc = GraphService()
        src = svc.create_object(
            TENANT, _obj_create("Src", PlaneType.COMMERCIAL, payload={"rate": 100.0})
        )
        tgt = svc.create_object(
            TENANT, _obj_create("Tgt", PlaneType.FIELD, payload={"rate": 100.005})
        )
        rule = RateDeviationRule()
        mismatches = rule.evaluate(src, tgt)
        assert len(mismatches) == 0

    def test_quantity_discrepancy(self):
        svc = GraphService()
        src = svc.create_object(
            TENANT, _obj_create("Src", PlaneType.COMMERCIAL, payload={"quantity": 10})
        )
        tgt = svc.create_object(
            TENANT, _obj_create("Tgt", PlaneType.FIELD, payload={"quantity": 8})
        )
        rule = QuantityDiscrepancyRule()
        mismatches = rule.evaluate(src, tgt)
        assert len(mismatches) == 1
        assert mismatches[0].category == MismatchCategory.QUANTITY_DISCREPANCY

    def test_obligation_unmet(self):
        svc = GraphService()
        src = svc.create_object(
            TENANT,
            _obj_create("Obligation", PlaneType.COMMERCIAL, payload={"obligation_status": "unmet"}),
        )
        tgt = svc.create_object(TENANT, _obj_create("WO", PlaneType.FIELD))
        rule = ObligationUnmetRule()
        mismatches = rule.evaluate(src, tgt)
        assert len(mismatches) == 1

    def test_scope_mismatch(self):
        svc = GraphService()
        src = svc.create_object(
            TENANT, _obj_create("Src", PlaneType.COMMERCIAL, payload={"scope": "regional"})
        )
        tgt = svc.create_object(
            TENANT, _obj_create("Tgt", PlaneType.FIELD, payload={"scope": "national"})
        )
        rule = ScopeMatchRule()
        mismatches = rule.evaluate(src, tgt)
        assert len(mismatches) == 1

    def test_billing_without_completion(self):
        svc = GraphService()
        src = svc.create_object(
            TENANT, _obj_create("Bill", PlaneType.COMMERCIAL, payload={"is_billed": True})
        )
        tgt = svc.create_object(
            TENANT, _obj_create("WO", PlaneType.FIELD, payload={"is_completed": False})
        )
        rule = BillingWithoutCompletionRule()
        mismatches = rule.evaluate(src, tgt)
        assert len(mismatches) == 1
        assert mismatches[0].severity == MismatchSeverity.CRITICAL

    def test_no_mismatch_when_clean(self):
        svc = GraphService()
        src = svc.create_object(
            TENANT, _obj_create("Src", PlaneType.COMMERCIAL, payload={"rate": 100})
        )
        tgt = svc.create_object(TENANT, _obj_create("Tgt", PlaneType.FIELD, payload={"rate": 100}))
        rule = RateDeviationRule()
        assert rule.evaluate(src, tgt) == []


class TestReconciliationScoring:
    def test_clean_score(self):
        score = score_mismatches([])
        assert score.is_clean
        assert score.overall_score == 1.0

    def test_critical_mismatch_lowers_score(self):
        m = Mismatch(
            category=MismatchCategory.BILLING_WITHOUT_COMPLETION,
            severity=MismatchSeverity.CRITICAL,
            source_object_id=ControlObjectId(uuid.uuid4()),
            target_object_id=ControlObjectId(uuid.uuid4()),
            source_plane=PlaneType.COMMERCIAL,
            target_plane=PlaneType.FIELD,
            description="test",
        )
        score = score_mismatches([m])
        assert score.overall_score < 1.0
        assert score.has_critical
        assert score.critical_count == 1

    def test_multiple_mismatches(self):
        mismatches = [
            Mismatch(
                category=MismatchCategory.RATE_DEVIATION,
                severity=MismatchSeverity.HIGH,
                source_object_id=ControlObjectId(uuid.uuid4()),
                target_object_id=ControlObjectId(uuid.uuid4()),
                source_plane=PlaneType.COMMERCIAL,
                target_plane=PlaneType.FIELD,
                description="rate",
                metadata={"financial_impact": 50.0},
            ),
            Mismatch(
                category=MismatchCategory.SCOPE_MISMATCH,
                severity=MismatchSeverity.MEDIUM,
                source_object_id=ControlObjectId(uuid.uuid4()),
                target_object_id=ControlObjectId(uuid.uuid4()),
                source_plane=PlaneType.COMMERCIAL,
                target_plane=PlaneType.FIELD,
                description="scope",
            ),
        ]
        score = score_mismatches(mismatches)
        assert score.mismatch_count == 2
        assert score.financial_impact_total == 50.0


class TestReconciliationEngine:
    def test_cross_plane_reconciliation(self):
        svc = GraphService()
        src = svc.create_object(
            TENANT, _obj_create("Contract Rate", PlaneType.COMMERCIAL, "test", {"rate": 100})
        )
        tgt = svc.create_object(
            TENANT, _obj_create("Field Rate", PlaneType.FIELD, "test", {"rate": 150})
        )
        # Freeze objects
        svc.freeze_object(src.id)
        svc.freeze_object(tgt.id)
        # Create cross-plane link
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=src.id, target_id=tgt.id, link_type=ControlLinkType.FULFILLS
            ),
        )
        engine = ReconciliationEngine(svc)
        result = engine.reconcile_cross_plane(TENANT, PlaneType.COMMERCIAL, PlaneType.FIELD, "test")
        assert result.status == ReconciliationStatus.COMPLETED
        assert result.score.mismatch_count >= 1
        assert result.decision_hash != ""

    def test_correlation_key_pairing(self):
        svc = GraphService()
        src = svc.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.COMMERCIAL,
                domain="test",
                label="Contract Item",
                payload={"rate": 100},
                correlation_keys={"contract_ref": "ABC-123"},
            ),
        )
        tgt = svc.create_object(
            TENANT,
            ControlObjectCreate(
                object_type=ControlObjectType.OBLIGATION,
                plane=PlaneType.FIELD,
                domain="test",
                label="Work Item",
                payload={"rate": 200},
                correlation_keys={"contract_ref": "ABC-123"},
            ),
        )
        svc.freeze_object(src.id)
        svc.freeze_object(tgt.id)
        engine = ReconciliationEngine(svc)
        result = engine.reconcile_cross_plane(TENANT, PlaneType.COMMERCIAL, PlaneType.FIELD, "test")
        assert result.score.mismatch_count >= 1

    def test_reconciliation_hash_is_deterministic(self):
        svc = GraphService()
        src = svc.create_object(TENANT, _obj_create("A", PlaneType.COMMERCIAL, "d", {"rate": 10}))
        tgt = svc.create_object(TENANT, _obj_create("B", PlaneType.FIELD, "d", {"rate": 20}))
        svc.freeze_object(src.id)
        svc.freeze_object(tgt.id)
        svc.create_link(
            TENANT,
            ControlLinkCreate(
                source_id=src.id, target_id=tgt.id, link_type=ControlLinkType.FULFILLS
            ),
        )
        engine = ReconciliationEngine(svc)
        r1 = engine.reconcile_cross_plane(TENANT, PlaneType.COMMERCIAL, PlaneType.FIELD, "d")
        # Run again on fresh engine but same data
        engine2 = ReconciliationEngine(svc)
        r2 = engine2.reconcile_cross_plane(TENANT, PlaneType.COMMERCIAL, PlaneType.FIELD, "d")
        assert r1.decision_hash == r2.decision_hash
