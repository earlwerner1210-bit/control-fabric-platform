"""Policy Manager — draft, simulate, publish, rollback, archive."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from .domain_types import (
    PolicyConflict,
    PolicyDefinition,
    PolicySimulationResult,
    PolicyStatus,
)

logger = logging.getLogger(__name__)


class PolicyManager:
    """Manages the full policy lifecycle."""

    def __init__(self) -> None:
        self._policies: dict[str, PolicyDefinition] = {}
        self._simulations: dict[str, PolicySimulationResult] = {}
        self._history: list[dict[str, str]] = []

    # ── lifecycle ───────────────────────────────────────────

    def create_draft(
        self,
        policy_name: str,
        description: str = "",
        rules: list[str] | None = None,
        target_packs: list[str] | None = None,
        created_by: str = "system",
    ) -> PolicyDefinition:
        policy = PolicyDefinition(
            policy_name=policy_name,
            description=description,
            rules=rules or [],
            target_packs=target_packs or [],
            created_by=created_by,
        )
        self._policies[policy.policy_id] = policy
        self._record("create_draft", policy.policy_id, created_by)
        return policy

    def simulate(self, policy_id: str, sample_size: int = 100) -> PolicySimulationResult:
        policy = self._get(policy_id)
        if policy.status not in (PolicyStatus.DRAFT, PolicyStatus.PUBLISHED):
            raise ValueError(f"Cannot simulate policy in state: {policy.status.value}")

        policy.status = PolicyStatus.SIMULATING
        affected = min(len(policy.rules) * 3, sample_size)
        result = PolicySimulationResult(
            policy_id=policy_id,
            cases_evaluated=sample_size,
            cases_affected=affected,
            false_positives=max(0, affected // 10),
            impact_summary=f"{affected}/{sample_size} cases affected by {len(policy.rules)} rules",
            safe_to_publish=affected < sample_size * 0.5,
        )
        self._simulations[policy_id] = result
        policy.status = PolicyStatus.DRAFT
        self._record("simulate", policy_id, "system")
        return result

    def publish(self, policy_id: str, published_by: str = "system") -> PolicyDefinition:
        policy = self._get(policy_id)
        if policy.status != PolicyStatus.DRAFT:
            raise ValueError(f"Can only publish from draft state, current: {policy.status.value}")

        conflicts = self.detect_conflicts(policy_id)
        if conflicts:
            raise ValueError(
                f"Cannot publish: {len(conflicts)} conflict(s) detected with existing policies"
            )

        policy.status = PolicyStatus.PUBLISHED
        policy.published_at = datetime.now(UTC)
        self._record("publish", policy_id, published_by)
        logger.info("Published policy %s", policy_id)
        return policy

    def rollback(self, policy_id: str, rolled_back_by: str = "system") -> PolicyDefinition:
        policy = self._get(policy_id)
        if policy.status != PolicyStatus.PUBLISHED:
            raise ValueError("Can only roll back published policies")
        policy.status = PolicyStatus.ROLLED_BACK
        self._record("rollback", policy_id, rolled_back_by)
        logger.info("Rolled back policy %s", policy_id)
        return policy

    def archive(self, policy_id: str) -> PolicyDefinition:
        policy = self._get(policy_id)
        if policy.status == PolicyStatus.PUBLISHED:
            raise ValueError("Cannot archive a published policy — rollback first")
        policy.status = PolicyStatus.ARCHIVED
        self._record("archive", policy_id, "system")
        return policy

    # ── queries ─────────────────────────────────────────────

    def get_policy(self, policy_id: str) -> PolicyDefinition | None:
        return self._policies.get(policy_id)

    def list_policies(self, status: PolicyStatus | None = None) -> list[PolicyDefinition]:
        policies = list(self._policies.values())
        if status:
            return [p for p in policies if p.status == status]
        return policies

    def detect_conflicts(self, policy_id: str) -> list[PolicyConflict]:
        policy = self._get(policy_id)
        conflicts: list[PolicyConflict] = []
        for other in self._policies.values():
            if other.policy_id == policy_id:
                continue
            if other.status != PolicyStatus.PUBLISHED:
                continue
            overlap = set(policy.target_packs) & set(other.target_packs)
            if overlap:
                rule_overlap = set(policy.rules) & set(other.rules)
                if rule_overlap:
                    conflicts.append(
                        PolicyConflict(
                            policy_a=policy_id,
                            policy_b=other.policy_id,
                            conflict_type="rule_overlap",
                            description=f"Overlapping rules on packs {overlap}: {rule_overlap}",
                        )
                    )
        return conflicts

    def get_simulation(self, policy_id: str) -> PolicySimulationResult | None:
        return self._simulations.get(policy_id)

    def get_history(self) -> list[dict[str, str]]:
        return list(self._history)

    # ── private ─────────────────────────────────────────────

    def _get(self, policy_id: str) -> PolicyDefinition:
        policy = self._policies.get(policy_id)
        if not policy:
            raise ValueError(f"Policy not found: {policy_id}")
        return policy

    def _record(self, action: str, policy_id: str, actor: str) -> None:
        self._history.append(
            {
                "action": action,
                "policy_id": policy_id,
                "actor": actor,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
