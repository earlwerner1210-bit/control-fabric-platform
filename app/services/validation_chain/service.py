"""Validation Chain Service — 8-stage deterministic release gate."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.validation_chain import (
    VALIDATION_STAGE_ORDER,
    ChainOutcome,
    StepVerdict,
    ValidationChainRequest,
    ValidationChainResponse,
    ValidationChainSummary,
    ValidationStage,
    ValidationStepResult,
)


class ValidationChainService:
    """Runs an 8-stage validation chain for candidate action release.

    Stages: schema → evidence → boundary → rule → cross_plane → policy → confidence → release
    """

    def __init__(
        self,
        validators: dict[ValidationStage, Any] | None = None,
    ) -> None:
        self._validators = validators or {}
        self._runs: dict[uuid.UUID, dict[str, Any]] = {}

    def register_validator(
        self,
        stage: ValidationStage,
        validator_fn: Any,
    ) -> None:
        self._validators[stage] = validator_fn

    def run_chain(
        self,
        request: ValidationChainRequest,
    ) -> ValidationChainResponse:
        run_id = uuid.uuid4()
        start = datetime.now(UTC)
        steps: list[ValidationStepResult] = []
        blocking_stage = None
        blocking_message = None

        for stage in VALIDATION_STAGE_ORDER:
            step_start = datetime.now(UTC)

            if stage in request.skip_stages:
                steps.append(
                    ValidationStepResult(
                        stage=stage,
                        verdict=StepVerdict.SKIP,
                        message=f"Stage {stage.value} skipped by request",
                        skipped=True,
                        skip_reason="Excluded in skip_stages",
                    )
                )
                continue

            validator = self._validators.get(stage)
            if validator:
                try:
                    result = validator(
                        stage=stage,
                        request=request,
                        context=request.context,
                    )
                    verdict = StepVerdict(result.get("verdict", "pass"))
                    message = result.get("message", f"Stage {stage.value} completed")
                    details = result.get("details", {})
                except Exception as e:
                    verdict = StepVerdict.FAIL
                    message = f"Stage {stage.value} error: {e!s}"
                    details = {"error": str(e)}
            else:
                verdict, message, details = self._default_validate(stage, request)

            step_end = datetime.now(UTC)
            duration_ms = (step_end - step_start).total_seconds() * 1000

            steps.append(
                ValidationStepResult(
                    stage=stage,
                    verdict=verdict,
                    message=message,
                    details=details,
                    duration_ms=duration_ms,
                )
            )

            if verdict == StepVerdict.FAIL:
                blocking_stage = stage
                blocking_message = message
                if request.fail_fast:
                    break

        end = datetime.now(UTC)
        total_duration = (end - start).total_seconds() * 1000

        passed = sum(1 for s in steps if s.verdict == StepVerdict.PASS)
        warned = sum(1 for s in steps if s.verdict == StepVerdict.WARN)
        failed = sum(1 for s in steps if s.verdict == StepVerdict.FAIL)
        skipped = sum(1 for s in steps if s.verdict == StepVerdict.SKIP)

        if failed > 0:
            outcome = ChainOutcome.BLOCKED
        elif warned > 0:
            outcome = ChainOutcome.WARN_RELEASED
        else:
            outcome = ChainOutcome.RELEASED

        response = ValidationChainResponse(
            id=run_id,
            pilot_case_id=request.pilot_case_id,
            tenant_id=request.tenant_id,
            outcome=outcome,
            steps=steps,
            total_steps=len(steps),
            passed_steps=passed,
            warned_steps=warned,
            failed_steps=failed,
            skipped_steps=skipped,
            blocking_stage=blocking_stage,
            blocking_message=blocking_message,
            duration_ms=total_duration,
            metadata=request.metadata,
            created_at=start,
        )

        self._runs[run_id] = {
            "response": response,
            "tenant_id": request.tenant_id,
        }

        return response

    def get_run(self, run_id: uuid.UUID) -> ValidationChainResponse | None:
        entry = self._runs.get(run_id)
        return entry["response"] if entry else None

    def get_summary(self, tenant_id: uuid.UUID) -> ValidationChainSummary:
        runs = [r["response"] for r in self._runs.values() if r["tenant_id"] == tenant_id]

        released = sum(1 for r in runs if r.outcome == ChainOutcome.RELEASED)
        blocked = sum(1 for r in runs if r.outcome == ChainOutcome.BLOCKED)
        warn_released = sum(1 for r in runs if r.outcome == ChainOutcome.WARN_RELEASED)
        escalated = sum(1 for r in runs if r.outcome == ChainOutcome.ESCALATED)

        blocking_stages: dict[str, int] = {}
        durations: list[float] = []
        by_stage_verdict: dict[str, dict[str, int]] = {}

        for r in runs:
            durations.append(r.duration_ms)
            if r.blocking_stage:
                bs = (
                    r.blocking_stage.value
                    if hasattr(r.blocking_stage, "value")
                    else str(r.blocking_stage)
                )
                blocking_stages[bs] = blocking_stages.get(bs, 0) + 1
            for step in r.steps:
                stage_key = step.stage.value if hasattr(step.stage, "value") else str(step.stage)
                if stage_key not in by_stage_verdict:
                    by_stage_verdict[stage_key] = {}
                v = step.verdict.value if hasattr(step.verdict, "value") else str(step.verdict)
                by_stage_verdict[stage_key][v] = by_stage_verdict[stage_key].get(v, 0) + 1

        most_common = max(blocking_stages, key=blocking_stages.get) if blocking_stages else None
        n = len(runs)

        return ValidationChainSummary(
            total_runs=n,
            released=released,
            blocked=blocked,
            warn_released=warn_released,
            escalated=escalated,
            most_common_blocking_stage=most_common,
            block_rate=blocked / n if n > 0 else 0.0,
            avg_duration_ms=sum(durations) / n if n > 0 else 0.0,
            by_stage_verdict=by_stage_verdict,
        )

    def _default_validate(
        self,
        stage: ValidationStage,
        request: ValidationChainRequest,
    ) -> tuple[StepVerdict, str, dict[str, Any]]:
        ctx = request.context

        if stage == ValidationStage.SCHEMA:
            if ctx.get("schema_valid", True):
                return StepVerdict.PASS, "Schema validation passed", {}
            return StepVerdict.FAIL, "Schema validation failed", {"reason": "invalid_schema"}

        if stage == ValidationStage.EVIDENCE:
            score = ctx.get("evidence_completeness", 1.0)
            if score >= 0.8:
                return StepVerdict.PASS, f"Evidence completeness: {score:.0%}", {"score": score}
            if score >= 0.5:
                return StepVerdict.WARN, f"Evidence incomplete: {score:.0%}", {"score": score}
            return StepVerdict.FAIL, f"Evidence insufficient: {score:.0%}", {"score": score}

        if stage == ValidationStage.BOUNDARY:
            if ctx.get("boundary_valid", True):
                return StepVerdict.PASS, "Boundary check passed", {}
            return StepVerdict.FAIL, "Boundary violation detected", {}

        if stage == ValidationStage.RULE:
            failed_rules = ctx.get("failed_rules", [])
            if not failed_rules:
                return StepVerdict.PASS, "All rules passed", {}
            return (
                StepVerdict.FAIL,
                f"Rules failed: {', '.join(failed_rules)}",
                {"failed_rules": failed_rules},
            )

        if stage == ValidationStage.CROSS_PLANE:
            conflicts = ctx.get("cross_plane_conflicts", 0)
            if conflicts == 0:
                return StepVerdict.PASS, "No cross-plane conflicts", {}
            if conflicts <= 2:
                return (
                    StepVerdict.WARN,
                    f"{conflicts} cross-plane conflict(s)",
                    {"count": conflicts},
                )
            return StepVerdict.FAIL, f"{conflicts} cross-plane conflicts", {"count": conflicts}

        if stage == ValidationStage.POLICY:
            if ctx.get("policy_compliant", True):
                return StepVerdict.PASS, "Policy check passed", {}
            return StepVerdict.FAIL, "Policy violation", {"reason": ctx.get("policy_reason", "")}

        if stage == ValidationStage.CONFIDENCE:
            conf = ctx.get("confidence", 1.0)
            threshold = ctx.get("confidence_threshold", 0.7)
            if conf >= threshold:
                return (
                    StepVerdict.PASS,
                    f"Confidence {conf:.2f} >= {threshold:.2f}",
                    {"confidence": conf},
                )
            return (
                StepVerdict.FAIL,
                f"Confidence {conf:.2f} < {threshold:.2f}",
                {"confidence": conf, "threshold": threshold},
            )

        if stage == ValidationStage.RELEASE:
            return StepVerdict.PASS, "Release gate passed", {}

        return StepVerdict.PASS, f"Stage {stage.value} passed (default)", {}
