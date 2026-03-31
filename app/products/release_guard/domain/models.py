"""
Release Guard — domain models.

These are the product-facing models that SMB customers interact with.
They are simpler than the underlying platform models and use
plain business language.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.products.release_guard.domain.enums import (
    ApprovalStatus,
    EvidenceType,
    IntegrationProvider,
    OnboardingStep,
    PolicyProfileName,
    ReleaseRisk,
    ReleaseStatus,
    WorkspacePlan,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


@dataclass
class Workspace:
    workspace_id: str = field(default_factory=_uid)
    name: str = ""
    slug: str = ""
    plan: WorkspacePlan = WorkspacePlan.STARTER
    tenant_id: str = "default"
    created_by: str = ""
    created_at: str = field(default_factory=_now)
    onboarding_complete: bool = False
    onboarding_step: OnboardingStep = OnboardingStep.WELCOME
    policy_profile: PolicyProfileName = PolicyProfileName.STARTUP_DEFAULT
    member_count: int = 1
    status: str = "active"


@dataclass
class ReleaseRequest:
    release_id: str = field(default_factory=_uid)
    workspace_id: str = ""
    tenant_id: str = "default"
    title: str = ""
    description: str = ""
    service_name: str = ""
    environment: str = "production"
    risk_level: ReleaseRisk = ReleaseRisk.MEDIUM
    status: ReleaseStatus = ReleaseStatus.DRAFT
    submitted_by: str = ""
    created_at: str = field(default_factory=_now)
    submitted_at: str | None = None
    decided_at: str | None = None
    blocked_reason: str | None = None
    blocked_checks: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    approval_steps: list[ApprovalStep] = field(default_factory=list)
    package_id: str | None = None  # underlying evidence package ID
    audit_trail: list[dict] = field(default_factory=list)


@dataclass
class EvidenceItem:
    evidence_id: str = field(default_factory=_uid)
    release_id: str = ""
    evidence_type: EvidenceType = EvidenceType.JIRA_TICKET
    title: str = ""
    reference: str = ""  # ticket ID, PR number, build ID, URL
    url: str = ""
    verified: bool = False
    added_by: str = ""
    added_at: str = field(default_factory=_now)


@dataclass
class ApprovalStep:
    step_id: str = field(default_factory=_uid)
    release_id: str = ""
    approver_id: str = ""
    approver_email: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    decision_note: str = ""
    requested_at: str = field(default_factory=_now)
    decided_at: str | None = None
    reminder_sent_at: str | None = None
    sla_hours: int = 24


@dataclass
class PolicyProfile:
    profile_id: str = field(default_factory=_uid)
    workspace_id: str = ""
    name: PolicyProfileName = PolicyProfileName.STARTUP_DEFAULT
    toggles: dict = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


@dataclass
class Integration:
    integration_id: str = field(default_factory=_uid)
    workspace_id: str = ""
    provider: IntegrationProvider = IntegrationProvider.GITHUB
    status: str = "disconnected"  # connected / disconnected / error
    config: dict = field(default_factory=dict)
    last_sync_at: str | None = None
    error_message: str | None = None
    connected_at: str | None = None
    connected_by: str = ""


@dataclass
class WorkspaceMember:
    member_id: str = field(default_factory=_uid)
    workspace_id: str = ""
    user_id: str = ""
    email: str = ""
    name: str = ""
    role: str = "operator"  # admin / approver / operator / viewer
    invited_at: str = field(default_factory=_now)
    accepted_at: str | None = None


@dataclass
class DashboardSummary:
    workspace_id: str = ""
    period_days: int = 30
    total_releases: int = 0
    approved: int = 0
    blocked: int = 0
    pending_approval: int = 0
    approval_rate_pct: float = 0.0
    avg_time_to_decision_hours: float = 0.0
    top_block_reasons: list[dict] = field(default_factory=list)
    recent_releases: list[dict] = field(default_factory=list)
    audit_readiness_grade: str = "B"
    pending_approvals: int = 0
    generated_at: str = field(default_factory=_now)
