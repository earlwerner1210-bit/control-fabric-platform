"""Validator service business logic."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import ControlObject, ValidationResult, ValidationStatus
from shared.telemetry.logging import get_logger

logger = get_logger("validator_service")


class ValidatorService:
    """Validates control objects against domain rules."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def validate_output(
        self,
        control_object_ids: list[uuid.UUID],
        domain: str,
        rules: list[str],
        tenant_id: uuid.UUID,
        case_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Run schema, evidence, rules, and confidence validation."""
        case_id = case_id or uuid.uuid4()

        result = await self.db.execute(
            select(ControlObject).where(
                ControlObject.id.in_(control_object_ids),
                ControlObject.tenant_id == tenant_id,
            )
        )
        objects = list(result.scalars().all())
        if not objects:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No control objects found")

        validation_results: list[ValidationResult] = []
        for obj in objects:
            rule_results = self.run_domain_rules(obj, domain, rules)
            vr_status = self.gate_confidence(rule_results, obj.confidence)

            vr = ValidationResult(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                target_type="control_object",
                target_id=obj.id,
                status=vr_status,
                rules_passed=sum(1 for r in rule_results if r["passed"]),
                rules_warned=sum(1 for r in rule_results if not r["passed"] and r["severity"] == "warning"),
                rules_blocked=sum(1 for r in rule_results if not r["passed"] and r["severity"] in ("error", "critical")),
                rule_results=rule_results,
                metadata_={"case_id": str(case_id), "domain": domain},
            )
            self.db.add(vr)
            validation_results.append(vr)

        await self.db.flush()
        overall = self._compute_overall_status(validation_results)
        logger.info(
            "Validated %d objects for case %s: %s",
            len(objects), case_id, overall,
        )
        return {
            "case_id": case_id,
            "results": validation_results,
            "overall_status": overall,
        }

    @staticmethod
    def run_domain_rules(
        obj: ControlObject, domain: str, rules: list[str]
    ) -> list[dict[str, Any]]:
        """Apply domain-specific validation rules to a control object."""
        results: list[dict[str, Any]] = []

        # Schema completeness check
        results.append({
            "rule_name": "schema_completeness",
            "passed": bool(obj.payload),
            "message": "Payload is present" if obj.payload else "Payload is empty",
            "severity": "error" if not obj.payload else "info",
            "metadata": {},
        })

        # Evidence check
        has_source = obj.source_document_id is not None
        results.append({
            "rule_name": "evidence_linkage",
            "passed": has_source,
            "message": "Linked to source document" if has_source else "No source document linked",
            "severity": "warning" if not has_source else "info",
            "metadata": {},
        })

        # Confidence check
        confidence = obj.confidence or 0.0
        passed = confidence >= 0.7
        results.append({
            "rule_name": "confidence_threshold",
            "passed": passed,
            "message": f"Confidence {confidence:.2f} {'meets' if passed else 'below'} threshold 0.70",
            "severity": "info" if passed else "warning",
            "metadata": {"confidence": confidence, "threshold": 0.70},
        })

        # Domain-specific rules
        if domain == "contract-margin" and obj.control_type:
            if obj.control_type.value == "billable_event":
                has_rate = bool((obj.payload or {}).get("rate"))
                results.append({
                    "rule_name": "billing_rate_present",
                    "passed": has_rate,
                    "message": "Billing rate defined" if has_rate else "No billing rate in payload",
                    "severity": "error" if not has_rate else "info",
                    "metadata": {},
                })

        return results

    @staticmethod
    def gate_confidence(
        rule_results: list[dict[str, Any]], confidence: float | None
    ) -> ValidationStatus:
        """Determine overall validation status based on rule results and confidence."""
        has_critical = any(
            not r["passed"] and r["severity"] == "critical" for r in rule_results
        )
        has_error = any(
            not r["passed"] and r["severity"] == "error" for r in rule_results
        )
        has_warning = any(
            not r["passed"] and r["severity"] == "warning" for r in rule_results
        )

        if has_critical:
            return ValidationStatus.escalated
        if has_error:
            return ValidationStatus.blocked
        if has_warning:
            return ValidationStatus.warned
        return ValidationStatus.passed

    async def persist_results(self, results: list[ValidationResult]) -> None:
        """Persist validation results to the database."""
        for r in results:
            self.db.add(r)
        await self.db.flush()

    @staticmethod
    def _compute_overall_status(results: list[ValidationResult]) -> str:
        """Compute worst-case status across all results."""
        priority = {
            ValidationStatus.escalated: 4,
            ValidationStatus.blocked: 3,
            ValidationStatus.warned: 2,
            ValidationStatus.passed: 1,
        }
        worst = max(results, key=lambda r: priority.get(r.status, 0))
        return worst.status.value

    async def get_validations_by_case(
        self, case_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[ValidationResult]:
        """Get all validation results for a case."""
        result = await self.db.execute(
            select(ValidationResult).where(
                ValidationResult.tenant_id == tenant_id,
            )
        )
        all_results = result.scalars().all()
        # Filter by case_id stored in metadata
        return [
            r for r in all_results
            if (r.metadata_ or {}).get("case_id") == str(case_id)
        ]
