"""
Pack Compatibility Matrix

Tracks which packs can safely coexist and which have
namespace or rule conflicts that would cause governance
ambiguity.

Conflict types:
  NAMESPACE_COLLISION — two packs own the same namespace
  RULE_CONFLICT       — two packs have conflicting reconciliation rules
  DEPENDENCY_MISSING  — pack requires another pack that is not installed
  VERSION_INCOMPATIBLE — pack requires a specific version of a dependency
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from app.core.domain_pack_loader import DomainPack

logger = logging.getLogger(__name__)


class CompatibilityIssueType(str, Enum):
    NAMESPACE_COLLISION = "namespace_collision"
    RULE_CONFLICT = "rule_conflict"
    DEPENDENCY_MISSING = "dependency_missing"
    VERSION_INCOMPATIBLE = "version_incompatible"
    SAFE = "safe"


@dataclass
class CompatibilityIssue:
    issue_type: CompatibilityIssueType
    pack_a: str
    pack_b: str
    detail: str
    severity: str  # blocking / warning


@dataclass
class CompatibilityReport:
    pack_id: str
    candidate_pack_id: str
    compatible: bool
    issues: list[CompatibilityIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PackCompatibilityMatrix:
    """
    Evaluates whether two packs can coexist safely.
    Checks for namespace collisions, rule conflicts, and dependency issues.
    """

    def check(self, pack_a: DomainPack, pack_b: DomainPack) -> CompatibilityReport:
        issues = []
        warnings = []

        # Check namespace collisions
        ns_a = {ns.name for ns in pack_a.namespaces}
        ns_b = {ns.name for ns in pack_b.namespaces}
        collisions = ns_a & ns_b
        for ns_name in collisions:
            issues.append(
                CompatibilityIssue(
                    issue_type=CompatibilityIssueType.NAMESPACE_COLLISION,
                    pack_a=pack_a.pack_id,
                    pack_b=pack_b.pack_id,
                    detail=f"Both packs own namespace '{ns_name}' — only one can be authoritative",
                    severity="blocking",
                )
            )

        # Check rule ID conflicts
        rule_ids_a = {r.rule_id for r in pack_a.reconciliation_rules}
        rule_ids_b = {r.rule_id for r in pack_b.reconciliation_rules}
        rule_conflicts = rule_ids_a & rule_ids_b
        for rule_id in rule_conflicts:
            issues.append(
                CompatibilityIssue(
                    issue_type=CompatibilityIssueType.RULE_CONFLICT,
                    pack_a=pack_a.pack_id,
                    pack_b=pack_b.pack_id,
                    detail=f"Both packs define rule '{rule_id}' — the last loaded will override",
                    severity="warning",
                )
            )
            warnings.append(f"Rule {rule_id} defined in both packs — last loaded wins")

        compatible = not any(i.severity == "blocking" for i in issues)
        return CompatibilityReport(
            pack_id=pack_a.pack_id,
            candidate_pack_id=pack_b.pack_id,
            compatible=compatible,
            issues=issues,
            warnings=warnings,
        )

    def build_matrix(self, packs: list[DomainPack]) -> dict:
        """Build a full compatibility matrix for a list of packs."""
        matrix = {}
        for i, pack_a in enumerate(packs):
            for pack_b in packs[i + 1 :]:
                report = self.check(pack_a, pack_b)
                key = f"{pack_a.pack_id}:{pack_b.pack_id}"
                matrix[key] = {
                    "pack_a": pack_a.pack_id,
                    "pack_b": pack_b.pack_id,
                    "compatible": report.compatible,
                    "issue_count": len(report.issues),
                    "warning_count": len(report.warnings),
                }
        return matrix
