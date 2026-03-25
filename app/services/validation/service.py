"""Validation service – schema, evidence, rule, and confidence validation."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import ValidationResult, ValidationStatus
from app.domain_packs.contract_margin.schemas import BillableCategory
from app.schemas.validation import RuleResult
from app.schemas.workflows import MarginVerdict

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

    async def validate_billability_decision(
        self,
        tenant_id: uuid.UUID,
        case_id: uuid.UUID,
        decision: dict,
        domain_pack: str = "contract_margin",
    ) -> ValidationResult:
        """Validate a billability decision against deterministic rules.

        Checks:
        1. Rate card evidence exists (rate_applied is not None when billable=True)
        2. Reasons are populated (non-empty list)
        3. Confidence meets minimum threshold (>= 0.6 for billable, >= 0.8 for non-billable)
        4. Rule results present and all critical rules passed
        5. Category is valid BillableCategory value
        6. No conflicting rule results (e.g. "has_valid_rate" passed but rate_applied is None)
        """
        results: list[RuleResult] = []
        billable = decision.get("billable", False)
        rate_applied = decision.get("rate_applied")
        reasons = decision.get("reasons", [])
        confidence = decision.get("confidence", 0.0)
        rule_results_raw = decision.get("rule_results", [])
        category = decision.get("category")

        # 1. Rate card evidence when billable
        if billable:
            results.append(
                RuleResult(
                    rule_name="rate_card_evidence",
                    passed=rate_applied is not None,
                    message="Rate applied is present for billable decision"
                    if rate_applied is not None
                    else "Billable decision requires rate_applied to be set",
                    severity="error" if rate_applied is None else "info",
                )
            )

        # 2. Reasons populated
        reasons_populated = isinstance(reasons, list) and len(reasons) > 0
        results.append(
            RuleResult(
                rule_name="reasons_populated",
                passed=reasons_populated,
                message=f"{len(reasons)} reasons provided"
                if reasons_populated
                else "Reasons list is empty or missing",
                severity="error" if not reasons_populated else "info",
            )
        )

        # 3. Confidence threshold
        min_confidence = 0.6 if billable else 0.8
        conf_ok = confidence >= min_confidence
        results.append(
            RuleResult(
                rule_name="confidence_threshold",
                passed=conf_ok,
                message=f"Confidence {confidence:.2f} meets threshold {min_confidence}"
                if conf_ok
                else f"Confidence {confidence:.2f} below required {min_confidence} for {'billable' if billable else 'non-billable'}",
                severity="warning" if not conf_ok else "info",
            )
        )

        # 4. Rule results present and critical rules passed
        has_rules = isinstance(rule_results_raw, list) and len(rule_results_raw) > 0
        results.append(
            RuleResult(
                rule_name="rule_results_present",
                passed=has_rules,
                message=f"{len(rule_results_raw)} rule results present"
                if has_rules
                else "No rule results provided",
                severity="error" if not has_rules else "info",
            )
        )

        if has_rules:
            critical_failures = [
                r for r in rule_results_raw
                if r.get("severity") == "critical" and not r.get("passed", False)
            ]
            results.append(
                RuleResult(
                    rule_name="critical_rules_passed",
                    passed=len(critical_failures) == 0,
                    message="All critical rules passed"
                    if not critical_failures
                    else f"{len(critical_failures)} critical rule(s) failed",
                    severity="critical" if critical_failures else "info",
                )
            )

        # 5. Category validation
        valid_categories = {c.value for c in BillableCategory}
        if category is not None:
            cat_valid = category in valid_categories
            results.append(
                RuleResult(
                    rule_name="valid_category",
                    passed=cat_valid,
                    message=f"Category '{category}' is valid"
                    if cat_valid
                    else f"Invalid category '{category}'; valid: {valid_categories}",
                    severity="error" if not cat_valid else "info",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_name="valid_category",
                    passed=False,
                    message="Category is missing",
                    severity="error",
                )
            )

        # 6. Conflicting rule results
        if has_rules:
            rate_rule = next(
                (r for r in rule_results_raw if r.get("rule_name") == "has_valid_rate"),
                None,
            )
            if rate_rule and rate_rule.get("passed", False) and rate_applied is None:
                results.append(
                    RuleResult(
                        rule_name="no_conflicting_rules",
                        passed=False,
                        message="Conflict: 'has_valid_rate' passed but rate_applied is None",
                        severity="error",
                    )
                )
            else:
                results.append(
                    RuleResult(
                        rule_name="no_conflicting_rules",
                        passed=True,
                        message="No conflicting rule results detected",
                        severity="info",
                    )
                )

        status = self._determine_status(results)

        vr = ValidationResult(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_case_id=case_id,
            validator_name=f"{domain_pack}_billability_validator",
            status=status,
            domain=domain_pack,
            rule_results={"rules": [r.model_dump() for r in results]},
            summary=self._build_summary(results, status),
        )
        self.db.add(vr)
        await self.db.flush()

        logger.info(
            "billability_validation_complete",
            case_id=str(case_id),
            status=status.value,
            rules_checked=len(results),
        )
        return vr

    async def validate_margin_diagnosis(
        self,
        tenant_id: uuid.UUID,
        case_id: uuid.UUID,
        diagnosis: dict,
        domain_pack: str = "contract_margin",
    ) -> ValidationResult:
        """Validate a margin diagnosis result.

        Checks:
        1. Verdict is valid MarginVerdict value
        2. If verdict is "under_recovery" or "penalty_risk", leakage_drivers must be non-empty
        3. If verdict is "billable", no critical leakage triggers should exist
        4. Evidence object IDs are valid UUIDs
        5. Recovery recommendations are populated when leakage exists
        6. Executive summary is present and non-empty
        7. Confidence score is within [0, 1]
        """
        results: list[RuleResult] = []
        verdict = diagnosis.get("verdict", "")
        leakage_drivers = diagnosis.get("leakage_drivers", [])
        evidence_object_ids = diagnosis.get("evidence_object_ids", [])
        recovery_recs = diagnosis.get("recovery_recommendations", [])
        executive_summary = diagnosis.get("executive_summary")
        confidence = diagnosis.get("confidence")

        # 1. Valid MarginVerdict
        valid_verdicts = {v.value for v in MarginVerdict}
        verdict_ok = verdict in valid_verdicts
        results.append(
            RuleResult(
                rule_name="valid_margin_verdict",
                passed=verdict_ok,
                message=f"Verdict '{verdict}' is valid"
                if verdict_ok
                else f"Invalid verdict '{verdict}'; valid: {valid_verdicts}",
                severity="error" if not verdict_ok else "info",
            )
        )

        # 2. Leakage drivers required for under_recovery / penalty_risk
        if verdict in ("under_recovery", "penalty_risk"):
            has_drivers = isinstance(leakage_drivers, list) and len(leakage_drivers) > 0
            results.append(
                RuleResult(
                    rule_name="leakage_drivers_required",
                    passed=has_drivers,
                    message=f"{len(leakage_drivers)} leakage drivers provided"
                    if has_drivers
                    else f"Verdict '{verdict}' requires non-empty leakage_drivers",
                    severity="error" if not has_drivers else "info",
                )
            )

        # 3. Billable verdict should not have critical leakage triggers
        if verdict == "billable":
            leakage_triggers = diagnosis.get("leakage_triggers", [])
            critical_triggers = [
                t for t in leakage_triggers
                if isinstance(t, dict) and t.get("severity") == "critical"
            ]
            no_critical = len(critical_triggers) == 0
            results.append(
                RuleResult(
                    rule_name="billable_no_critical_leakage",
                    passed=no_critical,
                    message="No critical leakage triggers for billable verdict"
                    if no_critical
                    else f"{len(critical_triggers)} critical leakage trigger(s) conflict with billable verdict",
                    severity="error" if not no_critical else "info",
                )
            )

        # 4. Evidence object IDs are valid UUIDs
        all_valid_uuids = True
        for eid in evidence_object_ids:
            try:
                uuid.UUID(str(eid))
            except (ValueError, AttributeError):
                all_valid_uuids = False
                break
        results.append(
            RuleResult(
                rule_name="evidence_ids_valid_uuids",
                passed=all_valid_uuids,
                message=f"{len(evidence_object_ids)} valid evidence UUIDs"
                if all_valid_uuids
                else "One or more evidence_object_ids are not valid UUIDs",
                severity="error" if not all_valid_uuids else "info",
            )
        )

        # 5. Recovery recommendations when leakage exists
        has_leakage = len(leakage_drivers) > 0
        if has_leakage:
            has_recs = isinstance(recovery_recs, list) and len(recovery_recs) > 0
            results.append(
                RuleResult(
                    rule_name="recovery_recommendations_present",
                    passed=has_recs,
                    message=f"{len(recovery_recs)} recovery recommendations provided"
                    if has_recs
                    else "Leakage detected but no recovery recommendations provided",
                    severity="warning" if not has_recs else "info",
                )
            )

        # 6. Executive summary present
        summary_ok = isinstance(executive_summary, str) and len(executive_summary.strip()) > 0
        results.append(
            RuleResult(
                rule_name="executive_summary_present",
                passed=summary_ok,
                message="Executive summary is present"
                if summary_ok
                else "Executive summary is missing or empty",
                severity="warning" if not summary_ok else "info",
            )
        )

        # 7. Confidence in [0, 1]
        if confidence is not None:
            conf_valid = isinstance(confidence, (int, float)) and 0 <= confidence <= 1
            results.append(
                RuleResult(
                    rule_name="confidence_in_range",
                    passed=conf_valid,
                    message=f"Confidence {confidence} is within [0, 1]"
                    if conf_valid
                    else f"Confidence {confidence} is outside valid range [0, 1]",
                    severity="error" if not conf_valid else "info",
                )
            )

        status = self._determine_status(results)

        vr = ValidationResult(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_case_id=case_id,
            validator_name=f"{domain_pack}_margin_diagnosis_validator",
            status=status,
            domain=domain_pack,
            rule_results={"rules": [r.model_dump() for r in results]},
            summary=self._build_summary(results, status),
        )
        self.db.add(vr)
        await self.db.flush()

        logger.info(
            "margin_diagnosis_validation_complete",
            case_id=str(case_id),
            status=status.value,
            rules_checked=len(results),
        )
        return vr

    async def validate_reconciliation_output(
        self,
        tenant_id: uuid.UUID,
        case_id: uuid.UUID,
        reconciliation: dict,
    ) -> ValidationResult:
        """Validate cross-pack reconciliation results.

        Checks:
        1. All cross-plane links have valid source/target references
        2. Conflict severities are valid values
        3. Evidence bundle has at least one evidence item
        4. No orphaned links (link targets exist in the evidence set)
        5. Verdict is consistent with detected conflicts
        """
        results: list[RuleResult] = []
        links = reconciliation.get("links", [])
        conflicts = reconciliation.get("conflicts", [])
        evidence_bundle = reconciliation.get("evidence_bundle", [])
        verdict = reconciliation.get("verdict", "")

        # 1. Cross-plane links have valid source/target
        links_valid = True
        for link in links:
            source = link.get("source_id")
            target = link.get("target_id")
            if not source or not target:
                links_valid = False
                break
            try:
                uuid.UUID(str(source))
                uuid.UUID(str(target))
            except (ValueError, AttributeError):
                links_valid = False
                break
        results.append(
            RuleResult(
                rule_name="links_valid_references",
                passed=links_valid,
                message=f"{len(links)} links have valid source/target references"
                if links_valid
                else "One or more links have missing or invalid source/target references",
                severity="error" if not links_valid else "info",
            )
        )

        # 2. Conflict severities valid
        valid_severities = {"low", "medium", "high", "critical"}
        severities_valid = True
        for conflict in conflicts:
            sev = conflict.get("severity", "")
            if sev not in valid_severities:
                severities_valid = False
                break
        results.append(
            RuleResult(
                rule_name="conflict_severities_valid",
                passed=severities_valid,
                message="All conflict severities are valid"
                if severities_valid
                else f"Invalid conflict severity found; valid: {valid_severities}",
                severity="error" if not severities_valid else "info",
            )
        )

        # 3. Evidence bundle has at least one item
        has_evidence = isinstance(evidence_bundle, list) and len(evidence_bundle) > 0
        results.append(
            RuleResult(
                rule_name="evidence_bundle_populated",
                passed=has_evidence,
                message=f"Evidence bundle has {len(evidence_bundle)} items"
                if has_evidence
                else "Evidence bundle is empty",
                severity="warning" if not has_evidence else "info",
            )
        )

        # 4. No orphaned links
        evidence_ids = set()
        for ev in evidence_bundle:
            eid = ev.get("id") or ev.get("evidence_id")
            if eid:
                evidence_ids.add(str(eid))

        orphaned = False
        for link in links:
            target = str(link.get("target_id", ""))
            if target and target not in evidence_ids:
                orphaned = True
                break
        results.append(
            RuleResult(
                rule_name="no_orphaned_links",
                passed=not orphaned,
                message="All link targets exist in the evidence set"
                if not orphaned
                else "Orphaned link detected: target not found in evidence bundle",
                severity="error" if orphaned else "info",
            )
        )

        # 5. Verdict consistency with conflicts
        has_conflicts = len(conflicts) > 0
        verdict_consistent = True
        if has_conflicts and verdict in ("clean", "no_issues"):
            verdict_consistent = False
        if not has_conflicts and verdict in ("conflicted", "needs_resolution"):
            verdict_consistent = False
        results.append(
            RuleResult(
                rule_name="verdict_conflict_consistency",
                passed=verdict_consistent,
                message="Verdict is consistent with detected conflicts"
                if verdict_consistent
                else f"Verdict '{verdict}' is inconsistent with {len(conflicts)} conflicts detected",
                severity="error" if not verdict_consistent else "info",
            )
        )

        status = self._determine_status(results)

        vr = ValidationResult(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_case_id=case_id,
            validator_name="reconciliation_validator",
            status=status,
            domain="cross_pack",
            rule_results={"rules": [r.model_dump() for r in results]},
            summary=self._build_summary(results, status),
        )
        self.db.add(vr)
        await self.db.flush()

        logger.info(
            "reconciliation_validation_complete",
            case_id=str(case_id),
            status=status.value,
            rules_checked=len(results),
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
