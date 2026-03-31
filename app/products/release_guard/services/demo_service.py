"""
Demo Scenario Service

Seeds realistic release scenarios for onboarding and demos.
Creates a complete picture: blocked release, approved release,
pending approval, and an exception request.

Critical for conversion — the first thing a prospect sees
should be a working, realistic scenario they recognise.

One-click reset returns workspace to clean demo state.
"""

from __future__ import annotations

import logging

from app.products.release_guard.domain.enums import (
    EvidenceType,
    PolicyProfileName,
    ReleaseRisk,
)

logger = logging.getLogger(__name__)


class DemoService:
    """Seeds demo scenarios and resets demo workspaces."""

    def seed(
        self,
        workspace_id: str,
        policy_profile: PolicyProfileName = PolicyProfileName.REGULATED_DEFAULT,
    ) -> dict:
        """
        Seed 4 demo scenarios:
        1. Blocked release — missing security scan
        2. Approved release — all evidence complete
        3. Pending approval — evidence complete, awaiting review
        4. Exception request — urgent fix without full evidence
        """
        from app.products.release_guard.services.approval_service import approval_service
        from app.products.release_guard.services.exception_service import exception_service
        from app.products.release_guard.services.release_request_service import (
            release_request_service,
        )

        created = []

        # ── Scenario 1: BLOCKED — missing security scan ──────────────────────
        blocked = release_request_service.create(
            workspace_id=workspace_id,
            tenant_id="default",
            title="Payment API v3.1 — production release",
            service_name="payment-api",
            environment="production",
            risk_level=ReleaseRisk.HIGH,
            submitted_by="alice@demo.com",
            description="Monthly release — new payment processor integration",
        )
        release_request_service.add_evidence(
            blocked.release_id,
            EvidenceType.BUILD_RESULT,
            "CI pipeline passed — all 847 tests green",
            "build-2026-04-01-847",
            "https://ci.demo.com/builds/847",
            "alice@demo.com",
        )
        release_request_service.add_evidence(
            blocked.release_id,
            EvidenceType.JIRA_TICKET,
            "PAY-2341: Add Stripe payment processor",
            "PAY-2341",
            "https://jira.demo.com/PAY-2341",
            "alice@demo.com",
        )
        # Missing: security_scan — this will cause the block
        release_request_service.submit(blocked.release_id, policy_profile)
        created.append(
            {
                "scenario": "blocked_release",
                "release_id": blocked.release_id,
                "title": blocked.title,
                "status": blocked.status.value,
                "why": "Missing security scan — required by regulated_default profile",
            }
        )

        # ── Scenario 2: APPROVED — all evidence complete ──────────────────────
        approved = release_request_service.create(
            workspace_id=workspace_id,
            tenant_id="default",
            title="User Auth service v2.0 — production release",
            service_name="auth-service",
            environment="production",
            risk_level=ReleaseRisk.MEDIUM,
            submitted_by="bob@demo.com",
            description="OAuth 2.0 migration — all tests passing, security reviewed",
        )
        release_request_service.add_evidence(
            approved.release_id,
            EvidenceType.BUILD_RESULT,
            "All tests passed — 1,243 unit + 89 integration",
            "build-2026-04-01-1243",
            "https://ci.demo.com/builds/1243",
            "bob@demo.com",
        )
        release_request_service.add_evidence(
            approved.release_id,
            EvidenceType.JIRA_TICKET,
            "AUTH-891: Migrate to OAuth 2.0",
            "AUTH-891",
            "https://jira.demo.com/AUTH-891",
            "bob@demo.com",
        )
        release_request_service.add_evidence(
            approved.release_id,
            EvidenceType.GITHUB_PR,
            "PR #234: OAuth 2.0 migration",
            "234",
            "https://github.com/demo/auth-service/pull/234",
            "bob@demo.com",
        )
        release_request_service.add_evidence(
            approved.release_id,
            EvidenceType.SECURITY_SCAN,
            "Snyk security scan — 0 critical, 0 high vulnerabilities",
            "snyk-scan-2026-04-01",
            "https://snyk.io/results/demo-2026-04-01",
            "bob@demo.com",
        )
        release_request_service.submit(
            approved.release_id, PolicyProfileName.STARTUP_DEFAULT
        )
        created.append(
            {
                "scenario": "approved_release",
                "release_id": approved.release_id,
                "title": approved.title,
                "status": approved.status.value,
                "why": "All required evidence provided — auto-approved by startup profile",
            }
        )

        # ── Scenario 3: PENDING APPROVAL ─────────────────────────────────────
        pending = release_request_service.create(
            workspace_id=workspace_id,
            tenant_id="default",
            title="Database schema migration v4 — production",
            service_name="core-db",
            environment="production",
            risk_level=ReleaseRisk.HIGH,
            submitted_by="carol@demo.com",
            description="Add new customer segments table — irreversible migration",
        )
        for ev_type, title, ref, url in [
            (
                EvidenceType.BUILD_RESULT,
                "Migration tests passed — dry run on staging",
                "build-db-2026",
                "https://ci.demo.com/db",
            ),
            (
                EvidenceType.JIRA_TICKET,
                "DB-445: Customer segments schema",
                "DB-445",
                "https://jira.demo.com/DB-445",
            ),
            (
                EvidenceType.SECURITY_SCAN,
                "No vulnerabilities in migration scripts",
                "scan-db-2026",
                "https://snyk.io/db",
            ),
        ]:
            release_request_service.add_evidence(
                pending.release_id,
                ev_type,
                title,
                ref,
                url,
                "carol@demo.com",
            )
        release_request_service.submit(pending.release_id, policy_profile)
        step = approval_service.request(
            pending.release_id, "manager@demo.com", sla_hours=24
        )
        created.append(
            {
                "scenario": "pending_approval",
                "release_id": pending.release_id,
                "step_id": step.step_id,
                "title": pending.title,
                "status": pending.status.value,
                "approver": "manager@demo.com",
                "why": "Evidence complete — awaiting manager approval (HIGH risk requires human review)",
            }
        )

        # ── Scenario 4: EXCEPTION — urgent hotfix ─────────────────────────────
        hotfix = release_request_service.create(
            workspace_id=workspace_id,
            tenant_id="default",
            title="URGENT: Security patch CVE-2026-0142 — immediate deploy",
            service_name="api-gateway",
            environment="production",
            risk_level=ReleaseRisk.CRITICAL,
            submitted_by="dave@demo.com",
            description="Critical security vulnerability — must deploy within 2 hours",
        )
        release_request_service.add_evidence(
            hotfix.release_id,
            EvidenceType.BUILD_RESULT,
            "Hotfix build passed",
            "build-hotfix-142",
            "",
            "dave@demo.com",
        )
        release_request_service.submit(hotfix.release_id, policy_profile)
        exc = exception_service.raise_exception(
            release_id=hotfix.release_id,
            workspace_id=workspace_id,
            raised_by="dave@demo.com",
            reason="Critical security vulnerability CVE-2026-0142 being actively exploited",
            business_justification=(
                "Active exploitation detected in production. "
                "2-hour SLA to patch. Security team has approved emergency deployment."
            ),
            approver_email="cto@demo.com",
            urgency="critical",
        )
        created.append(
            {
                "scenario": "exception_request",
                "release_id": hotfix.release_id,
                "exception_id": exc.exception_id,
                "title": hotfix.title,
                "status": "pending_approval",
                "approver": "cto@demo.com",
                "why": "Emergency exception — missing security scan but active CVE requires immediate action",
            }
        )

        logger.info(
            "Demo seeded: workspace=%s scenarios=%d",
            workspace_id[:8],
            len(created),
        )
        return {
            "workspace_id": workspace_id,
            "scenarios_created": len(created),
            "scenarios": created,
            "demo_credentials": {
                "engineer": "alice@demo.com / bob@demo.com / carol@demo.com",
                "approver": "manager@demo.com",
                "cto": "cto@demo.com",
            },
            "what_to_show": [
                f"Blocked release: /releases/{created[0]['release_id']}",
                f"Approved release: /releases/{created[1]['release_id']}",
                "Pending approval: /approvals/inbox?approver_email=manager@demo.com",
                f"Exception request: /rg/exceptions/{created[3]['exception_id']}",
            ],
        }

    def reset(self, workspace_id: str) -> dict:
        """Clear all demo data and re-seed from scratch."""
        from app.products.release_guard.services.release_request_service import (
            _releases,
        )

        demo_release_ids = [
            rid for rid, r in _releases.items() if r.workspace_id == workspace_id
        ]
        for rid in demo_release_ids:
            del _releases[rid]

        return self.seed(workspace_id)

    def get_status(self, workspace_id: str) -> dict:
        from app.products.release_guard.services.release_request_service import (
            release_request_service,
        )

        releases = release_request_service.list_for_workspace(workspace_id, limit=20)
        return {
            "workspace_id": workspace_id,
            "total_releases": len(releases),
            "has_demo_data": any(r.submitted_by.endswith("@demo.com") for r in releases),
            "release_statuses": {
                r.status.value: sum(1 for rel in releases if rel.status == r.status)
                for r in releases
            },
        }


demo_service = DemoService()
