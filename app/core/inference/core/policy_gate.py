"""
Control Fabric Platform — Bounded Inference Engine
Policy Gate: Deterministic Pre-Inference Enforcement

Patent Claim (Theme 3): Gate runs BEFORE any model invocation.
DETERMINISTIC — same inputs always produce same output.

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.inference.models.domain_types import PolicyDecision, PolicyGateResult, ScopeParameters

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    policy_id: str
    policy_version: str
    allowed_planes: frozenset[str]
    allowed_requesting_entities: frozenset[str] | None
    denied_requesting_entities: frozenset[str]
    allowed_hypothesis_types: frozenset[str]
    max_control_objects_per_request: int
    max_graph_depth: int
    allowed_data_classification: str
    allowed_relationship_types: frozenset[str]
    description: str


@dataclass
class PolicyStore:
    _rules: dict[str, PolicyRule] = field(default_factory=dict)

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules[rule.rule_id] = rule

    def get_rules_for_plane(self, plane: str) -> list[PolicyRule]:
        return [r for r in self._rules.values() if plane in r.allowed_planes]


def build_default_policy_store() -> PolicyStore:
    store = PolicyStore()
    store.add_rule(
        PolicyRule(
            rule_id="POL-001",
            policy_id="governance-standard",
            policy_version="1.0.0",
            allowed_planes=frozenset(["risk", "compliance", "security", "operations", "audit"]),
            allowed_requesting_entities=None,
            denied_requesting_entities=frozenset(),
            allowed_hypothesis_types=frozenset(
                [
                    "remediation_suggestion",
                    "gap_analysis",
                    "conflict_resolution",
                    "risk_assessment",
                    "compliance_mapping",
                    "pattern_detection",
                ]
            ),
            max_control_objects_per_request=50,
            max_graph_depth=3,
            allowed_data_classification="internal",
            allowed_relationship_types=frozenset(
                [
                    "mitigates",
                    "satisfies",
                    "implements",
                    "violates",
                    "requires",
                    "depends_on",
                ]
            ),
            description="Standard governance inference policy",
        )
    )
    store.add_rule(
        PolicyRule(
            rule_id="POL-002",
            policy_id="governance-restricted",
            policy_version="1.0.0",
            allowed_planes=frozenset(["financial", "legal", "executive"]),
            allowed_requesting_entities=frozenset(["senior-analyst", "compliance-officer"]),
            denied_requesting_entities=frozenset(),
            allowed_hypothesis_types=frozenset(["risk_assessment", "compliance_mapping"]),
            max_control_objects_per_request=10,
            max_graph_depth=2,
            allowed_data_classification="confidential",
            allowed_relationship_types=frozenset(["mitigates", "satisfies", "requires"]),
            description="Restricted policy for sensitive operational planes",
        )
    )
    return store


class PolicyGate:
    """
    Pre-inference policy enforcement gate.
    No inference occurs unless this gate returns PolicyDecision.ALLOW.
    """

    def __init__(self, policy_store: PolicyStore | None = None) -> None:
        self._store = policy_store or build_default_policy_store()

    def evaluate(
        self,
        requesting_entity_id: str,
        target_operational_plane: str,
        hypothesis_type_requested: str,
        target_control_object_ids: list[str],
    ) -> PolicyGateResult:
        applicable_rules = self._store.get_rules_for_plane(target_operational_plane)
        if not applicable_rules:
            return self._deny(
                "no-applicable-policy", "0.0.0", f"No policy for plane: {target_operational_plane}"
            )
        for rule in applicable_rules:
            result = self._evaluate_rule(
                rule,
                requesting_entity_id,
                target_operational_plane,
                hypothesis_type_requested,
                target_control_object_ids,
            )
            if result is not None:
                return result
        return self._deny(
            "default-deny", "1.0.0", "Request did not satisfy any applicable policy rule"
        )

    def _evaluate_rule(
        self,
        rule: PolicyRule,
        requesting_entity_id: str,
        target_operational_plane: str,
        hypothesis_type_requested: str,
        target_control_object_ids: list[str],
    ) -> PolicyGateResult | None:
        if requesting_entity_id in rule.denied_requesting_entities:
            return self._deny(
                rule.policy_id,
                rule.policy_version,
                f"Entity {requesting_entity_id} explicitly denied",
            )
        if (
            rule.allowed_requesting_entities is not None
            and requesting_entity_id not in rule.allowed_requesting_entities
        ):
            return None
        if hypothesis_type_requested not in rule.allowed_hypothesis_types:
            return self._deny(
                rule.policy_id,
                rule.policy_version,
                f"Hypothesis type '{hypothesis_type_requested}' not permitted",
            )
        if len(target_control_object_ids) > rule.max_control_objects_per_request:
            return self._deny(
                rule.policy_id,
                rule.policy_version,
                f"Too many objects: {len(target_control_object_ids)} > {rule.max_control_objects_per_request}",
            )
        scope = ScopeParameters(
            allowed_control_object_ids=target_control_object_ids,
            allowed_operational_planes=[target_operational_plane],
            max_graph_depth=rule.max_graph_depth,
            allowed_relationship_types=list(rule.allowed_relationship_types),
            data_classification_ceiling=rule.allowed_data_classification,
        )
        return PolicyGateResult(
            decision=PolicyDecision.ALLOW,
            policy_id=rule.policy_id,
            policy_version=rule.policy_version,
            scope_parameters=scope,
        )

    @staticmethod
    def _deny(policy_id: str, policy_version: str, reason: str) -> PolicyGateResult:
        return PolicyGateResult(
            decision=PolicyDecision.DENY,
            policy_id=policy_id,
            policy_version=policy_version,
            denial_reason=reason,
        )
