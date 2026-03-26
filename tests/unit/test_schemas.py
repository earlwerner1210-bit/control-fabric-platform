"""Tests for shared Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.schemas.common import ErrorResponse, HealthResponse, PaginatedResponse
from app.schemas.control_objects import (
    ControlLinkCreate,
    ControlObjectCreate,
    ControlObjectResponse,
    ControlObjectTypeEnum,
)
from app.schemas.workflows import (
    CaseVerdictEnum,
    MarginVerdict,
    ReadinessVerdict,
    SPENBillabilityVerdict,
    WorkflowStatusEnum,
    WorkflowTimelineEntry,
)


class TestPaginatedResponse:
    """Test PaginatedResponse schema."""

    def test_empty(self):
        resp = PaginatedResponse(items=[], total=0, page=1, page_size=50)
        assert resp.total == 0
        assert len(resp.items) == 0

    def test_with_items(self):
        resp = PaginatedResponse(
            items=["a", "b", "c"],
            total=100,
            page=2,
            page_size=3,
        )
        assert len(resp.items) == 3
        assert resp.total == 100
        assert resp.page == 2

    def test_defaults(self):
        resp = PaginatedResponse(items=[], total=0)
        assert resp.page == 1
        assert resp.page_size == 50


class TestSPENBillabilityVerdict:
    """Test SPEN billability verdict enum."""

    def test_values(self):
        assert SPENBillabilityVerdict.billable == "billable"
        assert SPENBillabilityVerdict.non_billable == "non_billable"

    def test_is_str(self):
        assert isinstance(SPENBillabilityVerdict.billable, str)


class TestWorkflowEnums:
    """Test workflow enum values."""

    def test_workflow_status(self):
        assert WorkflowStatusEnum.pending == "pending"
        assert WorkflowStatusEnum.running == "running"
        assert WorkflowStatusEnum.completed == "completed"
        assert WorkflowStatusEnum.failed == "failed"
        assert WorkflowStatusEnum.cancelled == "cancelled"

    def test_case_verdict(self):
        assert CaseVerdictEnum.approved == "approved"
        assert CaseVerdictEnum.rejected == "rejected"

    def test_margin_verdict(self):
        assert MarginVerdict.billable == "billable"
        assert MarginVerdict.non_billable == "non_billable"
        assert MarginVerdict.under_recovery == "under_recovery"
        assert MarginVerdict.penalty_risk == "penalty_risk"
        assert MarginVerdict.unknown == "unknown"

    def test_readiness_verdict(self):
        assert ReadinessVerdict.ready == "ready"
        assert ReadinessVerdict.blocked == "blocked"


class TestWorkflowTimelineEntry:
    """Test WorkflowTimelineEntry schema."""

    def test_create(self):
        entry = WorkflowTimelineEntry(
            timestamp=datetime.now(UTC),
            event_type="workflow_started",
            stage="init",
            detail="Margin diagnosis workflow initiated",
            actor="system",
        )
        assert entry.event_type == "workflow_started"
        assert entry.actor == "system"
        assert entry.stage == "init"


class TestControlObjectTypeEnum:
    """Test ControlObjectTypeEnum values."""

    def test_values(self):
        assert ControlObjectTypeEnum.obligation == "obligation"
        assert ControlObjectTypeEnum.billable_event == "billable_event"
        assert ControlObjectTypeEnum.penalty_condition == "penalty_condition"
        assert ControlObjectTypeEnum.leakage_trigger == "leakage_trigger"


class TestControlObjectCreate:
    """Test ControlObjectCreate schema."""

    def test_create(self):
        obj = ControlObjectCreate(
            control_type=ControlObjectTypeEnum.obligation,
            domain="contract_margin",
            label="Monthly reporting obligation",
        )
        assert obj.control_type == "obligation"
        assert obj.domain == "contract_margin"
        assert obj.confidence == 1.0

    def test_with_source(self):
        doc_id = uuid.uuid4()
        obj = ControlObjectCreate(
            control_type=ControlObjectTypeEnum.billable_event,
            domain="contract_margin",
            label="Cable jointing",
            source_document_id=doc_id,
            source_clause_ref="CL-005",
            confidence=0.95,
        )
        assert obj.source_document_id == doc_id
        assert obj.source_clause_ref == "CL-005"


class TestControlObjectResponse:
    """Test ControlObjectResponse schema."""

    def test_create(self):
        now = datetime.now(UTC)
        resp = ControlObjectResponse(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            control_type=ControlObjectTypeEnum.obligation,
            domain="contract_margin",
            label="Monthly reporting",
            payload={"clause_id": "CL-001"},
            confidence=0.9,
            created_at=now,
            updated_at=now,
        )
        assert resp.domain == "contract_margin"
        assert resp.control_type == "obligation"
        assert resp.confidence == 0.9


class TestControlLinkCreate:
    """Test ControlLinkCreate schema."""

    def test_create(self):
        link = ControlLinkCreate(
            source_object_id=uuid.uuid4(),
            target_object_id=uuid.uuid4(),
            link_type="contract_work_order",
            weight=0.85,
        )
        assert link.link_type == "contract_work_order"
        assert link.weight == 0.85


class TestErrorResponse:
    """Test ErrorResponse schema."""

    def test_create(self):
        err = ErrorResponse(detail="Not found", code="NOT_FOUND")
        assert err.detail == "Not found"
        assert err.code == "NOT_FOUND"
        assert err.timestamp is None

    def test_with_extra(self):
        err = ErrorResponse(
            detail="Validation failed",
            code="VALIDATION_ERROR",
            extra={"field": "email", "reason": "invalid format"},
        )
        assert err.extra["field"] == "email"


class TestHealthResponse:
    """Test HealthResponse schema."""

    def test_create(self):
        health = HealthResponse(status="ok", version="0.1.0", environment="dev")
        assert health.status == "ok"
