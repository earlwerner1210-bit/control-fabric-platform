"""
Release Guard Policy Profiles

Three presets. Simple toggles. No deep policy authoring.

startup_default:
  Required: CI/CD pass + Jira ticket
  Approval: 1 approver for HIGH/CRITICAL
  Blocks: force_deploy

regulated_default:
  Required: CI/CD pass + Jira ticket + security scan
  Approval: 1 approver for MEDIUM+
  Blocks: force_deploy, unreviewed_production_release

strict:
  Required: CI/CD + Jira + security scan + rollback plan
  Approval: 2 approvers for any production release
  Blocks: force_deploy, unreviewed_production_release, skip_testing
"""

from __future__ import annotations

from app.products.release_guard.domain.enums import PolicyProfileName, ReleaseRisk

PROFILES: dict[PolicyProfileName, dict] = {
    PolicyProfileName.STARTUP_DEFAULT: {
        "name": "Startup Default",
        "description": (
            "Lightweight rules for fast-moving teams. Requires a Jira ticket and passing CI."
        ),
        "required_evidence": ["build_result", "jira_ticket"],
        "blocked_action_types": ["force_deploy"],
        "require_approval_for_risk": [ReleaseRisk.HIGH, ReleaseRisk.CRITICAL],
        "approvers_required": 1,
        "toggles": {
            "require_jira_ticket": True,
            "require_pr_link": False,
            "require_ci_pass": True,
            "require_security_scan": False,
            "require_rollback_plan": False,
            "require_approval_for_medium": False,
            "block_force_deploy": True,
            "two_approver_for_critical": False,
        },
    },
    PolicyProfileName.REGULATED_DEFAULT: {
        "name": "Regulated Default",
        "description": (
            "For regulated environments."
            " Adds security scan and mandatory approval for all production releases."
        ),
        "required_evidence": ["build_result", "jira_ticket", "security_scan"],
        "blocked_action_types": ["force_deploy", "unreviewed_production_release"],
        "require_approval_for_risk": [
            ReleaseRisk.MEDIUM,
            ReleaseRisk.HIGH,
            ReleaseRisk.CRITICAL,
        ],
        "approvers_required": 1,
        "toggles": {
            "require_jira_ticket": True,
            "require_pr_link": True,
            "require_ci_pass": True,
            "require_security_scan": True,
            "require_rollback_plan": False,
            "require_approval_for_medium": True,
            "block_force_deploy": True,
            "two_approver_for_critical": False,
        },
    },
    PolicyProfileName.STRICT: {
        "name": "Strict Release Control",
        "description": (
            "Maximum governance. All evidence required. Two approvers for critical releases."
        ),
        "required_evidence": [
            "build_result",
            "jira_ticket",
            "security_scan",
            "rollback_plan",
        ],
        "blocked_action_types": ["force_deploy", "unreviewed_production_release"],
        "require_approval_for_risk": [
            ReleaseRisk.LOW,
            ReleaseRisk.MEDIUM,
            ReleaseRisk.HIGH,
            ReleaseRisk.CRITICAL,
        ],
        "approvers_required": 2,
        "toggles": {
            "require_jira_ticket": True,
            "require_pr_link": True,
            "require_ci_pass": True,
            "require_security_scan": True,
            "require_rollback_plan": True,
            "require_approval_for_medium": True,
            "block_force_deploy": True,
            "two_approver_for_critical": True,
        },
    },
}


def get_profile(name: PolicyProfileName) -> dict:
    return PROFILES.get(name, PROFILES[PolicyProfileName.STARTUP_DEFAULT])


def get_required_evidence(name: PolicyProfileName) -> list[str]:
    return get_profile(name)["required_evidence"]


def get_blocked_actions(name: PolicyProfileName) -> list[str]:
    return get_profile(name)["blocked_action_types"]


def needs_approval(
    profile_name: PolicyProfileName,
    risk: ReleaseRisk,
) -> bool:
    profile = get_profile(profile_name)
    return risk in profile["require_approval_for_risk"]


def approvers_required(profile_name: PolicyProfileName) -> int:
    return get_profile(profile_name)["approvers_required"]
