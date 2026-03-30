"""Wave 2 reconciliation repositories — run and case persistence abstractions."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.core.reconciliation.domain_types import (
    ReconciliationCase,
    ReconciliationCaseId,
    ReconciliationCaseStatus,
    ReconciliationRun,
    ReconciliationRunId,
    ReconciliationStatus,
)
from app.core.types import PlaneType


class ReconciliationRunRepository(ABC):
    @abstractmethod
    def store_run(self, run: ReconciliationRun) -> None: ...

    @abstractmethod
    def get_run(self, run_id: ReconciliationRunId) -> ReconciliationRun | None: ...

    @abstractmethod
    def list_runs(
        self,
        tenant_id: uuid.UUID,
        status: ReconciliationStatus | None = None,
    ) -> list[ReconciliationRun]: ...


class ReconciliationCaseRepository(ABC):
    @abstractmethod
    def store_case(self, case: ReconciliationCase) -> None: ...

    @abstractmethod
    def get_case(self, case_id: ReconciliationCaseId) -> ReconciliationCase | None: ...

    @abstractmethod
    def list_cases(
        self,
        tenant_id: uuid.UUID,
        run_id: ReconciliationRunId | None = None,
        status: ReconciliationCaseStatus | None = None,
    ) -> list[ReconciliationCase]: ...

    @abstractmethod
    def list_cases_for_run(self, run_id: ReconciliationRunId) -> list[ReconciliationCase]: ...


class InMemoryReconciliationRunRepository(ReconciliationRunRepository):
    def __init__(self) -> None:
        self._runs: dict[ReconciliationRunId, ReconciliationRun] = {}

    def store_run(self, run: ReconciliationRun) -> None:
        self._runs[run.id] = run

    def get_run(self, run_id: ReconciliationRunId) -> ReconciliationRun | None:
        return self._runs.get(run_id)

    def list_runs(
        self,
        tenant_id: uuid.UUID,
        status: ReconciliationStatus | None = None,
    ) -> list[ReconciliationRun]:
        results = [r for r in self._runs.values() if r.tenant_id == tenant_id]
        if status:
            results = [r for r in results if r.status == status]
        return results

    @property
    def count(self) -> int:
        return len(self._runs)


class InMemoryReconciliationCaseRepository(ReconciliationCaseRepository):
    def __init__(self) -> None:
        self._cases: dict[ReconciliationCaseId, ReconciliationCase] = {}

    def store_case(self, case: ReconciliationCase) -> None:
        self._cases[case.id] = case

    def get_case(self, case_id: ReconciliationCaseId) -> ReconciliationCase | None:
        return self._cases.get(case_id)

    def list_cases(
        self,
        tenant_id: uuid.UUID,
        run_id: ReconciliationRunId | None = None,
        status: ReconciliationCaseStatus | None = None,
    ) -> list[ReconciliationCase]:
        results = [c for c in self._cases.values() if c.tenant_id == tenant_id]
        if run_id:
            results = [c for c in results if c.run_id == run_id]
        if status:
            results = [c for c in results if c.status == status]
        return results

    def list_cases_for_run(self, run_id: ReconciliationRunId) -> list[ReconciliationCase]:
        return [c for c in self._cases.values() if c.run_id == run_id]

    @property
    def count(self) -> int:
        return len(self._cases)
