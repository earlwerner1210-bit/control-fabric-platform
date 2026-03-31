from __future__ import annotations

import json

import pytest


def _make_workspace():
    from app.products.release_guard.services.workspace_service import WorkspaceService

    svc = WorkspaceService()
    return svc.create("Phase2 WS", "admin@test.com")


def _make_blocked_release(workspace_id: str, tenant_id: str = "default"):
    from app.products.release_guard.domain.enums import PolicyProfileName, ReleaseRisk
    from app.products.release_guard.services.release_request_service import (
        ReleaseRequestService,
    )

    svc = ReleaseRequestService()
    release = svc.create(
        workspace_id,
        tenant_id,
        "Test Release",
        "test-svc",
        "production",
        ReleaseRisk.HIGH,
        "eng@test.com",
    )
    result = svc.submit(release.release_id, PolicyProfileName.REGULATED_DEFAULT)
    return result


class TestExceptionService:
    def test_raise_exception_on_blocked_release(self) -> None:
        from app.products.release_guard.services.exception_service import ExceptionService

        ws = _make_workspace()
        release = _make_blocked_release(ws.workspace_id)

        svc = ExceptionService()
        exc = svc.raise_exception(
            release_id=release.release_id,
            workspace_id=ws.workspace_id,
            raised_by="eng@test.com",
            reason="Production incident — must deploy immediately",
            business_justification="Revenue impact $50k/hour",
            approver_email="cto@test.com",
            urgency="critical",
        )
        assert exc.status == "pending_approval"
        assert exc.urgency == "critical"
        assert len(exc.audit_hash) == 16

    def test_cannot_raise_exception_on_approved_release(self) -> None:
        from app.products.release_guard.domain.enums import (
            EvidenceType,
            PolicyProfileName,
            ReleaseRisk,
        )
        from app.products.release_guard.services.exception_service import ExceptionService
        from app.products.release_guard.services.release_request_service import (
            ReleaseRequestService,
        )

        ws = _make_workspace()
        rrs = ReleaseRequestService()
        release = rrs.create(
            ws.workspace_id,
            "default",
            "Approved",
            "svc",
            "production",
            ReleaseRisk.LOW,
            "eng@test.com",
        )
        rrs.add_evidence(release.release_id, EvidenceType.BUILD_RESULT, "CI", "b1", "", "eng")
        rrs.add_evidence(release.release_id, EvidenceType.JIRA_TICKET, "CR-1", "CR-1", "", "eng")
        rrs.submit(release.release_id, PolicyProfileName.STARTUP_DEFAULT)

        svc = ExceptionService()
        with pytest.raises(ValueError, match="Exceptions can only be raised for blocked"):
            svc.raise_exception(
                release.release_id,
                ws.workspace_id,
                "eng",
                "reason",
                "justification",
                "cto@test.com",
            )

    def test_approve_exception_changes_release_status(self) -> None:
        from app.products.release_guard.domain.enums import ReleaseStatus
        from app.products.release_guard.services.exception_service import ExceptionService
        from app.products.release_guard.services.release_request_service import (
            release_request_service,
        )

        ws = _make_workspace()
        release = _make_blocked_release(ws.workspace_id)

        svc = ExceptionService()
        exc = svc.raise_exception(
            release.release_id,
            ws.workspace_id,
            "eng@test.com",
            "urgent",
            "justification",
            "cto@test.com",
        )
        svc.approve_exception(exc.exception_id, "cto@test.com", "Approved — P1 incident")
        updated = release_request_service.get(release.release_id)
        assert updated.status == ReleaseStatus.APPROVED

    def test_list_pending_for_approver(self) -> None:
        from app.products.release_guard.services.exception_service import ExceptionService

        ws = _make_workspace()
        release = _make_blocked_release(ws.workspace_id)
        svc = ExceptionService()
        svc.raise_exception(
            release.release_id,
            ws.workspace_id,
            "eng@test.com",
            "urgent",
            "just",
            "approver@test.com",
        )
        pending = svc.get_pending_for_approver("approver@test.com")
        assert isinstance(pending, list)


