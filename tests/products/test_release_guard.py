from __future__ import annotations


class TestWorkspaceService:
    def test_create_workspace(self) -> None:
        from app.products.release_guard.services.workspace_service import WorkspaceService

        svc = WorkspaceService()
        ws = svc.create("Acme Engineering", "admin@acme.com")
        assert ws.name == "Acme Engineering"
        assert ws.slug == "acme-engineering"
        assert ws.member_count == 1

    def test_invite_member(self) -> None:
        from app.products.release_guard.services.workspace_service import WorkspaceService

        svc = WorkspaceService()
        ws = svc.create("Test Corp", "admin@test.com")
        member = svc.invite_member(ws.workspace_id, "dev@test.com", "operator")
        assert member.email == "dev@test.com"
        assert member.role == "operator"

    def test_advance_onboarding(self) -> None:
        from app.products.release_guard.domain.enums import OnboardingStep
        from app.products.release_guard.services.workspace_service import WorkspaceService

        svc = WorkspaceService()
        ws = svc.create("Onboard Co", "admin@ob.com")
        assert ws.onboarding_step == OnboardingStep.WELCOME
        ws = svc.advance_onboarding(ws.workspace_id, OnboardingStep.WELCOME)
        assert ws.onboarding_step == OnboardingStep.CONNECT_GITHUB


class TestReleaseRequestService:
    def _make_workspace(self):
        from app.products.release_guard.services.workspace_service import WorkspaceService

        svc = WorkspaceService()
        return svc.create("Test WS", "admin@test.com")

    def test_create_release(self) -> None:
        from app.products.release_guard.domain.enums import ReleaseRisk
        from app.products.release_guard.services.release_request_service import (
            ReleaseRequestService,
        )

        ws = self._make_workspace()
        svc = ReleaseRequestService()
        release = svc.create(
            workspace_id=ws.workspace_id,
            tenant_id="default",
            title="API Gateway v2.0",
            service_name="api-gateway",
            environment="production",
            risk_level=ReleaseRisk.HIGH,
            submitted_by="engineer@test.com",
        )
        assert release.title == "API Gateway v2.0"
        assert release.status.value == "draft"

    def test_submit_blocked_missing_evidence(self) -> None:
        from app.products.release_guard.domain.enums import (
            PolicyProfileName,
            ReleaseRisk,
            ReleaseStatus,
        )
        from app.products.release_guard.services.release_request_service import (
            ReleaseRequestService,
        )

        ws = self._make_workspace()
        svc = ReleaseRequestService()
        release = svc.create(
            ws.workspace_id,
            "default",
            "Test Release",
            "svc",
            "production",
            ReleaseRisk.MEDIUM,
            "eng@test.com",
        )
        result = svc.submit(release.release_id, PolicyProfileName.STARTUP_DEFAULT)
        assert result.status == ReleaseStatus.BLOCKED
        assert len(result.missing_evidence) > 0

    def test_submit_approved_with_evidence(self) -> None:
        from app.products.release_guard.domain.enums import (
            EvidenceType,
            PolicyProfileName,
            ReleaseRisk,
            ReleaseStatus,
        )
        from app.products.release_guard.services.release_request_service import (
            ReleaseRequestService,
        )

        ws = self._make_workspace()
        svc = ReleaseRequestService()
        release = svc.create(
            ws.workspace_id,
            "default",
            "Evidenced Release",
            "svc",
            "production",
            ReleaseRisk.LOW,
            "eng@test.com",
        )
        svc.add_evidence(
            release.release_id,
            EvidenceType.BUILD_RESULT,
            "CI Pass",
            "build-123",
            "",
            "eng@test.com",
        )
        svc.add_evidence(
            release.release_id,
            EvidenceType.JIRA_TICKET,
            "CR-456",
            "CR-456",
            "",
            "eng@test.com",
        )
        result = svc.submit(release.release_id, PolicyProfileName.STARTUP_DEFAULT)
        # Low risk with startup profile -> approved (no approval needed)
        assert result.status in (ReleaseStatus.APPROVED, ReleaseStatus.PENDING)

    def test_check_evidence_completeness(self) -> None:
        from app.products.release_guard.domain.enums import (
            EvidenceType,
            PolicyProfileName,
            ReleaseRisk,
        )
        from app.products.release_guard.services.release_request_service import (
            ReleaseRequestService,
        )

        ws = self._make_workspace()
        svc = ReleaseRequestService()
        release = svc.create(
            ws.workspace_id,
            "default",
            "Check Release",
            "svc",
            "production",
            ReleaseRisk.MEDIUM,
            "eng@test.com",
        )
        check = svc.check_evidence_completeness(
            release.release_id, PolicyProfileName.STARTUP_DEFAULT
        )
        assert check["complete"] is False
        assert len(check["missing"]) > 0
        svc.add_evidence(release.release_id, EvidenceType.BUILD_RESULT, "CI", "b1", "", "eng")
        svc.add_evidence(release.release_id, EvidenceType.JIRA_TICKET, "CR-1", "CR-1", "", "eng")
        check2 = svc.check_evidence_completeness(
            release.release_id, PolicyProfileName.STARTUP_DEFAULT
        )
        assert check2["complete"] is True

    def test_audit_trail_populated(self) -> None:
        from app.products.release_guard.domain.enums import ReleaseRisk
        from app.products.release_guard.services.release_request_service import (
            ReleaseRequestService,
        )

        ws = self._make_workspace()
        svc = ReleaseRequestService()
        release = svc.create(
            ws.workspace_id,
            "default",
            "Audit Test",
            "svc",
            "production",
            ReleaseRisk.LOW,
            "eng@test.com",
        )
        assert len(release.audit_trail) >= 1
        assert release.audit_trail[0]["event"] == "created"


