"""Tests for the review and approval workflow."""

from __future__ import annotations

import uuid

import pytest

from app.services.audit.service import InMemoryAuditService
from app.workflows.review_and_approval import (
    ReviewAndApprovalActivities,
    ReviewAndApprovalInput,
    ReviewAndApprovalWorkflow,
)


@pytest.fixture
def audit_svc():
    return InMemoryAuditService()


@pytest.fixture
def workflow(audit_svc):
    activities = ReviewAndApprovalActivities(audit_service=audit_svc)
    return ReviewAndApprovalWorkflow(activities=activities)


def _input(**kwargs):
    defaults = {
        "pilot_case_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "reviewer_id": str(uuid.uuid4()),
        "workflow_output": {"verdict": "billable", "confidence": 0.92},
        "validation_result": {"status": "passed"},
    }
    defaults.update(kwargs)
    return ReviewAndApprovalInput(**defaults)


class TestAcceptFlow:
    def test_accept_results_in_approved(self, workflow):
        result = workflow.run(_input(), review_outcome="accept")
        assert result.final_state == "approved"
        assert result.approval_type == "approval"
        assert result.review_outcome == "accept"

    def test_accept_with_confidence(self, workflow):
        result = workflow.run(
            _input(),
            review_outcome="accept",
            review_reasoning="Verified correct",
            review_confidence=0.96,
        )
        assert result.reviewer_confidence == 0.96

    def test_accept_timeline(self, workflow):
        result = workflow.run(_input(), review_outcome="accept")
        event_types = [e["event_type"] for e in result.timeline]
        assert "workflow_output_fetched" in event_types
        assert "evidence_fetched" in event_types
        assert "review_task_created" in event_types
        assert "review_outcome_captured" in event_types
        assert "approval_captured" in event_types
        assert "final_result_persisted" in event_types


class TestWarnFlow:
    def test_warn_results_in_approved(self, workflow):
        result = workflow.run(_input(), review_outcome="warn")
        assert result.final_state == "approved"
        assert result.approval_type == "approval"


class TestRejectFlow:
    def test_reject_without_override_closes(self, workflow):
        result = workflow.run(_input(), review_outcome="reject")
        assert result.final_state == "closed"
        assert result.approval_type is None

    def test_reject_with_override(self, workflow):
        result = workflow.run(
            _input(),
            review_outcome="reject",
            override_reason="model_acceptable_commercial_differs",
            corrected_outcome={"verdict": "not_billable"},
        )
        assert result.final_state == "overridden"
        assert result.approval_type == "override"
        assert result.override_reason == "model_acceptable_commercial_differs"


class TestEscalateFlow:
    def test_escalate(self, workflow):
        result = workflow.run(
            _input(),
            review_outcome="escalate",
            escalation_route="governance_board",
        )
        assert result.final_state == "escalated"
        assert result.approval_type == "escalation"
        assert result.escalation_route == "governance_board"


class TestRequestMoreEvidence:
    def test_request_more_evidence(self, workflow):
        result = workflow.run(_input(), review_outcome="request_more_evidence")
        assert result.final_state == "evidence_ready"
        assert result.approval_type is None


class TestBaselineComparison:
    def test_baseline_compared_when_expectation_provided(self, workflow):
        result = workflow.run(
            _input(
                baseline_expectation={
                    "expected_outcome": "billable",
                    "expected_confidence": 0.95,
                }
            ),
            review_outcome="accept",
        )
        event_types = [e["event_type"] for e in result.timeline]
        assert "baseline_compared" in event_types


class TestAuditIntegration:
    def test_audit_events_recorded(self, workflow, audit_svc):
        workflow.run(_input(), review_outcome="accept")
        assert audit_svc.count() > 0
        assert audit_svc.count("review.task_created") == 1
        assert audit_svc.count("review.decision_captured") == 1
        assert audit_svc.count("review.approval") == 1
        assert audit_svc.count("review.completed") == 1

    def test_override_audit(self, workflow, audit_svc):
        workflow.run(
            _input(),
            review_outcome="reject",
            override_reason="evidence_incomplete",
            corrected_outcome={"verdict": "not_billable"},
        )
        assert audit_svc.count("review.override") == 1

    def test_escalation_audit(self, workflow, audit_svc):
        workflow.run(
            _input(),
            review_outcome="escalate",
            escalation_route="commercial_lead",
        )
        assert audit_svc.count("review.escalation") == 1
