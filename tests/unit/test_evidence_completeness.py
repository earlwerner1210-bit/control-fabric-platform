"""Tests for the evidence completeness scoring engine."""

from __future__ import annotations

import uuid

import pytest

from app.services.evidence.completeness import (
    CompletenessScore,
    score_evidence_completeness,
)


class TestCompletenessScore:
    def test_empty_evidence(self):
        result = score_evidence_completeness()
        assert result.score == 0.0
        assert result.normalized == 0.0
        assert len(result.missing) > 0

    def test_full_evidence(self):
        items = [
            {"evidence_type": "document", "source_id": str(uuid.uuid4())},
            {"evidence_type": "chunk", "source_id": str(uuid.uuid4())},
            {"evidence_type": "control_object", "source_id": str(uuid.uuid4())},
        ]
        chain_stages = [
            "contract_basis",
            "work_authorization",
            "execution_evidence",
            "billing_evidence",
        ]
        trace = {
            "rules_fired": [{"rule_id": "R001"}],
            "cross_plane_conflicts": [],
        }
        validation_trace = {
            "validators_run": [{"name": "rate_check"}],
        }
        model_lineage = {
            "model_id": "claude-3-opus",
        }

        result = score_evidence_completeness(
            items=items,
            chain_stages=chain_stages,
            trace=trace,
            validation_trace=validation_trace,
            model_lineage=model_lineage,
        )
        assert result.normalized == pytest.approx(1.0)
        assert len(result.missing) == 0

    def test_partial_evidence(self):
        items = [
            {"evidence_type": "document", "source_id": str(uuid.uuid4())},
        ]
        result = score_evidence_completeness(items=items)
        assert 0.0 < result.normalized < 1.0
        assert "source_chunks" in result.missing
        assert "control_objects" in result.missing

    def test_partial_chain_stages(self):
        result = score_evidence_completeness(
            chain_stages=["contract_basis", "work_authorization"],
        )
        assert result.dimensions["chain_stages"] > 0
        assert result.dimensions["chain_stages"] < 1.0

    def test_full_chain_stages(self):
        result = score_evidence_completeness(
            chain_stages=[
                "contract_basis",
                "work_authorization",
                "execution_evidence",
                "billing_evidence",
            ],
        )
        assert result.dimensions["chain_stages"] == pytest.approx(1.0)

    def test_explanation_includes_score(self):
        result = score_evidence_completeness()
        assert "Score:" in result.explanation
        assert "%" in result.explanation

    def test_explanation_lists_present_and_missing(self):
        items = [
            {"evidence_type": "document", "source_id": str(uuid.uuid4())},
        ]
        result = score_evidence_completeness(items=items)
        assert "Present:" in result.explanation
        assert "Missing:" in result.explanation
        assert "source_documents" in result.explanation

    def test_model_lineage_without_model_id(self):
        result = score_evidence_completeness(model_lineage={})
        assert result.dimensions["model_lineage"] == 0.0
        assert "model_lineage" in result.missing

    def test_validation_trace_without_validators(self):
        result = score_evidence_completeness(validation_trace={})
        assert result.dimensions["validation_trace"] == 0.0

    def test_cross_plane_conflicts_present(self):
        trace = {"cross_plane_conflicts": [{"conflict": "rate_mismatch"}]}
        result = score_evidence_completeness(trace=trace)
        assert result.dimensions["cross_plane_conflicts"] > 0

    def test_max_score_is_constant(self):
        r1 = score_evidence_completeness()
        r2 = score_evidence_completeness(
            items=[{"evidence_type": "document", "source_id": str(uuid.uuid4())}]
        )
        assert r1.max_score == r2.max_score
