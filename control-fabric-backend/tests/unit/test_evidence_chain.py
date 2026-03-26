"""Unit tests for EvidenceAssembler and EvidenceChainValidator.

Tests cover evidence assembly from contract, work order, and incident data,
as well as chain validation against the required margin-assurance stages.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain_packs.reconciliation.evidence import (
    EvidenceAssembler,
    EvidenceBundle,
    EvidenceChainValidator,
    EvidenceItem,
)

# ---------------------------------------------------------------------------
# EvidenceAssembler tests
# ---------------------------------------------------------------------------


class TestEvidenceAssembler:
    def _assembler(self) -> EvidenceAssembler:
        return EvidenceAssembler()

    def test_empty_inputs_returns_empty_bundle(self):
        bundle = self._assembler().assemble_margin_evidence([], [], [])
        assert bundle.total_items == 0
        assert bundle.confidence == 0.0
        assert bundle.domains == []

    def test_contract_scope_evidence(self):
        contracts = [{"contract_id": "C1", "description": "Network maintenance"}]
        bundle = self._assembler().assemble_margin_evidence(contracts, [], [])
        assert bundle.total_items >= 1
        assert "contract" in bundle.domains
        types = {it.evidence_type for it in bundle.evidence_items}
        assert "contract_scope" in types

    def test_contract_rate_card_evidence(self):
        contracts = [{"contract_id": "C1", "rate_card_ref": "RC-001"}]
        bundle = self._assembler().assemble_margin_evidence(contracts, [], [])
        types = {it.evidence_type for it in bundle.evidence_items}
        assert "rate_card" in types

    def test_contract_obligation_evidence(self):
        contracts = [{"id": "C1", "obligation_refs": ["OBL-1", "OBL-2"]}]
        bundle = self._assembler().assemble_margin_evidence(contracts, [], [])
        obl_items = [it for it in bundle.evidence_items if it.evidence_type == "obligation"]
        assert len(obl_items) == 2

    def test_contract_penalty_clause_evidence(self):
        contracts = [{"id": "C1", "penalty_clauses": [{"clause_id": "PEN-1"}]}]
        bundle = self._assembler().assemble_margin_evidence(contracts, [], [])
        types = {it.evidence_type for it in bundle.evidence_items}
        assert "penalty_clause" in types

    def test_work_order_dispatch_approval(self):
        work_orders = [{"work_order_id": "WO-1", "status": "approved"}]
        bundle = self._assembler().assemble_margin_evidence([], work_orders, [])
        assert "field" in bundle.domains
        types = {it.evidence_type for it in bundle.evidence_items}
        assert "dispatch_approval" in types

    def test_work_order_completion_evidence_dict(self):
        work_orders = [
            {
                "id": "WO-1",
                "status": "completed",
                "completion_evidence": [
                    {"type": "photo", "ref": "PHOTO-1", "description": "Job complete"}
                ],
            }
        ]
        bundle = self._assembler().assemble_margin_evidence([], work_orders, [])
        exec_items = [it for it in bundle.evidence_items if it.stage == "execution_evidence"]
        assert len(exec_items) >= 1

    def test_work_order_completion_evidence_string(self):
        work_orders = [{"id": "WO-1", "status": "completed", "completion_evidence": ["REF-123"]}]
        bundle = self._assembler().assemble_margin_evidence([], work_orders, [])
        exec_items = [it for it in bundle.evidence_items if it.stage == "execution_evidence"]
        assert len(exec_items) >= 1

    def test_work_order_billing_gates(self):
        work_orders = [
            {
                "id": "WO-1",
                "status": "completed",
                "billing_gates": [{"gate_id": "BG-1", "name": "signoff", "status": "passed"}],
            }
        ]
        bundle = self._assembler().assemble_margin_evidence([], work_orders, [])
        billing_items = [it for it in bundle.evidence_items if it.stage == "billing_evidence"]
        assert len(billing_items) >= 1
        assert billing_items[0].confidence == 1.0

    def test_work_order_billing_gate_not_passed(self):
        work_orders = [
            {
                "id": "WO-1",
                "status": "completed",
                "billing_gates": [{"gate_id": "BG-1", "name": "signoff", "status": "failed"}],
            }
        ]
        bundle = self._assembler().assemble_margin_evidence([], work_orders, [])
        billing_items = [it for it in bundle.evidence_items if it.stage == "billing_evidence"]
        assert billing_items[0].confidence == 0.5

    def test_incident_evidence(self):
        incidents = [{"incident_id": "INC-1", "title": "Outage", "severity": "high"}]
        bundle = self._assembler().assemble_margin_evidence([], [], incidents)
        assert "telco" in bundle.domains
        types = {it.evidence_type for it in bundle.evidence_items}
        assert "incident_record" in types

    def test_incident_resolution_evidence(self):
        incidents = [
            {
                "id": "INC-1",
                "title": "Outage",
                "severity": "high",
                "resolution_summary": "Replaced faulty module",
            }
        ]
        bundle = self._assembler().assemble_margin_evidence([], [], incidents)
        types = {it.evidence_type for it in bundle.evidence_items}
        assert "resolution_record" in types

    def test_incident_root_cause_evidence(self):
        incidents = [
            {"id": "INC-1", "title": "Outage", "severity": "high", "root_cause": "Hardware failure"}
        ]
        bundle = self._assembler().assemble_margin_evidence([], [], incidents)
        types = {it.evidence_type for it in bundle.evidence_items}
        assert "root_cause_analysis" in types

    def test_all_domains_present(self):
        contracts = [{"id": "C1", "description": "scope"}]
        work_orders = [{"id": "WO-1", "status": "approved"}]
        incidents = [{"id": "INC-1", "title": "x", "severity": "low"}]
        bundle = self._assembler().assemble_margin_evidence(contracts, work_orders, incidents)
        assert sorted(bundle.domains) == ["contract", "field", "telco"]

    def test_confidence_computed_correctly(self):
        contracts = [{"id": "C1", "description": "scope"}]
        bundle = self._assembler().assemble_margin_evidence(contracts, [], [])
        # All items have confidence 1.0 by default
        assert bundle.confidence == 1.0

    def test_special_requirements_permit(self):
        work_orders = [
            {
                "id": "WO-1",
                "status": "approved",
                "special_requirements": ["Permit required for road closure"],
            }
        ]
        bundle = self._assembler().assemble_margin_evidence([], work_orders, [])
        types = {it.evidence_type for it in bundle.evidence_items}
        assert "permit_reference" in types


# ---------------------------------------------------------------------------
# EvidenceChainValidator tests
# ---------------------------------------------------------------------------


class TestEvidenceChainValidator:
    def _validator(self) -> EvidenceChainValidator:
        return EvidenceChainValidator()

    def test_full_chain_all_present(self):
        items = [
            EvidenceItem(domain="contract", stage="contract_basis", evidence_type="contract_scope"),
            EvidenceItem(
                domain="field", stage="work_authorization", evidence_type="dispatch_approval"
            ),
            EvidenceItem(
                domain="field", stage="execution_evidence", evidence_type="completion_record"
            ),
            EvidenceItem(domain="field", stage="billing_evidence", evidence_type="billing_gate"),
        ]
        bundle = EvidenceBundle(evidence_items=items, total_items=len(items))
        results = self._validator().validate_chain(bundle)
        assert all(r["present"] for r in results)

    def test_missing_contract_basis(self):
        items = [
            EvidenceItem(
                domain="field", stage="work_authorization", evidence_type="dispatch_approval"
            ),
            EvidenceItem(
                domain="field", stage="execution_evidence", evidence_type="completion_record"
            ),
            EvidenceItem(domain="field", stage="billing_evidence", evidence_type="billing_gate"),
        ]
        bundle = EvidenceBundle(evidence_items=items, total_items=len(items))
        results = self._validator().validate_chain(bundle)
        contract_result = next(r for r in results if r["stage"] == "contract_basis")
        assert contract_result["present"] is False
        assert contract_result["severity"] == "critical"

    def test_missing_billing_evidence(self):
        items = [
            EvidenceItem(domain="contract", stage="contract_basis", evidence_type="contract_scope"),
            EvidenceItem(
                domain="field", stage="work_authorization", evidence_type="dispatch_approval"
            ),
            EvidenceItem(
                domain="field", stage="execution_evidence", evidence_type="completion_record"
            ),
        ]
        bundle = EvidenceBundle(evidence_items=items, total_items=len(items))
        results = self._validator().validate_chain(bundle)
        billing_result = next(r for r in results if r["stage"] == "billing_evidence")
        assert billing_result["present"] is False
        assert billing_result["severity"] == "medium"

    def test_empty_bundle_all_missing(self):
        bundle = EvidenceBundle()
        results = self._validator().validate_chain(bundle)
        assert len(results) == 4
        assert all(r["present"] is False for r in results)

    def test_chain_stages_count(self):
        assert len(EvidenceChainValidator.CHAIN_STAGES) == 4

    def test_incident_record_satisfies_execution(self):
        items = [
            EvidenceItem(
                domain="telco", stage="execution_evidence", evidence_type="incident_record"
            ),
        ]
        bundle = EvidenceBundle(evidence_items=items, total_items=len(items))
        results = self._validator().validate_chain(bundle)
        exec_result = next(r for r in results if r["stage"] == "execution_evidence")
        assert exec_result["present"] is True

    def test_result_messages_present(self):
        bundle = EvidenceBundle()
        results = self._validator().validate_chain(bundle)
        for r in results:
            assert "message" in r
            assert len(r["message"]) > 0
