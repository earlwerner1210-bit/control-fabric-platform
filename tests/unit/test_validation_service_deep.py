"""Deep tests for ValidationService – billability, margin diagnosis, reconciliation."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models.validation import ValidationResult, ValidationStatus
from app.services.validation.service import ValidationService


@pytest.fixture
def mock_db():
    """Create a mock async DB session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def svc(mock_db):
    return ValidationService(mock_db)


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def case_id():
    return uuid.uuid4()


# ── Billability Decision Tests ──────────────────────────────────


class TestValidateBillabilityDecisionValid:
    @pytest.mark.asyncio
    async def test_validate_billability_decision_valid(self, svc, tenant_id, case_id):
        """A fully valid billable decision should produce passed status."""
        decision = {
            "billable": True,
            "rate_applied": 150.0,
            "reasons": ["Rate card matched", "Within SLA"],
            "confidence": 0.85,
            "category": "time_and_materials",
            "rule_results": [
                {"rule_name": "has_valid_rate", "passed": True, "severity": "info"},
                {"rule_name": "sla_compliance", "passed": True, "severity": "info"},
            ],
        }
        result = await svc.validate_billability_decision(tenant_id, case_id, decision)

        assert isinstance(result, ValidationResult)
        assert result.status == ValidationStatus.passed
        assert result.validator_name == "contract_margin_billability_validator"
        assert result.domain == "contract_margin"
        svc.db.add.assert_called_once()
        svc.db.flush.assert_awaited_once()


class TestValidateBillabilityMissingRate:
    @pytest.mark.asyncio
    async def test_validate_billability_missing_rate(self, svc, tenant_id, case_id):
        """Billable=True with no rate_applied should fail."""
        decision = {
            "billable": True,
            "rate_applied": None,
            "reasons": ["Some reason"],
            "confidence": 0.7,
            "category": "fixed_price",
            "rule_results": [
                {"rule_name": "some_rule", "passed": True, "severity": "info"},
            ],
        }
        result = await svc.validate_billability_decision(tenant_id, case_id, decision)

        assert result.status == ValidationStatus.blocked
        rules = result.rule_results["rules"]
        rate_rule = next(r for r in rules if r["rule_name"] == "rate_card_evidence")
        assert rate_rule["passed"] is False


class TestValidateBillabilityLowConfidence:
    @pytest.mark.asyncio
    async def test_validate_billability_low_confidence(self, svc, tenant_id, case_id):
        """Low confidence for billable should produce warned status."""
        decision = {
            "billable": True,
            "rate_applied": 100.0,
            "reasons": ["Rate matched"],
            "confidence": 0.5,  # Below 0.6 threshold for billable
            "category": "time_and_materials",
            "rule_results": [
                {"rule_name": "basic", "passed": True, "severity": "info"},
            ],
        }
        result = await svc.validate_billability_decision(tenant_id, case_id, decision)

        assert result.status == ValidationStatus.warned
        rules = result.rule_results["rules"]
        conf_rule = next(r for r in rules if r["rule_name"] == "confidence_threshold")
        assert conf_rule["passed"] is False

    @pytest.mark.asyncio
    async def test_validate_billability_low_confidence_non_billable(self, svc, tenant_id, case_id):
        """Low confidence for non-billable (< 0.8) should warn."""
        decision = {
            "billable": False,
            "reasons": ["No match"],
            "confidence": 0.7,  # Below 0.8 threshold for non-billable
            "category": "fixed_price",
            "rule_results": [
                {"rule_name": "basic", "passed": True, "severity": "info"},
            ],
        }
        result = await svc.validate_billability_decision(tenant_id, case_id, decision)

        rules = result.rule_results["rules"]
        conf_rule = next(r for r in rules if r["rule_name"] == "confidence_threshold")
        assert conf_rule["passed"] is False


