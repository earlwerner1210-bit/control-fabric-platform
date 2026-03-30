"""Evidence review and traceability service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.evidence import (
    EvidenceBundleCreate,
    EvidenceBundleResponse,
    EvidenceItem,
    EvidenceObjectReference,
    EvidenceTrace,
    ModelLineageTrace,
    ValidationTrace,
)


class EvidenceService:
    """Manages evidence bundles and traceability for pilot cases."""

    def __init__(self) -> None:
        self._bundles: dict[uuid.UUID, dict[str, Any]] = {}
        self._traces: dict[uuid.UUID, dict[str, Any]] = {}
        self._validation_traces: dict[uuid.UUID, dict[str, Any]] = {}
        self._model_lineage: dict[uuid.UUID, dict[str, Any]] = {}

    def create_bundle(self, data: EvidenceBundleCreate) -> EvidenceBundleResponse:
        bundle_id = uuid.uuid4()
        now = datetime.now(UTC)

        bundle = {
            "id": bundle_id,
            "pilot_case_id": data.pilot_case_id,
            "items": [item.model_dump() for item in data.items],
            "chain_stages": data.chain_stages,
            "completeness_score": data.completeness_score,
            "metadata": data.metadata,
            "created_at": now,
        }
        self._bundles[data.pilot_case_id] = bundle
        return EvidenceBundleResponse(**bundle)

    def get_bundle(self, pilot_case_id: uuid.UUID) -> EvidenceBundleResponse | None:
        bundle = self._bundles.get(pilot_case_id)
        if bundle is None:
            return None
        return EvidenceBundleResponse(**bundle)

    def store_trace(
        self,
        pilot_case_id: uuid.UUID,
        documents: list[dict[str, Any]] | None = None,
        chunks: list[dict[str, Any]] | None = None,
        control_objects: list[dict[str, Any]] | None = None,
        rules_fired: list[dict[str, Any]] | None = None,
        cross_plane_conflicts: list[dict[str, Any]] | None = None,
    ) -> EvidenceTrace:
        trace = {
            "pilot_case_id": pilot_case_id,
            "documents_used": [EvidenceObjectReference(**d) for d in (documents or [])],
            "chunks_used": [EvidenceObjectReference(**c) for c in (chunks or [])],
            "control_objects": [EvidenceObjectReference(**co) for co in (control_objects or [])],
            "rules_fired": rules_fired or [],
            "cross_plane_conflicts": cross_plane_conflicts or [],
        }
        self._traces[pilot_case_id] = trace
        return EvidenceTrace(**trace)

    def get_trace(self, pilot_case_id: uuid.UUID) -> EvidenceTrace | None:
        trace = self._traces.get(pilot_case_id)
        if trace is None:
            return None
        return EvidenceTrace(**trace)

    def store_validation_trace(
        self,
        pilot_case_id: uuid.UUID,
        validators_run: list[dict[str, Any]],
        passed: list[str],
        failed: list[str],
        warnings: list[str],
        overall_status: str,
    ) -> ValidationTrace:
        trace = {
            "pilot_case_id": pilot_case_id,
            "validators_run": validators_run,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "overall_status": overall_status,
        }
        self._validation_traces[pilot_case_id] = trace
        return ValidationTrace(**trace)

    def get_validation_trace(self, pilot_case_id: uuid.UUID) -> ValidationTrace | None:
        trace = self._validation_traces.get(pilot_case_id)
        if trace is None:
            return None
        return ValidationTrace(**trace)

    def store_model_lineage(
        self,
        pilot_case_id: uuid.UUID,
        model_id: str | None = None,
        model_version: str | None = None,
        prompt_template_id: uuid.UUID | None = None,
        prompt_template_version: str | None = None,
        inference_provider: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        latency_ms: float | None = None,
        raw_output_summary: dict[str, Any] | None = None,
    ) -> ModelLineageTrace:
        lineage = {
            "pilot_case_id": pilot_case_id,
            "model_id": model_id,
            "model_version": model_version,
            "prompt_template_id": prompt_template_id,
            "prompt_template_version": prompt_template_version,
            "inference_provider": inference_provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "raw_output_summary": raw_output_summary or {},
        }
        self._model_lineage[pilot_case_id] = lineage
        return ModelLineageTrace(**lineage)

    def get_model_lineage(self, pilot_case_id: uuid.UUID) -> ModelLineageTrace | None:
        lineage = self._model_lineage.get(pilot_case_id)
        if lineage is None:
            return None
        return ModelLineageTrace(**lineage)