class TestApprovalService:
    def test_request_and_approve(self) -> None:
        from app.products.release_guard.domain.enums import ApprovalStatus
        from app.products.release_guard.services.approval_service import ApprovalService

        svc = ApprovalService()
        step = svc.request("release-001", "approver@company.com")
        assert step.status == ApprovalStatus.PENDING
        approved = svc.approve(step.step_id, "approver@company.com", "Looks good")
        assert approved.status == ApprovalStatus.APPROVED

    def test_pending_inbox(self) -> None:
        from app.products.release_guard.services.approval_service import ApprovalService

        svc = ApprovalService()
        svc.request("rls-inbox-1", "bob@company.com")
        svc.request("rls-inbox-2", "bob@company.com")
        # Note: inbox lookup requires releases to exist — just test it doesn't crash
        inbox = svc.get_pending_inbox("bob@company.com")
        assert isinstance(inbox, list)


class TestPolicyProfiles:
    def test_startup_default_requires_ci_and_ticket(self) -> None:
        from app.products.release_guard.domain.enums import PolicyProfileName
        from app.products.release_guard.policies.profiles import get_required_evidence

        evidence = get_required_evidence(PolicyProfileName.STARTUP_DEFAULT)
        assert "build_result" in evidence
        assert "jira_ticket" in evidence

    def test_strict_requires_all_four(self) -> None:
        from app.products.release_guard.domain.enums import PolicyProfileName
        from app.products.release_guard.policies.profiles import get_required_evidence

        evidence = get_required_evidence(PolicyProfileName.STRICT)
        assert len(evidence) == 4

    def test_needs_approval_high_risk_startup(self) -> None:
        from app.products.release_guard.domain.enums import PolicyProfileName, ReleaseRisk
        from app.products.release_guard.policies.profiles import needs_approval

        assert needs_approval(PolicyProfileName.STARTUP_DEFAULT, ReleaseRisk.HIGH) is True
        assert needs_approval(PolicyProfileName.STARTUP_DEFAULT, ReleaseRisk.LOW) is False

    def test_strict_needs_approval_for_all_risk(self) -> None:
        from app.products.release_guard.domain.enums import PolicyProfileName, ReleaseRisk
        from app.products.release_guard.policies.profiles import needs_approval

        for risk in ReleaseRisk:
            assert needs_approval(PolicyProfileName.STRICT, risk) is True


class TestDashboardService:
    def test_dashboard_summary_empty_workspace(self) -> None:
        from app.products.release_guard.services.dashboard_service import DashboardService

        svc = DashboardService()
        summary = svc.get_summary("empty-ws-001", period_days=30)
        assert summary.total_releases == 0
        assert summary.approved == 0
        assert summary.blocked == 0
