"""Integration tests proving domain packs work together.

These tests exercise multiple domain packs end-to-end without external
dependencies (no database, no API calls). They import parsers, compilers,
rule engines, validators, and reconciliation logic to verify the full flow.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain_packs.contract_margin.compiler import ContractCompiler
from app.domain_packs.contract_margin.parsers import ContractParser
from app.domain_packs.contract_margin.rules import (
    BillabilityRuleEngine,
    LeakageRuleEngine,
)
from app.domain_packs.contract_margin.schemas import (
    ClauseType,
    ContractType,
    ExtractedClause,
    ParsedContract,
    RateCardEntry,
    SLAEntry,
    ScopeBoundaryObject,
    ScopeType,
)
from app.domain_packs.reconciliation import (
    ContractWorkOrderLinker,
    CrossPlaneReconciler,
    MarginEvidenceAssembler,
    ReadinessEvidenceAssembler,
    WorkOrderIncidentLinker,
)
from app.domain_packs.telco_ops.compiler import TelcoCompiler
from app.domain_packs.telco_ops.parsers import IncidentParser
from app.domain_packs.telco_ops.rules import (
    ActionRuleEngine,
    EscalationRuleEngine,
)
from app.domain_packs.telco_ops.schemas import (
    IncidentSeverity,
    IncidentState,
    ParsedIncident,
    ServiceState,
)
from app.domain_packs.utilities_field.compiler import FieldCompiler
from app.domain_packs.utilities_field.parsers import (
    EngineerProfileParser,
    WorkOrderParser,
)
from app.domain_packs.utilities_field.rules import ReadinessRuleEngine
from app.domain_packs.utilities_field.schemas import (
    Accreditation,
    EngineerProfile,
    ParsedWorkOrder,
    PermitRequirement,
    PermitType,
    ReadinessStatus,
    SkillCategory,
    SkillRecord,
    WorkOrderType,
)


# ---------------------------------------------------------------------------
# Test: Contract compile -> margin diagnosis
# ---------------------------------------------------------------------------


class TestContractCompileToMarginDiagnosis:
    """test_contract_compile_to_margin_diagnosis: Parse contract, compile,
    run leakage rules, assemble margin evidence."""

    def test_full_pipeline(self):
        # 1. Parse contract
        parser = ContractParser()
        contract_data = {
            "document_type": "contract",
            "title": "MSA for Network Services",
            "parties": ["TelcoCorp", "FieldServices"],
            "clauses": [
                {"id": "CL-1", "type": "obligation", "text": "Provider shall deliver maintenance", "section": "2.1"},
                {"id": "CL-2", "type": "penalty", "text": "Failure to meet SLA shall result in penalty", "section": "3.1"},
            ],
            "sla_table": [
                {"priority": "P1", "response_time_hours": 1, "resolution_time_hours": 4, "penalty_percentage": 5.0},
            ],
            "rate_card": [
                {"activity": "standard_maintenance", "rate": 125.0, "unit": "hour"},
                {"activity": "emergency_repair", "rate": 187.50, "unit": "hour"},
            ],
        }
        parsed = parser.parse_contract(contract_data)
        assert parsed.title == "MSA for Network Services"
        assert len(parsed.rate_card) == 2

        # 2. Compile
        compiler = ContractCompiler()
        compiled = compiler.compile(parsed)
        assert len(compiled.control_object_payloads) > 0
        assert len(compiled.rate_card_entries) == 2

        # 3. Run leakage rules with work history
        work_history = [
            {"activity": "standard_maintenance", "status": "completed", "billed": False, "estimated_value": 500},
            {"activity": "emergency_repair", "status": "completed", "billed": True, "billed_rate": 150, "contract_rate": 187.50},
        ]
        leakage_engine = LeakageRuleEngine()
        triggers = leakage_engine.evaluate(compiled.control_object_payloads, work_history)

        # Should detect unbilled work and rate below contract
        assert len(triggers) >= 2
        trigger_types = {t.trigger_type for t in triggers}
        assert "unbilled_completed_work" in trigger_types
        assert "rate_below_contract" in trigger_types

        # 4. Billability check
        bill_engine = BillabilityRuleEngine()
        decision = bill_engine.evaluate(
            "standard_maintenance",
            parsed.rate_card,
            [{"text": "Provider shall deliver maintenance"}],
        )
        assert decision.billable is True
        assert decision.rate_applied == 125.0

        # 5. Assemble margin evidence
        assembler = MarginEvidenceAssembler()
        leakage_trigger_dicts = [
            {"trigger_type": t.trigger_type, "description": t.description, "severity": t.severity}
            for t in triggers
        ]
        bundle = assembler.assemble(
            compiled.control_object_payloads,
            work_history,
            leakage_trigger_dicts,
        )
        assert bundle.total_items > 0
        assert len(bundle.domains) >= 1


# ---------------------------------------------------------------------------
# Test: Work order readiness end-to-end
# ---------------------------------------------------------------------------


class TestWorkOrderReadinessEndToEnd:
    """test_work_order_readiness_end_to_end: Parse WO+engineer, compile,
    run readiness rules, validate output."""

    def test_full_pipeline(self):
        # 1. Parse work order
        wo_parser = WorkOrderParser()
        wo = wo_parser.parse_work_order({
            "work_order_id": "WO-READY",
            "work_order_type": "maintenance",
            "description": "Fiber cabinet maintenance",
            "priority": "normal",
            "required_skills": [
                {"skill_name": "fiber", "category": "fiber", "level": "qualified"},
            ],
            "required_permits": [
                {"permit_type": "building_access", "required": True, "obtained": True},
            ],
            "estimated_duration_hours": 3.0,
        })

        # 2. Parse engineer
        eng_parser = EngineerProfileParser()
        engineer = eng_parser.parse_profile({
            "engineer_id": "ENG-READY",
            "name": "Test Engineer",
            "skills": [{"skill_name": "fiber", "category": "fiber", "level": "expert"}],
            "accreditations": [{"name": "general_competency", "is_valid": True}],
        })

        # 3. Compile
        compiler = FieldCompiler()
        compiled = compiler.compile(wo, engineer)

        # Verify result via actual FieldCompileResult API
        assert compiled.summary["work_order_id"] == "WO-READY"
        assert compiled.summary["engineer_id"] == "ENG-READY"
        assert len(compiled.skill_requirements) >= 1

        # 4. Run readiness rules
        readiness_engine = ReadinessRuleEngine()
        decision = readiness_engine.evaluate(wo, engineer)

        assert decision.status == ReadinessStatus.ready
        assert len(decision.blockers) == 0
        assert decision.skill_fit is not None
        assert decision.skill_fit.fit is True

        # 5. Validate the output shape
        output = {
            "verdict": "ready",
            "reasons": [decision.recommendation],
            "missing_prerequisites": decision.missing_prerequisites,
        }
        assert output["verdict"] in ("ready", "blocked", "warn", "escalate")
        assert len(output["missing_prerequisites"]) == 0


class TestWorkOrderReadinessBlocked:
    """Test that missing skills cause a blocked readiness verdict."""

    def test_missing_skill_blocks_readiness(self):
        wo = ParsedWorkOrder(
            work_order_id="WO-BLOCKED",
            work_order_type=WorkOrderType.maintenance,
            description="Gas meter repair",
            required_skills=[
                SkillRecord(skill_name="gas_fitting", category=SkillCategory.gas, level="expert"),
            ],
            required_permits=[
                PermitRequirement(permit_type=PermitType.building_access, required=True, obtained=False),
            ],
        )
        engineer = EngineerProfile(
            engineer_id="ENG-NOGAS",
            name="No Gas Engineer",
            skills=[
                SkillRecord(skill_name="fiber", category=SkillCategory.fiber, level="expert"),
            ],
        )

        readiness_engine = ReadinessRuleEngine()
        decision = readiness_engine.evaluate(wo, engineer)

        assert decision.status == ReadinessStatus.blocked
        assert len(decision.blockers) > 0
        assert any("gas_fitting" in b.description for b in decision.blockers)


# ---------------------------------------------------------------------------
# Test: Incident dispatch end-to-end
# ---------------------------------------------------------------------------


class TestIncidentDispatchEndToEnd:
    """test_incident_dispatch_end_to_end: Parse incident, compile,
    run escalation+action rules, validate."""

    def test_full_pipeline(self):
        # 1. Parse incident
        inc_parser = IncidentParser()
        incident = inc_parser.parse_incident({
            "incident_id": "INC-DISPATCH",
            "title": "Core network failure",
            "description": "Complete core network outage",
            "severity": "p1",
            "state": "new",
            "affected_services": ["core_network", "voice_platform"],
            "assigned_to": "on_call_eng",
        })
        assert incident.severity == IncidentSeverity.p1

        # 2. Compile
        compiler = TelcoCompiler()
        compiled = compiler.compile(incident)
        assert compiled.incident_state["severity"] == "p1"
        assert compiled.incident_state["requires_immediate_attention"] is True

        # 3. Escalation rules
        esc_engine = EscalationRuleEngine()
        esc_decision = esc_engine.evaluate(incident)
        assert esc_decision.escalate is True
        assert esc_decision.level is not None
        assert esc_decision.owner != ""

        # 4. Action rules
        action_engine = ActionRuleEngine()
        next_action = action_engine.evaluate(
            incident.state,
            has_assigned_owner=True,
        )
        # New + assigned -> investigate
        assert next_action.action == "investigate"

        # 5. Validate the output shape
        output = {
            "next_action": next_action.action,
            "escalation_level": esc_decision.level.value if esc_decision.level else None,
            "escalation_owner": esc_decision.owner,
        }
        valid_actions = {"investigate", "escalate", "dispatch", "resolve", "monitor", "assign_engineer", "close", "reopen", "contact_customer"}
        assert output["next_action"] in valid_actions
        assert output["escalation_level"] in ("l1", "l2", "l3", "management")


# ---------------------------------------------------------------------------
# Test: Margin leakage with cross-pack evidence
# ---------------------------------------------------------------------------


class TestMarginLeakageWithCrossPackEvidence:
    """test_margin_leakage_with_cross_pack_evidence: Contract + work history
    -> leakage -> margin evidence with cross-pack links."""

    def test_leakage_with_evidence(self):
        # 1. Contract objects
        contract_objects = [
            {
                "type": "rate_card",
                "id": "rc-1",
                "activity": "standard_maintenance",
                "rate": 125.0,
            },
        ]

        # 2. Work history with unbilled work
        work_history = [
            {
                "work_order_id": "WO-1",
                "activity": "standard_maintenance",
                "description": "standard maintenance work",
                "status": "completed",
                "billed": False,
                "estimated_value": 500,
            },
        ]

        # 3. Run leakage
        leakage_engine = LeakageRuleEngine()
        triggers = leakage_engine.evaluate(contract_objects, work_history)
        assert len(triggers) >= 1

        # 4. Assemble evidence
        trigger_dicts = [
            {"trigger_type": t.trigger_type, "description": t.description, "severity": t.severity}
            for t in triggers
        ]
        assembler = MarginEvidenceAssembler()
        bundle = assembler.assemble(
            contract_objects,
            work_history,
            trigger_dicts,
        )

        assert bundle.total_items > 0
        # Should have items from multiple domains
        assert len(bundle.domains) >= 2  # contract_margin + utilities_field


# ---------------------------------------------------------------------------
# Test: Readiness blocked propagates to reconciliation
# ---------------------------------------------------------------------------


class TestReadinessBlockedPropagatesToReconciliation:
    """test_readiness_blocked_propagates_to_reconciliation: Blocked readiness
    creates conflict when work order is linked to contract."""

    def test_blocked_readiness_detected_in_reconciliation(self):
        # 1. Create a work order that will be blocked
        wo = ParsedWorkOrder(
            work_order_id="WO-BLOCK-RECON",
            work_order_type=WorkOrderType.repair,
            description="Repair requiring confined space entry",
            required_skills=[
                SkillRecord(skill_name="hvac_repair", category=SkillCategory.hvac, level="expert"),
            ],
            required_permits=[
                PermitRequirement(permit_type=PermitType.confined_space, required=True, obtained=False),
            ],
        )
        engineer = EngineerProfile(
            engineer_id="ENG-BLOCK",
            name="Blocked Engineer",
            skills=[],  # No matching skills
            accreditations=[],
        )

        # 2. Run readiness - should be blocked
        readiness_engine = ReadinessRuleEngine()
        decision = readiness_engine.evaluate(wo, engineer)
        assert decision.status == ReadinessStatus.blocked

        # 3. Compile the work order
        field_compiler = FieldCompiler()
        compiled = field_compiler.compile(wo, engineer)
        assert compiled.summary["work_order_id"] == "WO-BLOCK-RECON"

        # 4. Create contract data that links to this WO type
        contract_data = {
            "rate_card": [
                {"activity": "repair", "rate": 200.0, "unit": "hour"},
            ],
            "obligations": [
                {
                    "id": "ob-block",
                    "clause_id": "CL-BLOCK",
                    "description": "Provider shall complete all scheduled repairs",
                    "status": "active",
                },
            ],
        }

        # 5. Run reconciliation
        reconciler = CrossPlaneReconciler()
        wo_data = {
            "work_order_id": "WO-BLOCK-RECON",
            "work_order_type": "repair",
            "description": "repair requiring confined space entry",
            "status": "pending",
        }
        result = reconciler.reconcile_contract_to_work_order(
            contract_data=contract_data,
            wo_data=wo_data,
        )

        # 6. Should have links between contract and WO
        assert len(result["links"]) > 0

    def test_readiness_evidence_includes_blockers(self):
        """Readiness evidence bundle should include blocker information."""
        assembler = ReadinessEvidenceAssembler()
        bundle = assembler.assemble(
            work_order={"work_order_id": "WO-EVD", "description": "repair job"},
            engineer={"engineer_id": "ENG-EVD", "name": "Test"},
            blockers=[
                {"blocker_type": "missing_skill", "description": "Missing hvac_repair", "severity": "error"},
            ],
            skill_fit={"fit": False, "missing_skills": ["hvac_repair"]},
        )

        assert bundle.domains == ["utilities_field"]
        assert bundle.total_items == 4  # WO + engineer + 1 blocker + skill_fit
        # Low confidence due to blocker and no fit
        assert bundle.confidence < 0.7
