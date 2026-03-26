"""Evaluation service -- run deterministic regression / accuracy suites."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


@dataclass
class EvalCase:
    """A single evaluation case loaded from a suite definition."""

    name: str
    input_data: dict[str, Any] = field(default_factory=dict)
    expected: Any = None
    tags: list[str] = field(default_factory=list)


@dataclass
class EvalCaseResult:
    """Outcome of running a single eval case."""

    name: str
    passed: bool
    expected: Any = None
    actual: Any = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalRun:
    """Aggregated outcome of a full suite run."""

    run_id: UUID
    suite: str
    total: int
    passed: int
    failed: int
    results: list[EvalCaseResult] = field(default_factory=list)


# ── Built-in sample suites (in production these are loaded from YAML/JSON) ─


_SAMPLE_SUITES: dict[str, list[dict[str, Any]]] = {
    "contract_compile_v1": [
        {
            "name": "basic_contract_parse",
            "input_data": {"text": "Master Service Agreement between Acme and TelcoCo"},
            "expected": {"document_type": "contract"},
            "tags": ["smoke"],
        },
        {
            "name": "sla_detection",
            "input_data": {"text": "Service Level Agreement: uptime 99.9%"},
            "expected": {"document_type": "sla"},
            "tags": ["smoke", "sla"],
        },
    ],
    "margin_basic": [
        {
            "name": "simple_billable",
            "input_data": {"verdict": "billable", "total_billed": 1000},
            "expected": {"verdict": "billable"},
            "tags": ["smoke"],
        },
    ],
}


class EvalService:
    """Loads and executes evaluation suites for regression testing."""

    def run_suite(
        self,
        suite_name: str,
        tags: list[str] | None = None,
    ) -> EvalRun:
        """Run all cases in *suite_name*, optionally filtered by *tags*."""
        cases = self.load_cases(suite_name, tags or [])
        results: list[EvalCaseResult] = []
        for case in cases:
            result = self.evaluate_case(case)
            results.append(result)

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed

        run = EvalRun(
            run_id=uuid4(),
            suite=suite_name,
            total=len(results),
            passed=passed,
            failed=failed,
            results=results,
        )
        logger.info(
            "eval.run_suite: suite=%s total=%d passed=%d failed=%d",
            suite_name,
            run.total,
            run.passed,
            run.failed,
        )
        return run

    @staticmethod
    def load_cases(
        suite: str,
        tags: list[str],
    ) -> list[EvalCase]:
        """Load eval cases from the built-in registry, filtered by tags."""
        raw_cases = _SAMPLE_SUITES.get(suite, [])
        cases: list[EvalCase] = []
        for raw in raw_cases:
            case = EvalCase(
                name=raw["name"],
                input_data=raw.get("input_data", {}),
                expected=raw.get("expected"),
                tags=raw.get("tags", []),
            )
            if tags:
                if not set(tags) & set(case.tags):
                    continue
            cases.append(case)
        return cases

    @staticmethod
    def evaluate_case(case: EvalCase) -> EvalCaseResult:
        """Execute a single eval case and compare actual vs. expected.

        The stub implementation does a shallow dict comparison.  In production
        this would invoke the actual workflow / service under test.
        """
        # Stub: treat input_data as the "actual" output to compare
        actual = case.input_data
        expected = case.expected

        if expected is None:
            return EvalCaseResult(
                name=case.name,
                passed=True,
                expected=expected,
                actual=actual,
                details={"reason": "no expected value defined, auto-pass"},
            )

        # Shallow key-by-key comparison for dict expectations
        if isinstance(expected, dict) and isinstance(actual, dict):
            mismatches: dict[str, Any] = {}
            for key, exp_val in expected.items():
                act_val = actual.get(key)
                if act_val != exp_val:
                    mismatches[key] = {"expected": exp_val, "actual": act_val}
            passed = len(mismatches) == 0
            return EvalCaseResult(
                name=case.name,
                passed=passed,
                expected=expected,
                actual=actual,
                details={"mismatches": mismatches} if mismatches else {},
            )

        passed = actual == expected
        return EvalCaseResult(
            name=case.name,
            passed=passed,
            expected=expected,
            actual=actual,
        )


# Singleton
eval_service = EvalService()