class TestValidateBillabilityConflictingRules:
    @pytest.mark.asyncio
    async def test_validate_billability_conflicting_rules(self, svc, tenant_id, case_id):
        """has_valid_rate passed but rate_applied is None should flag conflict."""
        decision = {
            "billable": True,
            "rate_applied": None,
            "reasons": ["Reason"],
            "confidence": 0.7,
            "category": "time_and_materials",
            "rule_results": [
                {"rule_name": "has_valid_rate", "passed": True, "severity": "info"},
            ],
        }
        result = await svc.validate_billability_decision(tenant_id, case_id, decision)

        assert result.status == ValidationStatus.blocked
        rules = result.rule_results["rules"]
        conflict_rule = next(r for r in rules if r["rule_name"] == "no_conflicting_rules")
        assert conflict_rule["passed"] is False
        assert "Conflict" in conflict_rule["message"]

    @pytest.mark.asyncio
    async def test_validate_billability_invalid_category(self, svc, tenant_id, case_id):
        """Invalid category should produce error."""
        decision = {
            "billable": False,
            "reasons": ["No match"],
            "confidence": 0.9,
            "category": "invalid_category_xyz",
            "rule_results": [
                {"rule_name": "basic", "passed": True, "severity": "info"},
            ],
        }
        result = await svc.validate_billability_decision(tenant_id, case_id, decision)

        assert result.status == ValidationStatus.blocked
        rules = result.rule_results["rules"]
        cat_rule = next(r for r in rules if r["rule_name"] == "valid_category")
        assert cat_rule["passed"] is False

    @pytest.mark.asyncio
    async def test_validate_billability_empty_reasons(self, svc, tenant_id, case_id):
        """Empty reasons should produce error."""
        decision = {
            "billable": False,
            "reasons": [],
            "confidence": 0.9,
            "category": "fixed_price",
            "rule_results": [
                {"rule_name": "basic", "passed": True, "severity": "info"},
            ],
        }
        result = await svc.validate_billability_decision(tenant_id, case_id, decision)

        assert result.status == ValidationStatus.blocked
        rules = result.rule_results["rules"]
        reasons_rule = next(r for r in rules if r["rule_name"] == "reasons_populated")
        assert reasons_rule["passed"] is False


# ── Margin Diagnosis Tests ──────────────────────────────────────


class TestValidateMarginDiagnosisValid:
    @pytest.mark.asyncio
    async def test_validate_margin_diagnosis_valid(self, svc, tenant_id, case_id):
        """A fully valid margin diagnosis should produce passed status."""
        eid = uuid.uuid4()
        diagnosis = {
            "verdict": "under_recovery",
            "leakage_drivers": ["rate_mismatch", "sla_penalty"],
            "evidence_object_ids": [str(eid)],
            "recovery_recommendations": ["Renegotiate rate card"],
            "executive_summary": "Margin leakage detected due to rate mismatch.",
            "confidence": 0.9,
        }
        result = await svc.validate_margin_diagnosis(tenant_id, case_id, diagnosis)

        assert result.status == ValidationStatus.passed
        assert result.validator_name == "contract_margin_margin_diagnosis_validator"


class TestValidateMarginDiagnosisMissingDrivers:
    @pytest.mark.asyncio
    async def test_validate_margin_diagnosis_missing_drivers(self, svc, tenant_id, case_id):
        """under_recovery verdict without leakage_drivers should fail."""
        diagnosis = {
            "verdict": "under_recovery",
            "leakage_drivers": [],
            "evidence_object_ids": [str(uuid.uuid4())],
            "recovery_recommendations": [],
            "executive_summary": "Summary.",
            "confidence": 0.8,
        }
        result = await svc.validate_margin_diagnosis(tenant_id, case_id, diagnosis)

        assert result.status == ValidationStatus.blocked
        rules = result.rule_results["rules"]
        drivers_rule = next(r for r in rules if r["rule_name"] == "leakage_drivers_required")
        assert drivers_rule["passed"] is False


class TestValidateMarginDiagnosisInvalidVerdict:
    @pytest.mark.asyncio
    async def test_validate_margin_diagnosis_invalid_verdict(self, svc, tenant_id, case_id):
        """Invalid verdict should produce error."""
        diagnosis = {
            "verdict": "totally_bogus",
            "leakage_drivers": [],
            "evidence_object_ids": [],
            "executive_summary": "Summary.",
        }
        result = await svc.validate_margin_diagnosis(tenant_id, case_id, diagnosis)

        assert result.status == ValidationStatus.blocked
        rules = result.rule_results["rules"]
        verdict_rule = next(r for r in rules if r["rule_name"] == "valid_margin_verdict")
        assert verdict_rule["passed"] is False

    @pytest.mark.asyncio
    async def test_validate_margin_diagnosis_out_of_range_confidence(self, svc, tenant_id, case_id):
        """Confidence outside [0, 1] should produce error."""
        diagnosis = {
            "verdict": "billable",
            "leakage_drivers": [],
            "evidence_object_ids": [str(uuid.uuid4())],
            "executive_summary": "Summary.",
            "confidence": 1.5,
        }
        result = await svc.validate_margin_diagnosis(tenant_id, case_id, diagnosis)

        rules = result.rule_results["rules"]
        conf_rule = next(r for r in rules if r["rule_name"] == "confidence_in_range")
        assert conf_rule["passed"] is False


