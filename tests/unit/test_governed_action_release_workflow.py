"""Tests for the Governed Action Release Workflow."""

from __future__ import annotations

import uuid

import pytest

from app.workflows.governed_action_release.workflow import (
    GovernedActionReleaseActivities,
    GovernedActionReleaseInput,
    GovernedActionReleaseWorkflow,
)

TENANT = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
CASE = str(uuid.UUID("00000000-0000-0000-0000-000000000099"))


class TestGovernedActionReleaseWorkflow:
    def test_successful_release(self):
        wf = GovernedActionReleaseWorkflow(GovernedActionReleaseActivities())
        result = wf.run(
            GovernedActionReleaseInput(
                pilot_case_id=CASE,
                tenant_id=TENANT,
                action_type="billing_adjustment",
                action_label="Adjust Margin",
            )
        )
        assert result.status == "released"
        assert result.validation_outcome == "released"
        assert result.released_at is not None
        assert result.error is None

    def test_blocked_action(self):
        class BlockingActivities(GovernedActionReleaseActivities):
            def run_validation_chain(self, pilot_case_id, tenant_id, action_id, context):
                return {
                    "chain_id": str(uuid.uuid4()),
                    "outcome": "blocked",
                    "blocking_stage": "evidence",
                    "blocking_message": "Evidence insufficient",
                }

        wf = GovernedActionReleaseWorkflow(BlockingActivities())
        result = wf.run(
            GovernedActionReleaseInput(
                pilot_case_id=CASE,
                tenant_id=TENANT,
                action_type="dispatch_order",
                action_label="Dispatch Crew",
            )
        )
        assert result.status == "blocked"
        assert result.blocking_stage == "evidence"
        assert result.blocking_message == "Evidence insufficient"

    def test_escalated_action(self):
        class EscalatingActivities(GovernedActionReleaseActivities):
            def run_validation_chain(self, pilot_case_id, tenant_id, action_id, context):
                return {
                    "chain_id": str(uuid.uuid4()),
                    "outcome": "escalated",
                    "blocking_stage": None,
                    "blocking_message": "Needs governance review",
                }

        wf = GovernedActionReleaseWorkflow(EscalatingActivities())
        result = wf.run(
            GovernedActionReleaseInput(
                pilot_case_id=CASE,
                tenant_id=TENANT,
                action_type="escalation",
                action_label="Escalate to Board",
            )
        )
        assert result.status == "escalated"

    def test_warn_released(self):
        class WarnActivities(GovernedActionReleaseActivities):
            def run_validation_chain(self, pilot_case_id, tenant_id, action_id, context):
                return {
                    "chain_id": str(uuid.uuid4()),
                    "outcome": "warn_released",
                    "blocking_stage": None,
                    "blocking_message": None,
                }

        wf = GovernedActionReleaseWorkflow(WarnActivities())
        result = wf.run(
            GovernedActionReleaseInput(
                pilot_case_id=CASE,
                tenant_id=TENANT,
                action_type="notification",
                action_label="Notify Team",
            )
        )
        assert result.status == "released"
        assert result.validation_outcome == "warn_released"

    def test_with_evidence_refs(self):
        wf = GovernedActionReleaseWorkflow(GovernedActionReleaseActivities())
        result = wf.run(
            GovernedActionReleaseInput(
                pilot_case_id=CASE,
                tenant_id=TENANT,
                action_type="contract_flag",
                action_label="Flag Contract",
                evidence_refs=[str(uuid.uuid4()), str(uuid.uuid4())],
                confidence=0.88,
            )
        )
        assert result.status == "released"

    def test_error_handling(self):
        class FailingActivities(GovernedActionReleaseActivities):
            def create_candidate_action(self, **kwargs):
                raise RuntimeError("DB error")

        wf = GovernedActionReleaseWorkflow(FailingActivities())
        result = wf.run(
            GovernedActionReleaseInput(
                pilot_case_id=CASE,
                tenant_id=TENANT,
                action_type="billing_adjustment",
                action_label="Fail",
            )
        )
        assert result.status == "failed"
        assert result.error is not None
