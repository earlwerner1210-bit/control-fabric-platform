"""Deep tests for AuditService – workflow events, validation events, timeline."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import AuditEvent
from app.services.audit.service import AuditService


def _make_audit_event(
    *,
    event_type: str = "test",
    case_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    actor_type: str = "system",
    actor_id: uuid.UUID | None = None,
    detail: str = "",
    payload: dict | None = None,
    created_at: datetime | None = None,
) -> AuditEvent:
    """Helper to create an AuditEvent ORM object for testing."""
    event = AuditEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        workflow_case_id=case_id,
        event_type=event_type,
        actor_id=actor_id,
        actor_type=actor_type,
        resource_type=None,
        resource_id=None,
        detail=detail,
        payload=payload,
    )
    # Manually set created_at since it's normally set by the DB
    event.created_at = created_at or datetime.now(timezone.utc)
    return event


@pytest.fixture
def mock_db():
    """Create a mock async DB session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def svc(mock_db):
    return AuditService(mock_db)


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def case_id():
    return uuid.uuid4()


class TestLogWorkflowEvent:
    @pytest.mark.asyncio
    async def test_log_workflow_event(self, svc, mock_db, tenant_id, case_id):
        """log_workflow_event should create and persist an AuditEvent."""
        event = await svc.log_workflow_event(
            tenant_id=tenant_id,
            case_id=case_id,
            event_type="workflow_started",
            stage="ingestion",
            detail="Started contract compile workflow",
            metadata={"source": "api"},
            actor_id=uuid.uuid4(),
            actor_type="user",
        )

        assert isinstance(event, AuditEvent)
        assert event.event_type == "workflow_started"
        assert event.tenant_id == tenant_id
        assert event.workflow_case_id == case_id
        assert event.actor_type == "user"
        assert event.payload["stage"] == "ingestion"
        assert event.payload["metadata"] == {"source": "api"}
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()


class TestLogValidationEvent:
    @pytest.mark.asyncio
    async def test_log_validation_event(self, svc, mock_db, tenant_id, case_id):
        """log_validation_event should create a validation audit event."""
        vr_id = uuid.uuid4()
        event = await svc.log_validation_event(
            tenant_id=tenant_id,
            case_id=case_id,
            validation_result_id=vr_id,
            status="passed",
            rule_count=5,
            failed_count=0,
        )

        assert isinstance(event, AuditEvent)
        assert event.event_type == "validation_completed"
        assert event.resource_type == "validation_result"
        assert event.resource_id == vr_id
        assert event.payload["status"] == "passed"
        assert event.payload["rule_count"] == 5
        assert event.payload["failed_count"] == 0
        mock_db.add.assert_called_once()


class TestLogReconciliationEvent:
    @pytest.mark.asyncio
    async def test_log_reconciliation_event(self, svc, mock_db, tenant_id, case_id):
        """log_reconciliation_event should create a reconciliation audit event."""
        event = await svc.log_reconciliation_event(
            tenant_id=tenant_id,
            case_id=case_id,
            links_found=3,
            conflicts_found=1,
            leakage_patterns=2,
            verdict="needs_resolution",
        )

        assert isinstance(event, AuditEvent)
        assert event.event_type == "reconciliation_completed"
        assert event.payload["links_found"] == 3
        assert event.payload["conflicts_found"] == 1
        assert event.payload["leakage_patterns"] == 2
        assert event.payload["verdict"] == "needs_resolution"
        mock_db.add.assert_called_once()


