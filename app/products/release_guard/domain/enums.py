"""Release Guard — domain enumerations."""

from __future__ import annotations

from enum import Enum


class ReleaseStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"  # submitted, awaiting validation
    BLOCKED = "blocked"  # failed validation — needs fixing
    APPROVED = "approved"  # passed all checks
    CANCELLED = "cancelled"
    RELEASED = "released"  # dispatched to production


class ReleaseRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceType(str, Enum):
    JIRA_TICKET = "jira_ticket"
    GITHUB_PR = "github_pr"
    BUILD_RESULT = "build_result"
    SECURITY_SCAN = "security_scan"
    ROLLBACK_PLAN = "rollback_plan"
    APPROVAL_NOTE = "approval_note"
    CHANGE_REQUEST = "change_request"
    TEST_REPORT = "test_report"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class WorkspacePlan(str, Enum):
    STARTER = "starter"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


class PolicyProfileName(str, Enum):
    STARTUP_DEFAULT = "startup_default"
    REGULATED_DEFAULT = "regulated_default"
    STRICT = "strict"


class OnboardingStep(str, Enum):
    WELCOME = "welcome"
    CONNECT_GITHUB = "connect_github"
    CONNECT_JIRA = "connect_jira"
    SELECT_PROFILE = "select_profile"
    INVITE_APPROVER = "invite_approver"
    RUN_DEMO = "run_demo"
    COMPLETE = "complete"


class IntegrationProvider(str, Enum):
    GITHUB = "github"
    JIRA = "jira"
    SLACK = "slack"
    AZURE_DEVOPS = "azure_devops"
    SERVICENOW = "servicenow"
