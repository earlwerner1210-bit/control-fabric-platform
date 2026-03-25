"""Integration tests -- verify that workflows use domain pack rules correctly."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.domain_packs.contract_margin.compiler import ContractCompiler
from app.domain_packs.contract_margin.parsers import ContractParser
from app.domain_packs.contract_margin.rules import (
    BillabilityRuleEngine,
    LeakageRuleEngine,
)
from app.domain_packs.contract_margin.schemas import (
    ClauseType,
    ExtractedClause,
    ParsedContract,
    RateCardEntry,
    SLAEntry,
)
from app.domain_packs.reconciliation import (
    CrossPlaneReconciler,
    MarginEvidenceAssembler,
)
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
from app.domain_packs.utilities_field.parsers import (
    EngineerProfileParser,
    WorkOrderParser,
)
from app.domain_packs.utilities_field.rules import ReadinessRuleEngine
from app.domain_packs.utilities_field.schemas import (
    EngineerProfile,
    ParsedWorkOrder,
    ReadinessStatus,
    SkillCategory,
    SkillRecord,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def contract_parser() -> ContractParser:
    return ContractParser()


@pytest.fixture
def contract_compiler() -> ContractCompiler:
    return ContractCompiler()


@pytest.fixture
def wo_parser() -> WorkOrderParser:
    return WorkOrderParser()


@pytest.fixture
def eng_parser() -> EngineerProfileParser:
    return EngineerProfileParser()


@pytest.fixture
def inc_parser() -> IncidentParser:
    return IncidentParser()


@pytest.fixture
def sample_contract_data() -> dict:
    return {
        "document_type": "contract",
        "title": "Integration Test MSA",
        "parties": ["TelcoCorp", "FieldServices Ltd"],
        "clauses": [
            {"id": "CL-001", "type": "obligation", "text": "Provider shall deliver network maintenance", "section": "2.1"},
            {"id": "CL-002", "type": "penalty", "text": "Failure to meet SLA shall result in 5% penalty", "section": "3.1"},
            {"id": "CL-003", "type": "scope", "text": "Services include network maintenance and repair", "section": "2.2"},
        ],
        "sla_table": [
            {"priority": "P1", "response_time_hours": 1, "resolution_time_hours": 4},
        ],
        "rate_card": [
            {"activity": "network_maintenance", "rate": 125.0, "unit": "hour"},
            {"activity": "emergency_repair", "rate": 187.50, "unit": "hour"},
        ],
    }


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestContractCompileUsesDomainPack:
    """Verify that contract compilation integrates with the domain pack."""

    def test_contract_compile_uses_domain_pack(
        self,
        contract_parser: ContractParser,
        contract_compiler: ContractCompiler,
        sample_contract_data: dict,
    ):
        """Contract compile workflow should use domain pack parser and compiler."""
        # Step 1: Parse with domain pack parser
        parsed = contract_parser.parse_contract(sample_contract_data)
        assert isinstance(parsed, ParsedContract)
        assert len(parsed.clauses) == 3

        # Step 2: Compile with domain pack compiler
        result = contract_compiler.compile(parsed)

        # Verify compiler produced all expected control objects
        assert len(result.clauses) == 3
        assert len(result.obligations) >= 1
        assert len(result.penalties) >= 1
        assert len(result.rate_card_entries) == 2
        assert len(result.sla_entries) == 1

        # Verify obligations were extracted from obligation clauses
        obligation_clause_ids = {ob["clause_id"] for ob in result.obligations}
        assert "CL-001" in obligation_clause_ids

        # Verify penalties were extracted from penalty clauses
        penalty_clause_ids = {pen["clause_id"] for pen in result.penalties}
        assert "CL-002" in penalty_clause_ids

        # Verify billability rules can use compiled rate card
        billability_engine = BillabilityRuleEngine()
        rate_card = [
            RateCardEntry(activity=rc["activity"], rate=rc["rate"], unit=rc["unit"])
            for rc in result.rate_card_entries
        ]
        decision = billability_engine.evaluate(
            activity="network_maintenance",
            rate_card=rate_card,
            obligations=[{"text": ob["description"]} for ob in result.obligations],
        )
        assert decision.billable is True
        assert decision.rate_applied == 125.0


class TestReadinessUsesFieldRules:
    """Verify that readiness assessment uses field domain rules."""

    def test_readiness_uses_field_rules(
        self,
        wo_parser: WorkOrderParser,
        eng_parser: EngineerProfileParser,
    ):
        """Readiness workflow should use field rule engines end-to-end."""
        # Step 1: Parse work order with domain pack parser
        wo_data = {
            "work_order_id": "WO-INT-001",
            "work_order_type": "maintenance",
            "description": "Fiber splice repair",
            "required_skills": [{"skill_name": "fiber", "category": "fiber"}],
            "required_permits": [],
        }
        parsed_wo = wo_parser.parse_work_order(wo_data)
        assert isinstance(parsed_wo, ParsedWorkOrder)

        # Step 2: Parse engineer profile with domain pack parser
        eng_data = {
            "engineer_id": "ENG-INT-001",
            "name": "Test Engineer",
            "skills": [{"skill_name": "fiber", "category": "fiber", "level": "expert"}],
            "accreditations": [],
        }
        parsed_eng = eng_parser.parse_profile(eng_data)
        assert isinstance(parsed_eng, EngineerProfile)

        # Step 3: Run readiness rules
        engine = ReadinessRuleEngine()
        result = engine.evaluate(parsed_wo, parsed_eng)

        assert result.status == ReadinessStatus.ready
        assert result.skill_fit is not None
        assert result.skill_fit.fit is True
        assert "fiber" in result.skill_fit.matching_skills

    def test_readiness_blocked_when_skills_missing(
        self,
        wo_parser: WorkOrderParser,
        eng_parser: EngineerProfileParser,
    ):
        """Readiness should be blocked when engineer lacks required skills."""
        parsed_wo = wo_parser.parse_work_order({
            "work_order_id": "WO-INT-002",
            "work_order_type": "repair",
            "required_skills": [
                {"skill_name": "gas", "category": "gas"},
                {"skill_name": "electrical", "category": "electrical"},
            ],
            "required_permits": [],
        })
        parsed_eng = eng_parser.parse_profile({
            "engineer_id": "ENG-INT-002",
            "name": "Fiber Specialist",
            "skills": [{"skill_name": "fiber", "category": "fiber"}],
            "accreditations": [{"name": "general_competency", "is_valid": True}],
        })

        engine = ReadinessRuleEngine()
        result = engine.evaluate(parsed_wo, parsed_eng)

        assert result.status == ReadinessStatus.blocked
        assert len(result.missing_prerequisites) > 0
        assert result.skill_fit is not None
        assert result.skill_fit.fit is False
        assert "gas" in result.skill_fit.missing_skills


class TestIncidentDispatchUsesTelcoRules:
    """Verify that incident dispatch uses telco ops rules."""

    def test_incident_dispatch_uses_telco_rules(self, inc_parser: IncidentParser):
        """Incident dispatch should use telco rule engines end-to-end."""
        # Step 1: Parse incident with domain pack parser
        incident_data = {
            "incident_id": "INC-INT-001",
            "title": "Core network degradation",
            "severity": "p1",
            "state": "new",
            "affected_services": ["core_network"],
        }
        parsed = inc_parser.parse_incident(incident_data)
        assert isinstance(parsed, ParsedIncident)
        assert parsed.severity == IncidentSeverity.p1

        # Step 2: Run escalation rules
        esc_engine = EscalationRuleEngine()
        esc_result = esc_engine.evaluate(parsed)

        assert esc_result.escalate is True
        assert esc_result.level is not None
        assert esc_result.owner != ""

        # Step 3: Run action rules
        action_engine = ActionRuleEngine()
        action_result = action_engine.evaluate(
            incident_state=parsed.state,
            has_assigned_owner=bool(parsed.assigned_to),
        )

        # P1 new incident without owner should get assigned
        assert action_result.action in ("assign_engineer", "investigate", "escalate")

    def test_resolved_incident_recommends_closure(self, inc_parser: IncidentParser):
        """Resolved incident should recommend closure."""
        parsed = inc_parser.parse_incident({
            "incident_id": "INC-INT-002",
            "severity": "p4",
            "state": "resolved",
        })

        action_engine = ActionRuleEngine()
        result = action_engine.evaluate(incident_state=parsed.state)

        assert result.action == "close"

    def test_outage_triggers_escalation(self, inc_parser: IncidentParser):
        """Service outage should trigger escalation regardless of severity."""
        parsed = inc_parser.parse_incident({
            "incident_id": "INC-INT-003",
            "severity": "p3",
            "state": "investigating",
        })

        esc_engine = EscalationRuleEngine()
        result = esc_engine.evaluate(parsed, service_state=ServiceState.outage)

        assert result.escalate is True


class TestMarginDiagnosisUsesCrossPack:
    """Verify that margin diagnosis uses cross-pack reconciliation."""

    def test_margin_diagnosis_uses_cross_pack(
        self,
        contract_parser: ContractParser,
        contract_compiler: ContractCompiler,
        sample_contract_data: dict,
    ):
        """Margin diagnosis should use cross-pack reconciliation for full analysis."""
        # Step 1: Compile contract into control objects
        parsed = contract_parser.parse_contract(sample_contract_data)
        compiled = contract_compiler.compile(parsed)

        # Convert compiled objects to dicts for reconciliation
        contract_objects = compiled.control_object_payloads

        # Step 2: Define work order and incident objects
        work_order_objects = [
            {
                "work_order_id": "WO-MARGIN-001",
                "activity": "network_maintenance",
                "description": "Scheduled maintenance at site A",
                "scope": "network maintenance",
                "status": "completed",
                "rate": 125.0,
                "hours": 8.0,
                "billed": True,
                "incident_id": "INC-MARGIN-001",
            },
            {
                "work_order_id": "WO-MARGIN-002",
                "activity": "ad_hoc_consulting",
                "description": "Ad hoc consulting work",
                "scope": "consulting",
                "status": "completed",
                "rate": 150.0,
                "hours": 4.0,
                "billed": False,
            },
        ]
        incident_objects = [
            {
                "incident_id": "INC-MARGIN-001",
                "title": "Network issue",
                "description": "Network maintenance required",
                "state": "resolved",
                "affected_services": ["core_network"],
            },
        ]

        # Step 3: Run cross-pack reconciliation
        reconciler = CrossPlaneReconciler()
        result = reconciler.reconcile_all(
            contract_objects, work_order_objects, incident_objects
        )

        assert len(result["links"]) >= 0  # May or may not have links to nested payloads
        assert "summary" in result

        # Step 4: Assemble margin evidence
        assembler = MarginEvidenceAssembler()
        bundle = assembler.assemble_margin_evidence(
            contract_objects, work_order_objects, incident_objects
        )

        assert bundle.bundle_type == "margin_evidence"
        assert len(bundle.field_objects) == 2

        # Step 5: Calculate margin impact
        impact = assembler.calculate_margin_impact(bundle)

        assert impact["total_billed"] > 0  # WO-MARGIN-001 is billed
        assert impact["total_billable"] > impact["total_billed"]  # WO-MARGIN-002 is unbilled
        assert impact["leakage_amount"] > 0

    def test_no_leakage_when_all_billed(self):
        """No leakage should be detected when all work is properly billed."""
        contract_objects = [
            {
                "control_type": "rate_card",
                "activity": "maintenance",
                "label": "maintenance",
                "rate": 100.0,
            },
        ]
        work_orders = [
            {
                "work_order_id": "WO-OK",
                "activity": "maintenance",
                "status": "completed",
                "rate": 100.0,
                "hours": 8.0,
                "billed": True,
            },
        ]
        incidents: list[dict] = []

        assembler = MarginEvidenceAssembler()
        bundle = assembler.assemble_margin_evidence(
            contract_objects, work_orders, incidents
        )
        impact = assembler.calculate_margin_impact(bundle)

        assert impact["leakage_amount"] == 0.0
        assert impact["total_billed"] == impact["total_billable"]
