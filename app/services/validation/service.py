"""Validation service – schema, evidence, rule, and confidence validation."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import ValidationResult, ValidationStatus
from app.schemas.validation import RuleResult

logger = get_logger("validation")


class ValidationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def validate_output(
        self,
        tenant_id: uuid.UUID,
        workflow_case_id: uuid.UUID,
        domain: str,
        output_payload: dict[str, Any],
        control_objects: list[dict] | None = None,
        confidence_threshold: float = 0.7,
    ) -> ValidationResult:
        """Run full validation pipeline: schema → evidence → rules → confidence."""
        all_results: list[RuleResult] = []

        # 1. Schema validation
        schema_results = self._validate_schema(output_payload, domain)
        all_results.extend(schema_results)

        # 2. Evidence presence validation
        evidence_results = self._validate_evidence(output_payload)
        all_results.extend(evidence_results)

        # 3. Domain-rule validation
        domain_results = self._validate_domain_rules(domain, output_payload, control_objects or [])
        all_results.extend(domain_results)

        # 4. Confidence gating
        confidence_results = self._validate_confidence(output_payload, confidence_threshold)
        all_results.extend(confidence_results)

        # Determine overall status
        status = self._determine_status(all_results)

        # Persist
        vr = ValidationResult(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_case_id=workflow_case_id,
            validator_name=f"{domain}_validator",
            status=status,
            domain=domain,
            rule_results={"rules": [r.model_dump() for r in all_results]},
            summary=self._build_summary(all_results, status),
        )
        self.db.add(vr)
        await self.db.flush()

        logger.info(
            "validation_complete",
            case_id=str(workflow_case_id),
            status=status.value,
            rules_checked=len(all_results),
        )
        return vr

    def _validate_schema(self, output: dict, domain: str) -> list[RuleResult]:
        results: list[RuleResult] = []
        required_fields: dict[str, list[str]] = {
            "contract_margin": ["verdict", "evidence_object_ids"],
            "utilities_field": ["verdict", "reasons"],
            "telco_ops": ["next_action"],
        }
        for field in required_fields.get(domain, []):
            results.append(
                RuleResult(
                    rule_name=f"schema_{field}_present",
                    passed=field in output and output[field] is not None,
                    message=f"Field '{field}' is present" if field in output else f"Required field '{field}' is missing",
                    severity="error" if field not in output else "info",
                )
            )
        return results

    def _validate_evidence(self, output: dict) -> list[RuleResult]:
        results: list[RuleResult] = []
        evidence_ids = output.get("evidence_object_ids") or output.get("evidence_ids") or []
        results.append(
            RuleResult(
                rule_name="evidence_present",
                passed=len(evidence_ids) > 0,
                message=f"{len(evidence_ids)} evidence references found" if evidence_ids else "No evidence references provided",
                severity="warning" if not evidence_ids else "info",
            )
        )
        return results

    def _validate_domain_rules(
        self, domain: str, output: dict, control_objects: list[dict]
    ) -> list[RuleResult]:
        if domain == "contract_margin":
            return self._validate_contract_rules(output, control_objects)
        elif domain == "utilities_field":
            return self._validate_field_rules(output, control_objects)
        elif domain == "telco_ops":
            return self._validate_telco_rules(output, control_objects)
        return []

    def _validate_contract_rules(self, output: dict, objects: list[dict]) -> list[RuleResult]:
        results: list[RuleResult] = []
        verdict = output.get("verdict", "")
        valid_verdicts = {"billable", "non_billable", "under_recovery", "penalty_risk", "unknown"}

        results.append(
            RuleResult(
                rule_name="valid_margin_verdict",
                passed=verdict in valid_verdicts,
                message=f"Verdict '{verdict}' is valid" if verdict in valid_verdicts else f"Unsupported verdict: '{verdict}'",
                severity="error" if verdict not in valid_verdicts else "info",
            )
        )

        if verdict == "billable" and not output.get("evidence_object_ids"):
            results.append(
                RuleResult(
                    rule_name="billable_requires_evidence",
                    passed=False,
                    message="Billable verdict requires supporting evidence",
                    severity="error",
                )
            )

        return results

    def _validate_field_rules(self, output: dict, objects: list[dict]) -> list[RuleResult]:
        results: list[RuleResult] = []
        verdict = output.get("verdict", "")
        valid_verdicts = {"ready", "blocked", "warn", "escalate"}

        results.append(
            RuleResult(
                rule_name="valid_readiness_verdict",
                passed=verdict in valid_verdicts,
                message=f"Readiness verdict '{verdict}' is valid" if verdict in valid_verdicts else f"Unsupported: '{verdict}'",
                severity="error" if verdict not in valid_verdicts else "info",
            )
        )

        if verdict == "ready":
            missing = output.get("missing_prerequisites", [])
            results.append(
                RuleResult(
                    rule_name="ready_no_missing_prereqs",
                    passed=len(missing) == 0,
                    message="No missing prerequisites for ready verdict" if not missing else f"Ready verdict contradicts {len(missing)} missing prerequisites",
                    severity="error" if missing else "info",
                )
            )

        return results

    def _validate_telco_rules(self, output: dict, objects: list[dict]) -> list[RuleResult]:
        results: list[RuleResult] = []
        next_action = output.get("next_action", "")
        valid_actions = {
            "investigate", "escalate", "dispatch", "resolve", "monitor",
            "contact_customer", "assign_engineer", "close", "reopen",
        }

        results.append(
            RuleResult(
                rule_name="valid_next_action",
                passed=next_action in valid_actions,
                message=f"Action '{next_action}' is valid" if next_action in valid_actions else f"Invalid action: '{next_action}'",
                severity="error" if next_action not in valid_actions else "info",
            )
        )

        if output.get("escalation_level"):
            valid_levels = {"l1", "l2", "l3", "management"}
            level = output["escalation_level"]
            results.append(
                RuleResult(
                    rule_name="valid_escalation_level",
                    passed=level in valid_levels,
                    message=f"Escalation level '{level}' is valid" if level in valid_levels else f"Unsupported: '{level}'",
                    severity="error" if level not in valid_levels else "info",
                )
            )

        return results

    def _validate_confidence(self, output: dict, threshold: float) -> list[RuleResult]:
        confidence = output.get("confidence", 1.0)
        return [
            RuleResult(
                rule_name="confidence_threshold",
                passed=confidence >= threshold,
                message=f"Confidence {confidence:.2f} meets threshold {threshold}" if confidence >= threshold else f"Confidence {confidence:.2f} below threshold {threshold}",
                severity="warning" if confidence < threshold else "info",
            )
        ]

    def _determine_status(self, results: list[RuleResult]) -> ValidationStatus:
        has_errors = any(not r.passed and r.severity == "error" for r in results)
        has_critical = any(not r.passed and r.severity == "critical" for r in results)
        has_warnings = any(not r.passed and r.severity == "warning" for r in results)

        if has_critical:
            return ValidationStatus.escalated
        if has_errors:
            return ValidationStatus.blocked
        if has_warnings:
            return ValidationStatus.warned
        return ValidationStatus.passed

    def _build_summary(self, results: list[RuleResult], status: ValidationStatus) -> str:
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        failed_rules = [r.rule_name for r in results if not r.passed]
        summary = f"{passed}/{total} rules passed. Status: {status.value}."
        if failed_rules:
            summary += f" Failed: {', '.join(failed_rules)}"
        return summary
