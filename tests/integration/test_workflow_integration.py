"""Integration tests -- verify that workflows use domain pack rules correctly."""

from __future__ import annotations

import pytest

from app.domain_packs.contract_margin.compiler import ContractCompiler
from app.domain_packs.contract_margin.parsers import ContractParser
from app.domain_packs.contract_margin.rules import (
    BillabilityRuleEngine,
)
from app.domain_packs.contract_margin.schemas import (
    ParsedContract,
    RateCardEntry,
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
            {
                "id": "CL-001",
                "type": "obligation",
                "text": "Provider shall deliver network maintenance",
                "section": "2.1",
            },
            {
                "id": "CL-002",
                "type": "penalty",
                "text": "Failure to meet SLA shall result in 5% penalty",
                "section": "3.1",
            },
            {
                "id": "CL-003",
                "type": "scope",
                "text": "Services include network maintenance and repair",
                "section": "2.2",
            },
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
        parsed_wo = wo_parser.parse_work_order(
            {
                "work_order_id": "WO-INT-002",
                "work_order_type": "repair",
                "required_skills": [
                    {"skill_name": "gas", "category": "gas"},
                    {"skill_name": "electrical", "category": "electrical"},
                ],
                "required_permits": [],
            }
        )
        parsed_eng = eng_parser.parse_profile(
            {
                "engineer_id": "ENG-INT-002",
                "name": "Fiber Specialist",
                "skills": [{"skill_name": "fiber", "category": "fiber"}],
                "accreditations": [{"name": "general_competency", "is_valid": True}],
            }
        )

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
        parsed = inc_parser.parse_incident(
            {
                "incident_id": "INC-INT-002",
                "severity": "p4",
                "state": "resolved",
            }
        )

        action_engine = ActionRuleEngine()
        result = action_engine.evaluate(incident_state=parsed.state)

        assert result.action == "close"

    def test_outage_triggers_escalation(self, inc_parser: IncidentParser):
        """Service outage should trigger escalation regardless of severity."""
        parsed = inc_parser.parse_incident(
            {
                "incident_id": "INC-INT-003",
                "severity": "p3",
                "state": "investigating",
            }
        )

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

        # Step 2: Build contract data dict for reconciliation
        contract_data = {
            "rate_card": [
                {"activity": rc["activity"], "rate": rc["rate"], "unit": rc["unit"]}
                for rc in compiled.rate_card_entries
            ],
            "obligations": [
                {
                    "clause_id": ob["clause_id"],
                    "description": ob["description"],
                    "status": ob["status"],
                    "due_type": ob["due_type"],
                }
                for ob in compiled.obligations
            ],
            "scope_boundaries": [],
        }

        # Step 3: Define work order data
        wo_data = {
            "work_order_id": "WO-MARGIN-001",
            "description": "Scheduled network maintenance at site A",
            "rate": 125.0,
            "priority": "normal",
        }

        # Step 4: Run cross-pack reconciliation
        reconciler = CrossPlaneReconciler()
        result = reconciler.reconcile_contract_to_work_order(contract_data, wo_data)

        assert "links" in result
        assert "conflicts" in result
        assert "evidence" in result

        # Evidence should contain items from contract and field domains
        evidence = result["evidence"]
        assert evidence["total_items"] > 0

    def test_margin_evidence_assembly(self):
        """MarginEvidenceAssembler should assemble proper evidence bundle."""
        assembler = MarginEvidenceAssembler()

        contract_objects = [
            {
                "type": "rate_card",
                "activity": "maintenance",
                "rate": 100.0,
                "description": "maintenance",
            },
        ]
        work_history = [
            {"work_order_id": "WO-001", "description": "Maintenance work", "billed": True},
            {"work_order_id": "WO-002", "description": "Extra work", "billed": False},
        ]
        leakage_triggers = [
            {
                "trigger_type": "unbilled_work",
                "description": "WO-002 not billed",
                "severity": "error",
            },
        ]

        bundle = assembler.assemble(contract_objects, work_history, leakage_triggers)

        assert bundle.total_items == 4  # 1 contract + 2 WOs + 1 trigger
        assert bundle.confidence > 0
        assert "contract_margin" in bundle.domains
        assert "utilities_field" in bundle.domains

    def test_no_leakage_with_clean_data(self):
        """No leakage triggers should produce lower confidence."""
        assembler = MarginEvidenceAssembler()

        bundle = assembler.assemble(
            contract_objects=[{"type": "rate_card", "activity": "maintenance", "rate": 100.0}],
            work_history=[
                {"work_order_id": "WO-CLEAN", "description": "Clean work", "billed": True}
            ],
            leakage_triggers=[],
        )

        assert bundle.total_items == 2
        # Without leakage triggers, confidence should be lower
        assert bundle.confidence < 1.0
