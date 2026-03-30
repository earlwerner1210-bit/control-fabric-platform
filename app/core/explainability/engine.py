"""
Policy Explainability Engine

Answers the questions operators actually ask:
  - "Why was this action blocked?"
  - "Why was this action released?"
  - "Which gate failed?"
  - "Which evidence was missing?"
  - "Which policy version applied?"
  - "What changed from the previous version?"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GateExplanation:
    gate_name: str
    outcome: str  # passed / failed / skipped
    detail: str
    is_blocking: bool


@dataclass
class BlockExplanation:
    """Complete explanation of why an action was blocked."""

    request_id: str
    action_type: str
    origin: str
    requested_by: str
    requested_at: str
    overall_outcome: str  # blocked / released
    blocking_gate: str | None
    blocking_reason: str | None
    gates: list[GateExplanation] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    violated_policies: list[str] = field(default_factory=list)
    applicable_policy_versions: list[str] = field(default_factory=list)
    remediation_steps: list[str] = field(default_factory=list)
    evidence_provided: list[str] = field(default_factory=list)
    human_summary: str = ""


@dataclass
class ReleaseExplanation:
    """Complete explanation of why an action was released."""

    package_id: str
    action_type: str
    origin: str
    requested_by: str
    overall_outcome: str = "released"
    gates_passed: list[str] = field(default_factory=list)
    evidence_used: list[str] = field(default_factory=list)
    policies_satisfied: list[str] = field(default_factory=list)
    package_hash: str = ""
    compiled_at: str = ""
    human_summary: str = ""


class ExplainabilityEngine:
    """Generates human-readable explanations for all platform decisions."""

    def explain_block(self, audit_result: dict) -> BlockExplanation:
        """Generate a complete explanation of a blocked action."""
        failure_reason = audit_result.get("failure_reason", "")
        gate_name = self._extract_gate_name(failure_reason)

        gates = self._build_gate_timeline(failure_reason)
        missing_evidence = self._extract_missing_evidence(failure_reason)
        remediation = self._build_remediation_steps(gate_name, failure_reason, missing_evidence)

        explanation = BlockExplanation(
            request_id=audit_result.get("dispatch_id", ""),
            action_type=audit_result.get("action_type", ""),
            origin=audit_result.get("origin", ""),
            requested_by=audit_result.get("requested_by", ""),
            requested_at=audit_result.get("dispatched_at", ""),
            overall_outcome="blocked",
            blocking_gate=gate_name,
            blocking_reason=failure_reason,
            gates=gates,
            missing_evidence=missing_evidence,
            remediation_steps=remediation,
        )
        explanation.human_summary = self._generate_human_summary_block(explanation)
        return explanation

    def explain_release(self, package: dict) -> ReleaseExplanation:
        """Generate a complete explanation of a released action."""
        explanation = ReleaseExplanation(
            package_id=package.get("package_id", ""),
            action_type=package.get("action_type", ""),
            origin=package.get("origin", ""),
            requested_by=package.get("requested_by", ""),
            gates_passed=[
                "completeness",
                "evidence_sufficiency",
                "policy_compliance",
                "provenance_integrity",
                "schema_conformance",
            ],
            evidence_used=package.get("evidence_chain", []),
            package_hash=package.get("package_hash", ""),
            compiled_at=package.get("compiled_at", ""),
        )
        explanation.human_summary = self._generate_human_summary_release(explanation)
        return explanation

    def explain_case(self, case: dict) -> dict:
        """Generate a complete explanation of a reconciliation case."""
        case_type = case.get("case_type", "gap")
        severity = case.get("severity", "medium")
        rule_id = case.get("violated_rule_id", "")
        planes = case.get("affected_planes", [])

        explanations = {
            "gap": (
                f"A required governance relationship is missing between objects in "
                f"the {' and '.join(planes)} plane(s). The platform detected that "
                f"the rule '{rule_id}' requires a typed relationship that does not "
                f"exist in the control graph."
            ),
            "conflict": (
                f"Two or more active control objects in the {' and '.join(planes)} "
                f"plane(s) have a VIOLATES relationship, meaning they are in direct "
                f"governance conflict."
            ),
            "orphan": (
                f"One or more control objects in the {' and '.join(planes)} plane(s) "
                f"have no governance relationships. They exist in the registry but "
                f"are not connected to any policy or compliance requirement."
            ),
        }

        return {
            "case_id": case.get("case_id", ""),
            "case_type": case_type,
            "severity": severity,
            "explanation": explanations.get(case_type, "Governance anomaly detected."),
            "affected_planes": planes,
            "violated_rule": rule_id,
            "remediation": case.get("remediation_suggestions", []),
            "what_this_means": self._what_this_means(case_type, severity),
            "what_to_do_next": self._what_to_do_next(
                case_type, case.get("remediation_suggestions", [])
            ),
        }

    def diff_policy_versions(self, from_policy: dict, to_policy: dict) -> dict:
        """Explain what changed between two policy versions."""
        from_blocks = set(from_policy.get("blocked_action_types", []))
        to_blocks = set(to_policy.get("blocked_action_types", []))

        newly_blocked = sorted(to_blocks - from_blocks)
        newly_unblocked = sorted(from_blocks - to_blocks)
        is_breaking = bool(newly_blocked)

        changes = []
        if newly_blocked:
            changes.append(f"Now blocks: {', '.join(newly_blocked)}")
        if newly_unblocked:
            changes.append(f"No longer blocks: {', '.join(newly_unblocked)}")

        return {
            "from_version": from_policy.get("version", 1),
            "to_version": to_policy.get("version", 2),
            "is_breaking_change": is_breaking,
            "newly_blocked_actions": newly_blocked,
            "newly_unblocked_actions": newly_unblocked,
            "change_summary": (" | ".join(changes) if changes else "No effective changes"),
            "impact": (
                f"This change will affect {len(newly_blocked)} action type(s) "
                f"that were previously permitted."
                if newly_blocked
                else "No actions that were previously permitted will be blocked."
            ),
            "recommendation": (
                "Test in staging before publishing to production."
                if is_breaking
                else "Change is backward-compatible."
            ),
        }

    def _extract_gate_name(self, failure_reason: str) -> str:
        gate_map = {
            "completeness": "completeness",
            "evidence_sufficiency": "evidence_sufficiency",
            "policy_compliance": "policy_compliance",
            "provenance_integrity": "provenance_integrity",
            "schema_conformance": "schema_conformance",
        }
        for key, name in gate_map.items():
            if key in failure_reason.lower():
                return name
        return "unknown"

    def _build_gate_timeline(self, failure_reason: str) -> list[GateExplanation]:
        gates = []
        gate_names = [
            "completeness",
            "evidence_sufficiency",
            "policy_compliance",
            "provenance_integrity",
            "schema_conformance",
        ]
        failed_gate = self._extract_gate_name(failure_reason)
        for gate in gate_names:
            if gate == failed_gate:
                gates.append(
                    GateExplanation(
                        gate_name=gate,
                        outcome="failed",
                        detail=failure_reason,
                        is_blocking=True,
                    )
                )
                break
            gates.append(
                GateExplanation(
                    gate_name=gate,
                    outcome="passed",
                    detail="Check passed",
                    is_blocking=False,
                )
            )
        return gates

    def _extract_missing_evidence(self, failure_reason: str) -> list[str]:
        if "evidence" in failure_reason.lower():
            return ["At least one evidence reference is required for this action type and origin."]
        return []

    def _build_remediation_steps(
        self, gate: str, reason: str, missing_evidence: list[str]
    ) -> list[str]:
        remediation_map = {
            "completeness": [
                "Ensure all required fields are present: action_type, requested_by, proposed_payload.",
                "Check that proposed_payload is not empty.",
            ],
            "evidence_sufficiency": [
                "Provide at least one evidence reference (e.g. CI run ID, scan result ID).",
                "Evidence references must be non-empty strings.",
                "AI-originated actions always require evidence.",
            ],
            "policy_compliance": [
                "Check the active policies for blocked action types.",
                "Review which policy version is currently active.",
                "If this action is legitimately required, submit an exception request.",
            ],
            "provenance_integrity": [
                "The request hash does not match — the request may have been modified.",
                "Resubmit the request without modification.",
            ],
            "schema_conformance": [
                "Ensure proposed_payload is a valid dict.",
                "Check for required schema fields for this action type.",
            ],
        }
        return remediation_map.get(
            gate,
            [
                "Review the validation chain configuration.",
                "Contact your platform administrator.",
            ],
        )

    def _generate_human_summary_block(self, e: BlockExplanation) -> str:
        return (
            f"Action '{e.action_type}' was blocked at the {e.blocking_gate} gate. "
            f"{e.blocking_reason}. "
            f"To release this action: "
            f"{e.remediation_steps[0] if e.remediation_steps else 'review the validation chain configuration.'}"
        )

    def _generate_human_summary_release(self, e: ReleaseExplanation) -> str:
        return (
            f"Action '{e.action_type}' was released by {e.requested_by}. "
            f"All 5 validation gates passed. "
            f"{len(e.evidence_used)} evidence reference(s) bound to the release package. "
            f"Package hash: {e.package_hash[:16]}..."
        )

    def _what_this_means(self, case_type: str, severity: str) -> str:
        meanings = {
            ("gap", "critical"): (
                "A critical control is unprotected. A production action in this "
                "area has no governance coverage."
            ),
            ("gap", "high"): (
                "A high-risk control gap exists. Actions in this area may proceed "
                "without sufficient oversight."
            ),
            ("conflict", "critical"): (
                "Two controls are in direct conflict. One may be rendering the other ineffective."
            ),
            ("orphan", "high"): (
                "A governance object exists but is not connected to any compliance "
                "requirement or policy."
            ),
        }
        return meanings.get(
            (case_type, severity),
            f"A {severity}-severity {case_type} was detected.",
        )

    def _what_to_do_next(self, case_type: str, suggestions: list[str]) -> str:
        if suggestions:
            return suggestions[0]
        defaults = {
            "gap": "Link the affected object to an appropriate policy or compliance requirement.",
            "conflict": "Review the two conflicting objects and determine which should take precedence.",
            "orphan": "Connect the orphaned object to an appropriate governance relationship.",
        }
        return defaults.get(case_type, "Review the affected objects in the operator console.")


explainability_engine = ExplainabilityEngine()
