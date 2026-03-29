"""Wave 3 validation chain executor — ordered execution, report assembly, decisioning."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.audit import FabricAuditHook
from app.core.control_object import ControlObject
from app.core.graph.service import GraphService
from app.core.validation.audit_hooks import ValidationAuditIntegration
from app.core.validation.domain_types import (
    ValidationAssemblyInput,
    ValidationAssemblyOutput,
    ValidationChainDef,
    ValidationChainId,
    ValidationContext,
    ValidationDecision,
    ValidationDecisionPolicy,
    ValidationDecisionTrace,
    ValidationEligibility,
    ValidationExecutionRequest,
    ValidationExecutionResult,
    ValidationFailure,
    ValidationFailureCode,
    ValidationPrecondition,
    ValidationReport,
    ValidationReportHash,
    ValidationResult,
    ValidationRun,
    ValidationRunId,
    ValidationScope,
    ValidationStep,
    ValidationTarget,
    ValidationWarning,
    W3ValidationStatus,
    new_chain_id,
    new_run_id,
    new_step_id,
)
from app.core.validation.repository import (
    InMemoryValidationReportRepository,
    InMemoryValidationRunRepository,
    ValidationReportRepository,
    ValidationRunRepository,
)
from app.core.validation.rule_model import (
    ValidationRuleRegistry,
    ValidationRuleTraceEntry,
    build_default_validation_rule_registry,
)
from app.core.types import ControlObjectId


class ValidationChainExecutor:
    """Executes the Wave 3 validation chain: ordered rules, report assembly, decisioning."""

    def __init__(
        self,
        graph_service: GraphService,
        rule_registry: ValidationRuleRegistry | None = None,
        run_repository: ValidationRunRepository | None = None,
        report_repository: ValidationReportRepository | None = None,
        audit_hook: FabricAuditHook | None = None,
        decision_policy: ValidationDecisionPolicy | None = None,
    ) -> None:
        self._graph = graph_service
        self._rule_registry = rule_registry or build_default_validation_rule_registry()
        self._run_repo = run_repository or InMemoryValidationRunRepository()
        self._report_repo = report_repository or InMemoryValidationReportRepository()
        self._audit_hook = audit_hook or FabricAuditHook()
        self._audit = ValidationAuditIntegration(self._audit_hook)
        self._decision_policy = decision_policy or ValidationDecisionPolicy()

    @property
    def rule_registry(self) -> ValidationRuleRegistry:
        return self._rule_registry

    @property
    def run_repository(self) -> ValidationRunRepository:
        return self._run_repo

    @property
    def report_repository(self) -> ValidationReportRepository:
        return self._report_repo

    def execute(self, request: ValidationExecutionRequest) -> ValidationExecutionResult:
        chain_id = request.chain_id or new_chain_id()
        run_id = new_run_id()

        run = ValidationRun(
            id=run_id,
            chain_id=chain_id,
            tenant_id=request.tenant_id,
            context=request.context,
            status=W3ValidationStatus.RUNNING,
        )
        self._run_repo.store_run(run)

        self._audit.validation_run_started(
            run_id=run_id,
            tenant_id=request.tenant_id,
        )

        objects = self._resolve_objects(request.context.target, request.tenant_id)

        preconditions = self._check_preconditions(objects, request.context)
        blocked = any(p.blocking and not p.met for p in preconditions)

        if blocked:
            report = self._build_blocked_report(
                run_id, chain_id, request.tenant_id, request.context, preconditions
            )
            self._report_repo.store_report(report)
            run.report = report
            run.status = W3ValidationStatus.BLOCKED
            run.completed_at = datetime.now(UTC)
            self._run_repo.store_run(run)

            self._audit.validation_failed(
                run_id=run_id,
                tenant_id=request.tenant_id,
                failure_count=len(report.failures),
            )
            self._audit.validation_run_completed(
                run_id=run_id,
                tenant_id=request.tenant_id,
                status=W3ValidationStatus.BLOCKED,
                decision=ValidationDecision.REJECTED,
            )

            return ValidationExecutionResult(
                run=run,
                report=report,
                decision=ValidationDecision.REJECTED,
            )

        ctx = self._build_rule_context(request.context)
        action_type = request.context.scope.action_type
        applicable_rules = self._rule_registry.get_applicable_rules(objects, action_type)

        steps: list[ValidationStep] = []
        all_failures: list[ValidationFailure] = []
        all_warnings: list[ValidationWarning] = []
        rule_traces: list[dict[str, Any]] = []

        for i, rule in enumerate(applicable_rules):
            step_id = new_step_id()
            result = rule.validate(objects, self._graph, ctx)
            result.step_id = step_id

            step = ValidationStep(
                id=step_id,
                order=i,
                rule_id=rule.rule_id,
                result=result,
                executed=True,
            )
            steps.append(step)
            all_failures.extend(result.failures)
            all_warnings.extend(result.warnings)

            self._audit.validation_step_completed(
                run_id=run_id,
                tenant_id=request.tenant_id,
                rule_id=rule.rule_id,
                passed=result.passed,
            )

            rule_traces.append({
                "rule_id": rule.rule_id,
                "category": rule.category.value,
                "passed": result.passed,
                "failure_count": len(result.failures),
                "warning_count": len(result.warnings),
            })

        status = self._determine_status(all_failures, all_warnings)
        decision = self._determine_decision(status, all_failures, all_warnings)
        eligibility = self._build_eligibility(decision, all_failures)

        decision_trace = ValidationDecisionTrace(
            run_id=run_id,
            chain_id=chain_id,
            steps_executed=len(steps),
            failures_total=len(all_failures),
            warnings_total=len(all_warnings),
            decision=decision,
            rule_traces=rule_traces,
        )

        report = ValidationReport(
            run_id=run_id,
            chain_id=chain_id,
            tenant_id=request.tenant_id,
            status=status,
            decision=decision,
            eligibility=eligibility,
            steps=steps,
            failures=all_failures,
            warnings=all_warnings,
            preconditions=preconditions,
            target=request.context.target,
            scope=request.context.scope,
            decision_trace=decision_trace,
        )
        report.compute_hash()
        self._report_repo.store_report(report)

        run.report = report
        run.status = status
        run.completed_at = datetime.now(UTC)
        self._run_repo.store_run(run)

        if all_failures:
            self._audit.validation_failed(
                run_id=run_id,
                tenant_id=request.tenant_id,
                failure_count=len(all_failures),
            )

        self._audit.validation_decision_recorded(
            run_id=run_id,
            tenant_id=request.tenant_id,
            decision=decision,
            report_hash=report.report_hash,
        )
        self._audit.validation_run_completed(
            run_id=run_id,
            tenant_id=request.tenant_id,
            status=status,
            decision=decision,
        )

        return ValidationExecutionResult(
            run=run,
            report=report,
            decision=decision,
        )

    def _resolve_objects(
        self, target: ValidationTarget, tenant_id: uuid.UUID
    ) -> list[ControlObject]:
        objects: list[ControlObject] = []
        for oid in target.object_ids:
            obj = self._graph.get_object(oid)
            if obj:
                objects.append(obj)
        return objects

    def _check_preconditions(
        self, objects: list[ControlObject], context: ValidationContext
    ) -> list[ValidationPrecondition]:
        preconditions: list[ValidationPrecondition] = []
        preconditions.append(
            ValidationPrecondition(
                name="has-target-objects",
                met=len(objects) > 0,
                description="At least one target object must be resolvable",
                blocking=True,
            )
        )
        return preconditions

    def _build_blocked_report(
        self,
        run_id: ValidationRunId,
        chain_id: ValidationChainId,
        tenant_id: uuid.UUID,
        context: ValidationContext,
        preconditions: list[ValidationPrecondition],
    ) -> ValidationReport:
        failures = [
            ValidationFailure(
                code=ValidationFailureCode.MISSING_VALIDATION_INPUT,
                description=f"Precondition '{p.name}' not met: {p.description}",
            )
            for p in preconditions
            if not p.met and p.blocking
        ]

        report = ValidationReport(
            run_id=run_id,
            chain_id=chain_id,
            tenant_id=tenant_id,
            status=W3ValidationStatus.BLOCKED,
            decision=ValidationDecision.REJECTED,
            eligibility=ValidationEligibility(
                decision=ValidationDecision.REJECTED,
                explanation="Blocked by unmet preconditions",
                blocking_failures=failures,
            ),
            failures=failures,
            preconditions=preconditions,
            target=context.target,
            scope=context.scope,
        )
        report.compute_hash()
        return report

    def _build_rule_context(self, context: ValidationContext) -> dict[str, Any]:
        return {
            "require_reconciled": context.require_reconciled,
            "min_confidence": context.min_confidence,
            "required_evidence_types": context.required_evidence_types,
            "required_states": context.required_states,
            "min_evidence": 1,
            **context.policy_overrides,
            **context.metadata,
        }

    def _determine_status(
        self,
        failures: list[ValidationFailure],
        warnings: list[ValidationWarning],
    ) -> W3ValidationStatus:
        if failures:
            return W3ValidationStatus.FAILED
        if warnings:
            return W3ValidationStatus.PASSED_WITH_WARNINGS
        return W3ValidationStatus.PASSED

    def _determine_decision(
        self,
        status: W3ValidationStatus,
        failures: list[ValidationFailure],
        warnings: list[ValidationWarning],
    ) -> ValidationDecision:
        if status == W3ValidationStatus.FAILED:
            return ValidationDecision.REJECTED
        if status == W3ValidationStatus.PASSED_WITH_WARNINGS:
            if self._decision_policy.proposal_only_on_warnings:
                return ValidationDecision.PROPOSAL_ONLY
            if not self._decision_policy.allow_warnings:
                return ValidationDecision.REJECTED
            if len(warnings) > self._decision_policy.max_warnings:
                return ValidationDecision.APPROVAL_REQUIRED
            return ValidationDecision.ELIGIBLE
        if self._decision_policy.auto_eligible_on_pass:
            return ValidationDecision.ELIGIBLE
        return ValidationDecision.APPROVAL_REQUIRED

    def _build_eligibility(
        self,
        decision: ValidationDecision,
        failures: list[ValidationFailure],
    ) -> ValidationEligibility:
        return ValidationEligibility(
            decision=decision,
            eligible_for_release=decision == ValidationDecision.ELIGIBLE,
            requires_approval=decision == ValidationDecision.APPROVAL_REQUIRED,
            proposal_only=decision == ValidationDecision.PROPOSAL_ONLY,
            blocking_failures=failures if decision == ValidationDecision.REJECTED else [],
            explanation=f"Decision: {decision.value}",
        )
