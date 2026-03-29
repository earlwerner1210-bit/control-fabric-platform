"""Wave 3 validation repositories — run and report persistence abstractions."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.core.validation.domain_types import (
    ValidationReport,
    ValidationRun,
    ValidationRunId,
    W3ValidationStatus,
)


class ValidationRunRepository(ABC):
    @abstractmethod
    def store_run(self, run: ValidationRun) -> None: ...

    @abstractmethod
    def get_run(self, run_id: ValidationRunId) -> ValidationRun | None: ...

    @abstractmethod
    def list_runs(
        self, tenant_id: uuid.UUID, status: W3ValidationStatus | None = None
    ) -> list[ValidationRun]: ...


class ValidationReportRepository(ABC):
    @abstractmethod
    def store_report(self, report: ValidationReport) -> None: ...

    @abstractmethod
    def get_report(self, report_id: uuid.UUID) -> ValidationReport | None: ...

    @abstractmethod
    def get_report_for_run(self, run_id: ValidationRunId) -> ValidationReport | None: ...


class InMemoryValidationRunRepository(ValidationRunRepository):
    def __init__(self) -> None:
        self._runs: dict[ValidationRunId, ValidationRun] = {}

    def store_run(self, run: ValidationRun) -> None:
        self._runs[run.id] = run

    def get_run(self, run_id: ValidationRunId) -> ValidationRun | None:
        return self._runs.get(run_id)

    def list_runs(
        self, tenant_id: uuid.UUID, status: W3ValidationStatus | None = None
    ) -> list[ValidationRun]:
        results = [r for r in self._runs.values() if r.tenant_id == tenant_id]
        if status:
            results = [r for r in results if r.status == status]
        return results

    @property
    def count(self) -> int:
        return len(self._runs)


class InMemoryValidationReportRepository(ValidationReportRepository):
    def __init__(self) -> None:
        self._reports: dict[uuid.UUID, ValidationReport] = {}

    def store_report(self, report: ValidationReport) -> None:
        self._reports[report.id] = report

    def get_report(self, report_id: uuid.UUID) -> ValidationReport | None:
        return self._reports.get(report_id)

    def get_report_for_run(self, run_id: ValidationRunId) -> ValidationReport | None:
        for report in self._reports.values():
            if report.run_id == run_id:
                return report
        return None

    @property
    def count(self) -> int:
        return len(self._reports)
