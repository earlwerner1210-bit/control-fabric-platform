"""
Pack Authoring SDK

Simple Python API for defining custom domain packs.
Designed for enterprise customers who want to codify
their own governance rules without touching platform internals.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone


@dataclass
class PackRule:
    rule_id: str
    description: str
    source_plane: str
    target_plane: str
    severity: str = "high"  # low / medium / high / critical
    evidence_required: list[str] = field(default_factory=list)
    remediation: str = ""
    enabled: bool = True
    tags: list[str] = field(default_factory=list)


@dataclass
class PackDefinition:
    """
    Complete definition of a custom domain pack.
    Serialisable to JSON for version control and distribution.
    """

    pack_id: str
    name: str
    description: str
    version: str
    domain: str
    author: str
    rules: list[PackRule] = field(default_factory=list)
    blocked_action_types: list[str] = field(default_factory=list)
    required_evidence_types: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict:
        return {
            "pack_id": self.pack_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "domain": self.domain,
            "author": self.author,
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "description": r.description,
                    "source_plane": r.source_plane,
                    "target_plane": r.target_plane,
                    "severity": r.severity,
                    "evidence_required": r.evidence_required,
                    "remediation": r.remediation,
                    "enabled": r.enabled,
                }
                for r in self.rules
            ],
            "blocked_action_types": self.blocked_action_types,
            "required_evidence_types": self.required_evidence_types,
            "created_at": self.created_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_domain_pack(self):
        """Convert to a platform DomainPack object for direct loading."""
        try:
            from app.core.domain_pack_loader import DomainPack
            from app.core.reconciliation.cross_plane_engine import ReconciliationRule

            rules = []
            for r in self.rules:
                if r.enabled:
                    rule = ReconciliationRule(
                        rule_id=r.rule_id,
                        description=r.description,
                        source_plane=r.source_plane,
                        target_plane=r.target_plane,
                        severity=r.severity,
                        remediation_suggestions=([r.remediation] if r.remediation else []),
                    )
                    rules.append(rule)
            return DomainPack(
                pack_id=self.pack_id,
                name=self.name,
                description=self.description,
                version=self.version,
                namespaces=[],
                reconciliation_rules=rules,
            )
        except Exception as e:
            raise RuntimeError(f"Could not convert pack definition to DomainPack: {e}")


class PackBuilder:
    """
    Fluent builder for creating custom domain pack definitions.
    Designed to be readable and hard to misuse.
    """

    def __init__(self, pack_id: str) -> None:
        self._pack_id = pack_id
        self._name = pack_id
        self._description = ""
        self._version = "1.0.0"
        self._domain = "general"
        self._author = "platform"
        self._rules: list[PackRule] = []
        self._blocked_actions: list[str] = []
        self._required_evidence: list[str] = []

    def name(self, name: str) -> PackBuilder:
        self._name = name
        return self

    def description(self, description: str) -> PackBuilder:
        self._description = description
        return self

    def version(self, version: str) -> PackBuilder:
        self._version = version
        return self

    def domain(self, domain: str) -> PackBuilder:
        self._domain = domain
        return self

    def author(self, author: str) -> PackBuilder:
        self._author = author
        return self

    def add_rule(
        self,
        rule_id: str,
        description: str,
        source_plane: str,
        target_plane: str,
        severity: str = "high",
        evidence_required: list[str] | None = None,
        remediation: str = "",
        tags: list[str] | None = None,
    ) -> PackBuilder:
        self._rules.append(
            PackRule(
                rule_id=rule_id,
                description=description,
                source_plane=source_plane,
                target_plane=target_plane,
                severity=severity,
                evidence_required=evidence_required or [],
                remediation=remediation,
                tags=tags or [],
            )
        )
        return self

    def block_action(self, action_type: str) -> PackBuilder:
        """Add an action type that this pack blocks unconditionally."""
        self._blocked_actions.append(action_type)
        return self

    def require_evidence(self, evidence_type: str) -> PackBuilder:
        """Add a required evidence type for all actions under this pack."""
        self._required_evidence.append(evidence_type)
        return self

    def build(self) -> PackDefinition:
        if not self._description:
            raise ValueError(
                f"Pack {self._pack_id} must have a description. "
                "Call .description('...') before .build()"
            )
        if not self._rules:
            raise ValueError(
                f"Pack {self._pack_id} has no rules. "
                "Add at least one rule with .add_rule(...) before .build()"
            )
        return PackDefinition(
            pack_id=self._pack_id,
            name=self._name,
            description=self._description,
            version=self._version,
            domain=self._domain,
            author=self._author,
            rules=self._rules,
            blocked_action_types=self._blocked_actions,
            required_evidence_types=self._required_evidence,
        )

    @classmethod
    def from_json(cls, json_str: str) -> PackDefinition:
        """Load a pack definition from a JSON string."""
        data = json.loads(json_str)
        rules = [
            PackRule(
                rule_id=r["rule_id"],
                description=r["description"],
                source_plane=r["source_plane"],
                target_plane=r["target_plane"],
                severity=r.get("severity", "high"),
                evidence_required=r.get("evidence_required", []),
                remediation=r.get("remediation", ""),
            )
            for r in data.get("rules", [])
        ]
        return PackDefinition(
            pack_id=data["pack_id"],
            name=data["name"],
            description=data["description"],
            version=data["version"],
            domain=data.get("domain", "general"),
            author=data.get("author", "unknown"),
            rules=rules,
            blocked_action_types=data.get("blocked_action_types", []),
            required_evidence_types=data.get("required_evidence_types", []),
        )


def build_example_telecom_pack() -> PackDefinition:
    """
    Example: Vodafone-style network operations governance pack.
    Use this as a template for customer-specific packs.
    """
    return (
        PackBuilder("vodafone-network-ops-v1")
        .name("Network Operations Governance")
        .description(
            "Internal network change governance rules. "
            "Enforces NOA approval, SNOW change requests, and security review "
            "for all production network changes."
        )
        .version("1.0.0")
        .domain("telecom")
        .author("network-governance-team")
        .add_rule(
            rule_id="VF-NW-001",
            description="All network changes require an approved ServiceNow change request",
            source_plane="operations",
            target_plane="compliance",
            severity="critical",
            evidence_required=["servicenow_change_request"],
            remediation="Raise and approve a ServiceNow CR before deploying network changes",
        )
        .add_rule(
            rule_id="VF-NW-002",
            description="Production network deployments require Network Operations Authority sign-off",
            source_plane="operations",
            target_plane="risk",
            severity="critical",
            evidence_required=["approver_sign_off"],
            remediation="Obtain NOA approval via the governance console before production deployment",
        )
        .add_rule(
            rule_id="VF-NW-003",
            description="Security-classified network changes require security impact assessment",
            source_plane="security",
            target_plane="operations",
            severity="high",
            evidence_required=["security_assessment"],
            remediation="Complete a security impact assessment for changes affecting NIS2-classified systems",
        )
        .add_rule(
            rule_id="VF-NW-004",
            description="All changes must have a documented rollback plan before production deployment",
            source_plane="operations",
            target_plane="risk",
            severity="high",
            evidence_required=["rollback_plan"],
            remediation="Document the rollback procedure in the change request before submitting",
        )
        .block_action("force_deploy")
        .block_action("unreviewed_network_change")
        .build()
    )