# ── Reconciliation Tests ────────────────────────────────────────


class TestValidateReconciliationValid:
    @pytest.mark.asyncio
    async def test_validate_reconciliation_valid(self, svc, tenant_id, case_id):
        """A valid reconciliation should produce passed status."""
        eid1 = str(uuid.uuid4())
        eid2 = str(uuid.uuid4())
        reconciliation = {
            "links": [
                {"source_id": str(uuid.uuid4()), "target_id": eid1},
            ],
            "conflicts": [
                {"severity": "medium", "description": "Rate mismatch"},
            ],
            "evidence_bundle": [
                {"id": eid1, "type": "rate_card"},
                {"id": eid2, "type": "sla"},
            ],
            "verdict": "needs_resolution",
        }
        result = await svc.validate_reconciliation_output(tenant_id, case_id, reconciliation)

        assert result.status == ValidationStatus.passed
        assert result.domain == "cross_pack"


class TestValidateReconciliationOrphanedLinks:
    @pytest.mark.asyncio
    async def test_validate_reconciliation_orphaned_links(self, svc, tenant_id, case_id):
        """Link targeting an ID not in evidence bundle should be flagged."""
        orphan_id = str(uuid.uuid4())
        evidence_id = str(uuid.uuid4())
        reconciliation = {
            "links": [
                {"source_id": str(uuid.uuid4()), "target_id": orphan_id},
            ],
            "conflicts": [],
            "evidence_bundle": [
                {"id": evidence_id, "type": "rate_card"},
            ],
            "verdict": "clean",
        }
        result = await svc.validate_reconciliation_output(tenant_id, case_id, reconciliation)

        rules = result.rule_results["rules"]
        orphan_rule = next(r for r in rules if r["rule_name"] == "no_orphaned_links")
        assert orphan_rule["passed"] is False


class TestValidateReconciliationInconsistentVerdict:
    @pytest.mark.asyncio
    async def test_validate_reconciliation_inconsistent_verdict(self, svc, tenant_id, case_id):
        """Verdict 'clean' with conflicts should be inconsistent."""
        eid = str(uuid.uuid4())
        reconciliation = {
            "links": [],
            "conflicts": [
                {"severity": "high", "description": "SLA mismatch"},
            ],
            "evidence_bundle": [
                {"id": eid, "type": "sla"},
            ],
            "verdict": "clean",
        }
        result = await svc.validate_reconciliation_output(tenant_id, case_id, reconciliation)

        rules = result.rule_results["rules"]
        consistency_rule = next(
            r for r in rules if r["rule_name"] == "verdict_conflict_consistency"
        )
        assert consistency_rule["passed"] is False


class TestValidationPersistedToDb:
    @pytest.mark.asyncio
    async def test_validation_persisted_to_db(self, svc, mock_db, tenant_id, case_id):
        """ValidationResult should be added to the DB session."""
        decision = {
            "billable": False,
            "reasons": ["No match"],
            "confidence": 0.9,
            "category": "fixed_price",
            "rule_results": [{"rule_name": "r1", "passed": True, "severity": "info"}],
        }
        result = await svc.validate_billability_decision(tenant_id, case_id, decision)

        mock_db.add.assert_called_once()
        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, ValidationResult)
        assert added_obj.tenant_id == tenant_id
        assert added_obj.workflow_case_id == case_id
        mock_db.flush.assert_awaited_once()


class TestValidationCreatesAuditEvent:
    @pytest.mark.asyncio
    async def test_validation_creates_audit_event(self, svc, tenant_id, case_id):
        """Each validation method should persist a ValidationResult with a summary."""
        diagnosis = {
            "verdict": "billable",
            "leakage_drivers": [],
            "evidence_object_ids": [str(uuid.uuid4())],
            "executive_summary": "All good.",
            "confidence": 0.95,
        }
        result = await svc.validate_margin_diagnosis(tenant_id, case_id, diagnosis)

        assert result.summary is not None
        assert "rules passed" in result.summary
        assert result.id is not None
