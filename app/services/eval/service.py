"""Eval service – gold-case testing and regression."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import EvalCase, EvalRun

logger = get_logger("eval")


class EvalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run_eval_batch(
        self,
        tenant_id: uuid.UUID,
        domain: str | None = None,
        workflow_type: str | None = None,
        case_ids: list[uuid.UUID] | None = None,
    ) -> list[EvalRun]:
        """Run eval cases and produce results."""
        stmt = select(EvalCase)
        if domain:
            stmt = stmt.where(EvalCase.domain == domain)
        if workflow_type:
            stmt = stmt.where(EvalCase.workflow_type == workflow_type)
        if case_ids:
            stmt = stmt.where(EvalCase.id.in_(case_ids))

        result = await self.db.execute(stmt)
        cases = list(result.scalars().all())

        runs: list[EvalRun] = []
        for case in cases:
            run = await self._evaluate_case(tenant_id, case)
            runs.append(run)

        await self.db.flush()
        logger.info("eval_batch_complete", cases=len(cases), domain=domain)
        return runs

    async def _evaluate_case(self, tenant_id: uuid.UUID, case: EvalCase) -> EvalRun:
        """Compare expected output with actual (simulated for now)."""
        # In production, this would trigger the actual workflow
        # For now, we compare against the expected output structure
        expected = case.expected_output
        actual = self._simulate_output(case)

        passed, score, details = self._compare_outputs(expected, actual)

        run = EvalRun(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            eval_case_id=case.id,
            actual_output=actual,
            passed=passed,
            score=score,
            details=details,
        )
        self.db.add(run)
        return run

    def _simulate_output(self, case: EvalCase) -> dict:
        """Simulate output for eval case. Replace with actual workflow call in production."""
        return case.expected_output  # Passthrough for now

    def _compare_outputs(self, expected: dict, actual: dict) -> tuple[bool, float, dict]:
        """Compare expected and actual outputs."""
        matching_keys = 0
        total_keys = len(expected)
        mismatches: list[str] = []

        for key, expected_val in expected.items():
            actual_val = actual.get(key)
            if actual_val == expected_val:
                matching_keys += 1
            else:
                mismatches.append(f"{key}: expected={expected_val}, actual={actual_val}")

        score = matching_keys / max(total_keys, 1)
        passed = score >= 0.8

        return (
            passed,
            score,
            {
                "matching_keys": matching_keys,
                "total_keys": total_keys,
                "mismatches": mismatches,
            },
        )

    async def list_cases(
        self, domain: str | None = None, workflow_type: str | None = None
    ) -> list[EvalCase]:
        stmt = select(EvalCase)
        if domain:
            stmt = stmt.where(EvalCase.domain == domain)
        if workflow_type:
            stmt = stmt.where(EvalCase.workflow_type == workflow_type)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_eval_summary(
        self, tenant_id: uuid.UUID, run_ids: list[uuid.UUID] | None = None
    ) -> dict[str, Any]:
        stmt = select(EvalRun).where(EvalRun.tenant_id == tenant_id)
        if run_ids:
            stmt = stmt.where(EvalRun.id.in_(run_ids))
        result = await self.db.execute(stmt)
        runs = list(result.scalars().all())

        total = len(runs)
        passed = sum(1 for r in runs if r.passed)
        scores = [r.score for r in runs if r.score is not None]

        return {
            "total_cases": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / max(total, 1),
            "avg_score": sum(scores) / max(len(scores), 1) if scores else None,
        }
