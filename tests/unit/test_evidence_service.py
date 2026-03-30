"""Tests for the evidence service."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.evidence import (
    EvidenceBundleCreate,
    EvidenceItem,
)
from app.services.evidence import EvidenceService


@pytest.fixture
def svc() -> EvidenceService:
    return EvidenceService()


CASE_ID = uuid.uuid4()


class TestCreateBundle:
    def test_create_bundle(self, svc: EvidenceService):
        data = EvidenceBundleCreate(
            pilot_case_id=CASE_ID,
            items=[
                EvidenceItem(
                    evidence_type="document", source_id=uuid.uuid4(), source_label="MSA Contract"
                ),
                EvidenceItem(evidence_type="chunk", source_id=uuid.uuid4(), confidence=0.95),
            ],
            chain_stages=["contract_basis", "work_authorization"],
            completeness_score=0.85,
        )
        bundle = svc.create_bundle(data)
        assert bundle.pilot_case_id == CASE_ID
        assert len(bundle.items) == 2
        assert bundle.completeness_score == 0.85
        assert bundle.chain_stages == ["contract_basis", "work_authorization"]

    def test_create_bundle_empty_items(self, svc: EvidenceService):
        data = EvidenceBundleCreate(pilot_case_id=CASE_ID)
        bundle = svc.create_bundle(data)
        assert bundle.items == []
        assert bundle.completeness_score == 0.0

    def test_create_bundle_with_metadata(self, svc: EvidenceService):
        data = EvidenceBundleCreate(
            pilot_case_id=CASE_ID,
            metadata={"source_system": "contract_store"},
        )
        bundle = svc.create_bundle(data)
        assert bundle.metadata["source_system"] == "contract_store"


class TestGetBundle:
    def test_get_existing(self, svc: EvidenceService):
        data = EvidenceBundleCreate(pilot_case_id=CASE_ID, completeness_score=0.9)
        svc.create_bundle(data)
        bundle = svc.get_bundle(CASE_ID)
        assert bundle is not None
        assert bundle.completeness_score == 0.9

    def test_get_missing(self, svc: EvidenceService):
        assert svc.get_bundle(uuid.uuid4()) is None


class TestEvidenceTrace:
    def test_store_and_get_trace(self, svc: EvidenceService):
        doc_id = uuid.uuid4()
        trace = svc.store_trace(
            CASE_ID,
            documents=[{"object_type": "contract", "object_id": str(doc_id), "label": "MSA"}],
            chunks=[{"object_type": "chunk", "object_id": str(uuid.uuid4())}],
            rules_fired=[{"rule_id": "R001", "result": "pass"}],
        )
        assert trace.pilot_case_id == CASE_ID
        assert len(trace.documents_used) == 1
        assert len(trace.chunks_used) == 1
        assert len(trace.rules_fired) == 1

    def test_get_missing_trace(self, svc: EvidenceService):
        assert svc.get_trace(uuid.uuid4()) is None

    def test_trace_with_conflicts(self, svc: EvidenceService):
        trace = svc.store_trace(
            CASE_ID,
            cross_plane_conflicts=[
                {"conflict": "rate_mismatch", "planes": ["contract", "billing"]}
            ],
        )
        assert len(trace.cross_plane_conflicts) == 1


class TestValidationTrace:
    def test_store_and_get_validation_trace(self, svc: EvidenceService):
        trace = svc.store_validation_trace(
            CASE_ID,
            validators_run=[{"name": "rate_check", "version": "1.0"}],
            passed=["rate_check", "scope_check"],
            failed=["completeness_check"],
            warnings=["date_proximity"],
            overall_status="failed",
        )
        assert trace.pilot_case_id == CASE_ID
        assert trace.overall_status == "failed"
        assert len(trace.passed) == 2
        assert len(trace.failed) == 1
        assert len(trace.warnings) == 1

    def test_get_missing_validation_trace(self, svc: EvidenceService):
        assert svc.get_validation_trace(uuid.uuid4()) is None


class TestModelLineage:
    def test_store_and_get_lineage(self, svc: EvidenceService):
        lineage = svc.store_model_lineage(
            CASE_ID,
            model_id="claude-3-opus",
            model_version="20240229",
            inference_provider="anthropic",
            input_tokens=1500,
            output_tokens=800,
            latency_ms=2300.5,
            raw_output_summary={"verdict": "billable"},
        )
        assert lineage.model_id == "claude-3-opus"
        assert lineage.input_tokens == 1500
        assert lineage.latency_ms == 2300.5

    def test_get_missing_lineage(self, svc: EvidenceService):
        assert svc.get_model_lineage(uuid.uuid4()) is None

    def test_lineage_minimal(self, svc: EvidenceService):
        lineage = svc.store_model_lineage(CASE_ID)
        assert lineage.model_id is None
        assert lineage.raw_output_summary == {}
