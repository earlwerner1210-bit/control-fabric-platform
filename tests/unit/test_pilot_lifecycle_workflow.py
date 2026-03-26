"""Tests for the pilot case lifecycle workflow."""

from __future__ import annotations

import uuid

import pytest

from app.services.audit.service import InMemoryAuditService
from app.workflows.pilot_case_lifecycle import (
    PilotCaseLifecycleActivities,
    PilotCaseLifecycleInput,
    PilotCaseLifecycleWorkflow,
)


@pytest.fixture
def audit_svc():
    return InMemoryAuditService()


@pytest.fixture
def workflow(audit_svc):
    activities = PilotCaseLifecycleActivities(audit_service=audit_svc)
    return PilotCaseLifecycleWorkflow(activities=activities)


def _input(**kwargs):
    defaults = {
        "pilot_case_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "workflow_type": "margin_diagnosis",
        "title": "Test Case",
        "created_by": str(uuid.uuid4()),
    }
    defaults.update(kwargs)
    return PilotCaseLifecycleInput(**defaults)


class TestLifecycleWorkflow:
    def test_basic_run(self, workflow):
        result = workflow.run(_input())
        assert result.final_state == "under_review"
        assert result.error is None
        assert len(result.timeline) > 0

    def test_timeline_includes_creation(self, workflow):
        result = workflow.run(_input())
        event_types = [e["event_type"] for e in result.timeline]
        assert "case_created" in event_types
        assert "state_transition" in event_types

    def test_with_artifacts(self, workflow):
        inp = _input(
            artifacts=[
                {"type": "contract", "id": str(uuid.uuid4())},
                {"type": "rate_card", "id": str(uuid.uuid4())},
            ]
        )
        result = workflow.run(inp)
        event_types = [e["event_type"] for e in result.timeline]
        assert "artifact_linked" in event_types

    def test_with_reviewer(self, workflow):
        reviewer_id = str(uuid.uuid4())
        result = workflow.run(_input(reviewer_id=reviewer_id))
        event_types = [e["event_type"] for e in result.timeline]
        assert "reviewer_assigned" in event_types

    def test_with_baseline(self, workflow):
        result = workflow.run(
            _input(
                baseline_expectation={
                    "expected_outcome": "billable",
                    "expected_confidence": 0.95,
                }
            )
        )
        event_types = [e["event_type"] for e in result.timeline]
        assert "baseline_expectation_stored" in event_types

    def test_state_transitions_in_order(self, workflow):
        result = workflow.run(_input())
        transitions = [e for e in result.timeline if e["event_type"] == "state_transition"]
        states = [t["details"]["new_state"] for t in transitions]
        assert states == [
            "evidence_ready",
            "workflow_executed",
            "validation_completed",
            "under_review",
        ]

    def test_kpi_recorded(self, workflow):
        result = workflow.run(_input())
        assert len(result.kpi_measurements) >= 1
        assert result.kpi_measurements[0]["metric_name"] == "time_to_review_setup"

    def test_audit_events_recorded(self, workflow, audit_svc):
        workflow.run(_input())
        assert audit_svc.count() > 0
        assert audit_svc.count("pilot_case.created") == 1

    def test_full_lifecycle_with_all_options(self, workflow):
        result = workflow.run(
            _input(
                artifacts=[{"type": "contract", "id": str(uuid.uuid4())}],
                reviewer_id=str(uuid.uuid4()),
                baseline_expectation={"expected_outcome": "billable"},
                tags=["pilot_wave_1"],
                severity="high",
                business_impact="major",
            )
        )
        assert result.final_state == "under_review"
        assert len(result.timeline) >= 7  # create, artifact, reviewer, 4 transitions, baseline
