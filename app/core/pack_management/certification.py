"""
Pack Certification System

Ensures domain packs meet quality standards before deployment to customers.
Every pack must pass certification before being made available for install.

Certification checks:
  1. Schema validation — all namespaces have required attributes
  2. Rule completeness — all reconciliation rules have valid object types and planes
  3. Version format — follows semantic versioning
  4. Breaking change detection — compared to previous version
  5. Content presence — pack must contain at least one namespace or rule
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.domain_pack_loader import DomainPack

logger = logging.getLogger(__name__)

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass
class CertificationResult:
    pack_id: str
    pack_version: str
    certified: bool
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    certified_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    certificate_id: str = ""

    def __post_init__(self):
        if not self.certificate_id:
            payload = f"{self.pack_id}{self.pack_version}{self.certified_at.isoformat()}"
            self.certificate_id = hashlib.sha256(payload.encode()).hexdigest()[:16]


class PackCertifier:
    """
    Runs certification checks on a domain pack before it can be installed.
    Produces a CertificationResult with pass/fail per check.
    """

    def certify(
        self,
        pack: DomainPack,
        previous_version: DomainPack | None = None,
    ) -> CertificationResult:
        checks_passed: list[str] = []
        checks_failed: list[str] = []
        warnings: list[str] = []

        # Check 1: Semantic versioning
        if SEMVER_PATTERN.match(pack.version):
            checks_passed.append(f"semver_format: {pack.version} is valid semver")
        else:
            checks_failed.append(
                f"semver_format: '{pack.version}' does not follow"
                f" semantic versioning (major.minor.patch)"
            )

        # Check 2: Pack has required metadata
        if pack.name and pack.description and len(pack.description) >= 20:
            checks_passed.append("metadata_complete: name and description present")
        else:
            checks_failed.append(
                "metadata_complete: pack must have name and description (min 20 chars)"
            )

        # Check 3: Namespace validation
        ns_issues: list[str] = []
        for ns in pack.namespaces:
            if not ns.name or not ns.version:
                ns_issues.append("namespace missing name or version")
            if not ns.domain_pack:
                ns_issues.append(f"namespace {ns.name} missing domain_pack attribution")
        if ns_issues:
            checks_failed.append(f"namespace_validation: {'; '.join(ns_issues)}")
        else:
            checks_passed.append(f"namespace_validation: {len(pack.namespaces)} namespaces valid")

        # Check 4: Reconciliation rule completeness
        rule_issues: list[str] = []
        for rule in pack.reconciliation_rules:
            if not rule.rule_id or not rule.rule_name:
                rule_issues.append("rule missing rule_id or rule_name")
            if not rule.source_plane or not rule.target_plane:
                rule_issues.append(f"rule {rule.rule_id} missing source_plane or target_plane")
            if not rule.description or len(rule.description) < 20:
                rule_issues.append(f"rule {rule.rule_id} description too short (min 20 chars)")
        if rule_issues:
            checks_failed.append(f"rule_completeness: {'; '.join(rule_issues[:3])}")
        else:
            checks_passed.append(f"rule_completeness: {len(pack.reconciliation_rules)} rules valid")

        # Check 5: Breaking change detection vs previous version
        if previous_version:
            removed_namespaces = {ns.name for ns in previous_version.namespaces} - {
                ns.name for ns in pack.namespaces
            }
            removed_rules = {r.rule_id for r in previous_version.reconciliation_rules} - {
                r.rule_id for r in pack.reconciliation_rules
            }
            if removed_namespaces:
                checks_failed.append(f"breaking_change: namespaces removed: {removed_namespaces}")
            elif removed_rules:
                warnings.append(
                    f"breaking_change_warning: reconciliation rules removed:"
                    f" {removed_rules} — verify no customer workflows"
                    f" depend on these"
                )
                checks_passed.append("breaking_change: no namespace removals detected")
            else:
                checks_passed.append("breaking_change: no breaking changes detected")
        else:
            checks_passed.append("breaking_change: first version — no previous version to compare")

        # Check 6: Pack has at least one namespace or one rule
        if not pack.namespaces and not pack.reconciliation_rules:
            checks_failed.append(
                "pack_content: pack must contain at least one namespace or one reconciliation rule"
            )
        else:
            checks_passed.append(
                f"pack_content: {len(pack.namespaces)} namespaces,"
                f" {len(pack.reconciliation_rules)} rules"
            )

        certified = len(checks_failed) == 0
        result = CertificationResult(
            pack_id=pack.pack_id,
            pack_version=pack.version,
            certified=certified,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            warnings=warnings,
        )
        logger.info(
            "Pack certification: %s v%s — %s (%d passed, %d failed)",
            pack.pack_id,
            pack.version,
            "CERTIFIED" if certified else "FAILED",
            len(checks_passed),
            len(checks_failed),
        )
        return result


# Module-level singleton
pack_certifier = PackCertifier()