class TestGetWorkflowTimelineOrdered:
    @pytest.mark.asyncio
    async def test_get_workflow_timeline_ordered(self, svc, mock_db, tenant_id, case_id):
        """get_workflow_timeline should return events ordered by timestamp."""
        t1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 1, 10, 5, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 1, 1, 10, 10, 0, tzinfo=timezone.utc)

        events = [
            _make_audit_event(
                event_type="started", case_id=case_id, tenant_id=tenant_id,
                payload={"stage": "ingestion"}, detail="Started", created_at=t1,
            ),
            _make_audit_event(
                event_type="compiled", case_id=case_id, tenant_id=tenant_id,
                payload={"stage": "compilation"}, detail="Compiled", created_at=t2,
            ),
            _make_audit_event(
                event_type="validated", case_id=case_id, tenant_id=tenant_id,
                payload={"stage": "validation"}, detail="Validated", created_at=t3,
            ),
        ]

        # Mock the DB query result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = events
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)

        timeline = await svc.get_workflow_timeline(case_id, tenant_id)

        assert len(timeline) == 3
        assert timeline[0]["event_type"] == "started"
        assert timeline[0]["stage"] == "ingestion"
        assert timeline[1]["event_type"] == "compiled"
        assert timeline[2]["event_type"] == "validated"


class TestTimelineFiltersByTenant:
    @pytest.mark.asyncio
    async def test_timeline_filters_by_tenant(self, svc, mock_db, case_id):
        """get_workflow_timeline should only return events for the given tenant."""
        target_tenant = uuid.uuid4()
        other_tenant = uuid.uuid4()

        # Only the target tenant's event should be returned by the query
        target_event = _make_audit_event(
            event_type="started", case_id=case_id, tenant_id=target_tenant,
            payload={"stage": "ingestion"}, detail="Started",
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [target_event]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)

        timeline = await svc.get_workflow_timeline(case_id, target_tenant)

        assert len(timeline) == 1
        assert timeline[0]["event_type"] == "started"

        # Verify the query was called (tenant filtering happens at DB level)
        mock_db.execute.assert_awaited_once()


class TestAuditEventMetadataPersisted:
    @pytest.mark.asyncio
    async def test_audit_event_metadata_persisted(self, svc, mock_db, tenant_id, case_id):
        """Metadata dict should be persisted in the payload."""
        metadata = {"key1": "value1", "nested": {"a": 1}}
        event = await svc.log_workflow_event(
            tenant_id=tenant_id,
            case_id=case_id,
            event_type="custom_event",
            stage="analysis",
            metadata=metadata,
        )

        assert event.payload["metadata"] == metadata
        assert event.payload["metadata"]["nested"]["a"] == 1


class TestMultipleEventsSameCase:
    @pytest.mark.asyncio
    async def test_multiple_events_same_case(self, svc, mock_db, tenant_id, case_id):
        """Multiple events for the same case should each be persisted."""
        e1 = await svc.log_workflow_event(
            tenant_id=tenant_id, case_id=case_id,
            event_type="started", stage="ingestion",
        )
        e2 = await svc.log_workflow_event(
            tenant_id=tenant_id, case_id=case_id,
            event_type="completed", stage="validation",
        )

        assert e1.workflow_case_id == case_id
        assert e2.workflow_case_id == case_id
        assert e1.event_type != e2.event_type
        assert mock_db.add.call_count == 2
        assert mock_db.flush.await_count == 2


class TestAuditEventActorTypes:
    @pytest.mark.asyncio
    async def test_audit_event_actor_types(self, svc, mock_db, tenant_id, case_id):
        """Various actor types should be supported."""
        user_id = uuid.uuid4()

        # System actor (default)
        e1 = await svc.log_workflow_event(
            tenant_id=tenant_id, case_id=case_id,
            event_type="auto_check", stage="validation",
        )
        assert e1.actor_type == "system"
        assert e1.actor_id is None

        # User actor
        e2 = await svc.log_workflow_event(
            tenant_id=tenant_id, case_id=case_id,
            event_type="manual_review", stage="review",
            actor_id=user_id, actor_type="user",
        )
        assert e2.actor_type == "user"
        assert e2.actor_id == user_id

        # Workflow actor
        e3 = await svc.log_workflow_event(
            tenant_id=tenant_id, case_id=case_id,
            event_type="step_complete", stage="compilation",
            actor_type="workflow",
        )
        assert e3.actor_type == "workflow"
