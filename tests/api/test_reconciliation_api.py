"""API tests for reconciliation routes."""

from __future__ import annotations

import uuid

import pytest

from app.api.routes.reconciliation import (
    ContradictionCheckRequest,
    ContradictionResponse,
    EvidenceChainRequest,
    EvidenceChainResponse,
    ReconciliationRequest,
    ReconciliationResponse,
)


class TestReconciliationSchemas:
    """Test reconciliation request/response schemas."""

    def test_reconciliation_request_minimal(self):
        req = ReconciliationRequest(contract={"title": "MSA"})
        assert req.contract["title"] == "MSA"
        assert req.work_orders == []
        assert req.incidents == []

    def test_reconciliation_request_full(self):
        req = ReconciliationRequest(
            contract={"title": "MSA", "clauses": []},
            work_orders=[{"id": "WO-001", "activity": "cable_jointing"}],
            incidents=[{"id": "INC-001", "severity": "P1"}],
            rate_card=[{"activity": "cable_jointing", "rate": 150.0}],
            obligations=[{"clause_id": "CL-001", "description": "Monthly reporting"}],
        )
        assert len(req.work_orders) == 1
        assert len(req.incidents) == 1
        assert len(req.rate_card) == 1
        assert len(req.obligations) == 1

    def test_reconciliation_response(self):
        resp = ReconciliationResponse(
            verdict="billable",
            total_at_risk_value=5000.0,
            leakage_trigger_count=2,
            contradiction_count=1,
            evidence_chain_valid=True,
            executive_summary="Minor leakage detected",
        )
        assert resp.verdict == "billable"
        assert resp.total_at_risk_value == 5000.0
        assert resp.leakage_trigger_count == 2

    def test_contradiction_check_request(self):
        req = ContradictionCheckRequest(
            contract={"clauses": []},
            work_orders=[{"id": "WO-001"}],
        )
        assert len(req.work_orders) == 1

    def test_contradiction_response(self):
        resp = ContradictionResponse(
            contradictions=[
                {"type": "scope_mismatch", "severity": "high"},
                {"type": "rate_mismatch", "severity": "medium"},
            ],
            total=2,
        )
        assert resp.total == 2
        assert len(resp.contradictions) == 2

    def test_evidence_chain_request(self):
        req = EvidenceChainRequest(
            evidence_stages={
                "contract_basis": ["CL-001", "CL-002"],
                "work_authorization": ["WO-001"],
                "execution_evidence": ["PHOTO-001"],
                "billing_evidence": ["INV-001"],
            }
        )
        assert len(req.evidence_stages) == 4
        assert "contract_basis" in req.evidence_stages

    def test_evidence_chain_response_valid(self):
        resp = EvidenceChainResponse(
            valid=True,
            missing_stages=[],
            stage_results={"contract_basis": True, "work_authorization": True},
        )
        assert resp.valid is True
        assert len(resp.missing_stages) == 0

    def test_evidence_chain_response_invalid(self):
        resp = EvidenceChainResponse(
            valid=False,
            missing_stages=["billing_evidence"],
            stage_results={"contract_basis": True, "billing_evidence": False},
        )
        assert resp.valid is False
        assert "billing_evidence" in resp.missing_stages


class TestReconciliationResponseDefaults:
    """Test default values on ReconciliationResponse."""

    def test_defaults(self):
        resp = ReconciliationResponse(verdict="unknown")
        assert resp.total_at_risk_value == 0.0
        assert resp.leakage_trigger_count == 0
        assert resp.contradiction_count == 0
        assert resp.evidence_chain_valid is True
        assert resp.executive_summary == ""
        assert resp.details == {}
