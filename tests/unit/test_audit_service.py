"""Tests for the in-memory audit service."""

from __future__ import annotations

import uuid

import pytest

from app.services.audit.service import PILOT_AUDIT_EVENTS, InMemoryAuditService


@pytest.fixture
def svc():
    return InMemoryAuditService()


CASE_ID = str(uuid.uuid4())
TENANT_ID = str(uuid.uuid4())
ACTOR_ID = str(uuid.uuid4())


class TestRecord:
    def test_record_event(self, svc: InMemoryAuditService):
        event = svc.record(
            event_type="pilot_case.created",
            resource_id=CASE_ID,
            tenant_id=TENANT_ID,
            actor_id=ACTOR_ID,
            payload={"title": "Test Case"},
        )
        assert event["event_type"] == "pilot_case.created"
        assert event["resource_id"] == CASE_ID
        assert event["tenant_id"] == TENANT_ID
        assert event["payload"]["title"] == "Test Case"

    def test_record_minimal(self, svc: InMemoryAuditService):
        event = svc.record(event_type="pilot_case.created")
        assert event["event_type"] == "pilot_case.created"
        assert event["resource_id"] is None

    def test_events_are_append_only(self, svc: InMemoryAuditService):
        svc.record("pilot_case.created", resource_id=CASE_ID)
        svc.record("pilot_case.state_transition", resource_id=CASE_ID)
        svc.record("review.decision_captured", resource_id=CASE_ID)
        assert svc.count() == 3


class TestGetEvents:
    def test_get_by_resource(self, svc: InMemoryAuditService):
        svc.record("pilot_case.created", resource_id=CASE_ID)
        svc.record("review.decision_captured", resource_id=CASE_ID)
        svc.record("pilot_case.created", resource_id="other")
        events = svc.get_events(resource_id=CASE_ID)
        assert len(events) == 2

    def test_get_by_type(self, svc: InMemoryAuditService):
        svc.record("pilot_case.created", resource_id=CASE_ID)
        svc.record("review.decision_captured", resource_id=CASE_ID)
        events = svc.get_events(event_type="pilot_case.created")
        assert len(events) == 1

    def test_get_by_resource_and_type(self, svc: InMemoryAuditService):
        svc.record("pilot_case.created", resource_id=CASE_ID)
        svc.record("review.decision_captured", resource_id=CASE_ID)
        svc.record("pilot_case.created", resource_id="other")
        events = svc.get_events(resource_id=CASE_ID, event_type="pilot_case.created")
        assert len(events) == 1

    def test_get_empty(self, svc: InMemoryAuditService):
        assert svc.get_events(resource_id="nonexistent") == []


class TestCount:
    def test_count_all(self, svc: InMemoryAuditService):
        for i in range(5):
            svc.record(f"event_{i}")
        assert svc.count() == 5

    def test_count_by_type(self, svc: InMemoryAuditService):
        svc.record("pilot_case.created")
        svc.record("pilot_case.created")
        svc.record("review.decision_captured")
        assert svc.count("pilot_case.created") == 2
        assert svc.count("review.decision_captured") == 1

    def test_count_zero(self, svc: InMemoryAuditService):
        assert svc.count() == 0


class TestPilotAuditEvents:
    def test_all_expected_events_defined(self):
        """Verify all pilot hardening event types are registered."""
        expected_prefixes = [
            "pilot_case.",
            "review.",
            "evidence.",
            "baseline.",
            "feedback.",
            "kpi.",
        ]
        for prefix in expected_prefixes:
            matching = [e for e in PILOT_AUDIT_EVENTS if e.startswith(prefix)]
            assert len(matching) > 0, f"No events with prefix {prefix}"

    def test_event_count(self):
        assert len(PILOT_AUDIT_EVENTS) >= 25
