"""Eval service business logic."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import EvalCase, EvalRun
from shared.telemetry.logging import get_logger

logger = get_logger("eval_service")


class EvalService:
    """Runs evaluation batches against gold-standard test cases."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run_eval_batch(
        self,
        eval_case_ids: list[uuid.UUID],
        tenant_id: uuid.UUID,
        model_provider: str = "vllm",
    ) -> dict[str, Any]:
        """Run evaluation for a batch of eval cases."""
        result = await self.db.execute(
            select(EvalCase).where(
                EvalCase.id.in_(eval_case_ids),
                EvalCase.tenant_id == tenant_id,
            )
        )
        cases = list(result.scalars().all())
        if not cases:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No eval cases found")

        batch_run_id = uuid.uuid4()
        runs: list[EvalRun] = []
        total_score = 0.0
        passed_count = 0

        for case in cases:
            # Simulate running the model (in production, call inference-gateway)
            actual_output = self._simulate_model_output(case.input_data, case.expected_output)
            metrics = self.compute_metrics(case.expected_output, actual_output)
            score = metrics.get("f1", 0.0)
            case_passed = self.compare_output_to_gold(case.expected_output, actual_output)

            run = EvalRun(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                eval_case_id=case.id,
                actual_output=actual_output,
                score=score,
                passed=case_passed,
                detail={
                    "metrics": metrics,
                    "provider": model_provider,
                    "batch_run_id": str(batch_run_id),
                },
            )
            self.db.add(run)
            runs.append(run)
            total_score += score
            if case_passed:
                passed_count += 1

        await self.db.flush()
        await self.store_results(runs)

        avg_score = total_score / len(cases) if cases else 0.0
        logger.info(
            "Eval batch %s: %d/%d passed (avg score=%.2f)",
            batch_run_id,
            passed_count,
            len(cases),
            avg_score,
        )

        return {
            "run_id": batch_run_id,
            "total": len(cases),
            "passed": passed_count,
            "failed": len(cases) - passed_count,
            "metrics": {
                "avg_score": round(avg_score, 4),
                "pass_rate": round(passed_count / len(cases), 4) if cases else 0,
            },
            "results": runs,
        }

    @staticmethod
    def compare_output_to_gold(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
        """Compare model output to gold standard."""
        if not expected or not actual:
            return False
        # Simple key overlap heuristic
        expected_keys = set(expected.keys())
        actual_keys = set(actual.keys())
        overlap = expected_keys & actual_keys
        return len(overlap) / max(len(expected_keys), 1) >= 0.5

    @staticmethod
    def compute_metrics(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, float]:
        """Compute precision, recall, F1 based on key/value overlap."""
        exp_items = set(str(k) + "=" + str(v) for k, v in expected.items())
        act_items = set(str(k) + "=" + str(v) for k, v in actual.items())

        if not exp_items or not act_items:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

        true_pos = len(exp_items & act_items)
        precision = true_pos / len(act_items) if act_items else 0.0
        recall = true_pos / len(exp_items) if exp_items else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    async def store_results(self, runs: list[EvalRun]) -> None:
        """Persist eval run results."""
        # Already added to session in run_eval_batch; this is a hook for extensions
        pass

    @staticmethod
    def _simulate_model_output(
        input_data: dict[str, Any], expected: dict[str, Any]
    ) -> dict[str, Any]:
        """Simulate model output for testing. Returns partial match with expected."""
        output: dict[str, Any] = {}
        for i, (k, v) in enumerate(expected.items()):
            if i % 2 == 0:  # simulate ~50% match
                output[k] = v
            else:
                output[k] = f"simulated_{k}"
        return output

    async def get_eval_run(self, run_id: uuid.UUID, tenant_id: uuid.UUID) -> list[EvalRun]:
        """Get all runs for a given batch run_id."""
        result = await self.db.execute(select(EvalRun).where(EvalRun.tenant_id == tenant_id))
        all_runs = result.scalars().all()
        return [r for r in all_runs if (r.detail or {}).get("batch_run_id") == str(run_id)]

    async def list_eval_cases(
        self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[EvalCase]:
        """List eval cases."""
        result = await self.db.execute(
            select(EvalCase)
            .where(EvalCase.tenant_id == tenant_id)
            .order_by(EvalCase.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create_eval_case(
        self,
        tenant_id: uuid.UUID,
        eval_type: str,
        input_data: dict[str, Any],
        expected_output: dict[str, Any],
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvalCase:
        """Create a new eval case."""
        case = EvalCase(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            eval_type=eval_type,
            input_data=input_data,
            expected_output=expected_output,
            tags=tags or [],
            metadata_=metadata or {},
        )
        self.db.add(case)
        await self.db.flush()
        logger.info("Created eval case %s (type=%s)", case.id, eval_type)
        return case
