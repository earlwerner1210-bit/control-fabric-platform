"""
Platform Defaults — opinionated out-of-the-box configuration.

Covers:
  - Default policies (production, staging, hotfix)
  - Default severity thresholds
  - Default evidence requirements per release type
  - Default role mappings
  - Default reconciliation rules
  - Default exception rules
"""

from __future__ import annotations

SEVERITY_THRESHOLDS = {
    "must_block_above": 75.0,
    "requires_review_above": 40.0,
    "monitor_above": 10.0,
    "noise_below": 10.0,
    "production_multiplier": 1.5,
    "staging_multiplier": 1.1,
    "dev_multiplier": 0.7,
    "age_amplification_starts_hours": 48,
    "max_age_amplification": 0.3,
}

DEFAULT_POLICIES = [
    {
        "name": "Production Release Policy",
        "description": "Governs all production environment releases. Enforced by default.",
        "blocked_action_types": ["unreviewed_production_release", "force_deploy"],
        "required_origins_for": {
            "production_release": ["human_operator", "api_request"],
        },
        "applies_to_environment": "production",
        "min_approvers": 2,
        "required_evidence_types": ["ci_result", "security_scan", "load_test"],
    },
    {
        "name": "Staging Release Policy",
        "description": "Governs staging environment releases.",
        "blocked_action_types": ["force_deploy"],
        "applies_to_environment": "staging",
        "min_approvers": 1,
        "required_evidence_types": ["ci_result"],
    },
    {
        "name": "Hotfix Policy",
        "description": (
            "Emergency hotfix — requires CISO sign-off and mandatory post-incident review."
        ),
        "blocked_action_types": [],
        "applies_to_environment": "production",
        "min_approvers": 1,
        "required_evidence_types": ["incident_ticket"],
        "post_release_review_required": True,
        "max_exception_duration_hours": 4,
    },
    {
        "name": "AI Action Policy",
        "description": (
            "Governs all AI-originated actions platform-wide. AI must always provide evidence."
        ),
        "blocked_action_types": [],
        "required_origins_for": {},
        "special_rules": ["ai_inference_always_requires_evidence"],
    },
]

DEFAULT_EVIDENCE_REQUIREMENTS = [
    {
        "name": "CI/CD Pass",
        "evidence_type": "ci_result",
        "freshness_ttl_hours": 24,
        "required_for": ["production_release", "staging_release"],
        "description": "Passing CI/CD pipeline run with test results.",
        "minimum_test_coverage_pct": 70.0,
    },
    {
        "name": "Security Scan",
        "evidence_type": "security_scan",
        "freshness_ttl_hours": 72,
        "required_for": ["production_release"],
        "description": "Passing security vulnerability scan (no critical/high findings).",
    },
    {
        "name": "Load Test",
        "evidence_type": "load_test",
        "freshness_ttl_hours": 168,
        "required_for": ["production_release"],
        "description": "Load test confirming p99 latency within SLA.",
    },
    {
        "name": "Incident Ticket",
        "evidence_type": "incident_ticket",
        "freshness_ttl_hours": 1,
        "required_for": ["hotfix_release"],
        "description": "Active incident ticket confirming production impact.",
    },
    {
        "name": "Change Request",
        "evidence_type": "change_request",
        "freshness_ttl_hours": 168,
        "required_for": ["database_migration"],
        "description": "Approved change request with rollback procedure.",
    },
]

DEFAULT_ROLE_MAPPINGS = {
    "oidc_group_mappings": {
        "platform-admin": "platform_admin",
        "admin": "platform_admin",
        "engineering-lead": "approver",
        "senior-engineer": "reviewer",
        "engineer": "operator",
        "sre": "operator",
        "security": "reviewer",
        "ciso": "approver",
        "auditor": "auditor",
        "compliance": "auditor",
        "devops": "operator",
        "release-manager": "approver",
        "domain-owner": "domain_owner",
    },
    "default_role": "operator",
    "protected_roles": ["platform_admin"],
}

DEFAULT_EXCEPTION_RULES = {
    "max_duration_hours": {
        "critical": 4,
        "high": 24,
        "medium": 72,
        "low": 168,
    },
    "required_compensating_controls": {
        "production_release": ["monitoring_active", "rollback_verified"],
        "database_migration": ["backup_verified", "dba_monitoring"],
    },
    "auto_revoke_on_expiry": True,
    "post_exception_review_required": True,
    "max_concurrent_exceptions_per_user": 2,
    "escalation_required_above_risk": "high",
}

DEFAULT_DASHBOARD_METRICS = [
    {
        "id": "open_critical_cases",
        "label": "Critical cases",
        "type": "count",
        "filter": {"severity": "critical", "status": "open"},
    },
    {
        "id": "release_gate_pass_rate",
        "label": "Gate pass rate (24h)",
        "type": "percentage",
        "window_hours": 24,
    },
    {
        "id": "mean_time_to_resolve",
        "label": "Mean time to resolve",
        "type": "duration_hours",
    },
    {
        "id": "evidence_completeness",
        "label": "Evidence completeness",
        "type": "percentage",
    },
    {
        "id": "active_exceptions",
        "label": "Active exceptions",
        "type": "count",
    },
    {
        "id": "ungoverned_releases_blocked",
        "label": "Ungoverned releases blocked (7d)",
        "type": "count",
        "window_days": 7,
    },
]


def get_all_defaults() -> dict:
    """Return all platform defaults as a single configuration object."""
    return {
        "severity_thresholds": SEVERITY_THRESHOLDS,
        "policies": DEFAULT_POLICIES,
        "evidence_requirements": DEFAULT_EVIDENCE_REQUIREMENTS,
        "role_mappings": DEFAULT_ROLE_MAPPINGS,
        "exception_rules": DEFAULT_EXCEPTION_RULES,
        "dashboard_metrics": DEFAULT_DASHBOARD_METRICS,
    }