class TestExportService:
    def test_export_releases_produces_csv(self) -> None:
        from app.products.release_guard.services.export_service import ExportService

        ws = _make_workspace()
        svc = ExportService()
        job = svc.export_releases(ws.workspace_id, "admin@test.com", format="csv")
        assert job.format == "csv"
        assert job.export_type == "releases"
        assert len(job.content_hash) > 0

    def test_export_content_is_retrievable(self) -> None:
        from app.products.release_guard.services.export_service import ExportService

        ws = _make_workspace()
        svc = ExportService()
        job = svc.export_releases(ws.workspace_id, "admin@test.com")
        content = svc.get_content(job.export_id)
        assert isinstance(content, str)

    def test_export_json_format(self) -> None:
        from app.products.release_guard.services.export_service import ExportService

        ws = _make_workspace()
        svc = ExportService()
        job = svc.export_exceptions(ws.workspace_id, "admin@test.com", format="json")
        content = svc.get_content(job.export_id)
        parsed = json.loads(content)
        assert isinstance(parsed, list)

    def test_export_content_hash_is_deterministic(self) -> None:
        from app.products.release_guard.services.export_service import ExportService

        ws = _make_workspace()
        svc = ExportService()
        job1 = svc.export_releases(ws.workspace_id, "a@test.com")
        job2 = svc.export_releases(ws.workspace_id, "b@test.com")
        # Same content → same hash
        assert job1.content_hash == job2.content_hash


class TestDemoService:
    def test_seed_creates_four_scenarios(self) -> None:
        from app.products.release_guard.services.demo_service import DemoService

        ws = _make_workspace()
        svc = DemoService()
        result = svc.seed(ws.workspace_id)
        assert result["scenarios_created"] == 4
        scenarios = [s["scenario"] for s in result["scenarios"]]
        assert "blocked_release" in scenarios
        assert "approved_release" in scenarios
        assert "pending_approval" in scenarios
        assert "exception_request" in scenarios

    def test_seed_blocked_release_is_actually_blocked(self) -> None:
        from app.products.release_guard.domain.enums import ReleaseStatus
        from app.products.release_guard.services.demo_service import DemoService
        from app.products.release_guard.services.release_request_service import (
            release_request_service,
        )

        ws = _make_workspace()
        svc = DemoService()
        result = svc.seed(ws.workspace_id)
        blocked_scenario = next(
            s for s in result["scenarios"] if s["scenario"] == "blocked_release"
        )
        release = release_request_service.get(blocked_scenario["release_id"])
        assert release.status == ReleaseStatus.BLOCKED

    def test_seed_approved_release_is_approved(self) -> None:
        from app.products.release_guard.domain.enums import ReleaseStatus
        from app.products.release_guard.services.demo_service import DemoService
        from app.products.release_guard.services.release_request_service import (
            release_request_service,
        )

        ws = _make_workspace()
        svc = DemoService()
        result = svc.seed(ws.workspace_id)
        approved_scenario = next(
            s for s in result["scenarios"] if s["scenario"] == "approved_release"
        )
        release = release_request_service.get(approved_scenario["release_id"])
        assert release.status == ReleaseStatus.APPROVED

    def test_reset_reseeds_cleanly(self) -> None:
        from app.products.release_guard.services.demo_service import DemoService

        ws = _make_workspace()
        svc = DemoService()
        first = svc.seed(ws.workspace_id)
        second = svc.reset(ws.workspace_id)
        assert second["scenarios_created"] == 4
        # Release IDs should be different after reset
        first_ids = {s["release_id"] for s in first["scenarios"] if "release_id" in s}
        second_ids = {s["release_id"] for s in second["scenarios"] if "release_id" in s}
        assert first_ids != second_ids
