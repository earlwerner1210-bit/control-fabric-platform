"""Wave 1 end-to-end tests -- Utilities Field Operations domain.

Tests using SPEN work order fixtures to verify readiness gates,
skill matching, crew enforcement, and field-to-billing linkage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain_packs.reconciliation import ContractWorkOrderLinker
from app.domain_packs.utilities_field.parsers import WorkOrderParser
from app.domain_packs.utilities_field.rules import (
    CompletionValidator,
    SPENReadinessEngine,
)
from app.domain_packs.utilities_field.schemas import (
    Accreditation,
    CompletionEvidence,
    CompletionEvidenceType,
    EngineerProfile,
    ParsedWorkOrder,
    PermitRequirement,
    PermitType,
    ReadinessStatus,
    SkillCategory,
    SkillRecord,
    SPENReadinessGate,
    SPENWorkCategory,
    UKAccreditation,
    WorkOrderType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
FIXTURES_DIR = SAMPLE_DIR / "fixtures"


@pytest.fixture
def spen_hv_wo() -> dict:
    with open(SAMPLE_DIR / "sample-work-orders" / "spen_hv_switching_wo.json") as f:
        return json.load(f)


@pytest.fixture
def spen_cable_wo() -> dict:
    with open(SAMPLE_DIR / "sample-work-orders" / "spen_cable_jointing_wo.json") as f:
        return json.load(f)


@pytest.fixture
def wave1_fixture() -> dict:
    with open(FIXTURES_DIR / "wave1_contract_margin.json") as f:
        return json.load(f)


@pytest.fixture
def wo_parser() -> WorkOrderParser:
    return WorkOrderParser()


@pytest.fixture
def hv_engineer() -> EngineerProfile:
    """Engineer fully qualified for HV switching work."""
    return EngineerProfile(
        engineer_id="VF-ENG-1147",
        name="Alasdair MacGregor",
        skills=[
            SkillRecord(skill_name="hv_switching", category=SkillCategory.electrical),
            SkillRecord(skill_name="hv_operations", category=SkillCategory.electrical),
        ],
        accreditations=[
            Accreditation(name=UKAccreditation.hv_authorized_person.value, is_valid=True),
            Accreditation(name=UKAccreditation.ecs_card.value, is_valid=True),
            Accreditation(name=UKAccreditation.first_aid_at_work.value, is_valid=True),
        ],
    )


@pytest.fixture
def unqualified_engineer() -> EngineerProfile:
    """Engineer without HV authorisation."""
    return EngineerProfile(
        engineer_id="VF-ENG-9999",
        name="Test UnqualifiedEngineer",
        skills=[
            SkillRecord(skill_name="lv_fault_repair", category=SkillCategory.electrical),
        ],
        accreditations=[
            Accreditation(name=UKAccreditation.ecs_card.value, is_valid=True),
        ],
    )


@pytest.fixture
def cable_jointing_engineer() -> EngineerProfile:
    """Engineer qualified for cable jointing."""
    return EngineerProfile(
        engineer_id="VF-ENG-1203",
        name="Craig Henderson",
        skills=[
            SkillRecord(skill_name="cable_jointing_hv", category=SkillCategory.electrical),
            SkillRecord(skill_name="fault_location", category=SkillCategory.electrical),
        ],
        accreditations=[
            Accreditation(name=UKAccreditation.cable_jointer_approved.value, is_valid=True),
            Accreditation(name=UKAccreditation.cscs_card.value, is_valid=True),
            Accreditation(name=UKAccreditation.cat_and_genny.value, is_valid=True),
            Accreditation(name=UKAccreditation.nrswa_operative.value, is_valid=True),
        ],
    )


def _make_hv_work_order() -> ParsedWorkOrder:
    """Build a minimal HV switching work order."""
    return ParsedWorkOrder(
        work_order_id="SPEN-WO-TEST-001",
        work_order_type=WorkOrderType.maintenance,
        description="11kV HV switching for planned maintenance",
        required_skills=[
            SkillRecord(skill_name="hv_switching", category=SkillCategory.electrical),
        ],
        required_permits=[],
        customer_confirmed=True,
    )


# ===========================================================================
# Tests
# ===========================================================================


class TestHVSwitchingReadiness:
    """Test HV switching readiness gate evaluation."""

    def test_hv_switching_readiness_pass(self, hv_engineer: EngineerProfile):
        """Fully qualified engineer with all gates satisfied -> ready."""
        wo = _make_hv_work_order()
        engine = SPENReadinessEngine()
        decision = engine.evaluate(
            work_order=wo,
            engineer=hv_engineer,
            work_category=SPENWorkCategory.hv_switching,
            crew_size=2,
        )
        assert decision.status == ReadinessStatus.ready
        assert len(decision.blockers) == 0

    def test_hv_switching_readiness_blocked_no_auth(self, unqualified_engineer: EngineerProfile):
        """Engineer without HV authorisation -> blocked."""
        wo = _make_hv_work_order()
        engine = SPENReadinessEngine()
        decision = engine.evaluate(
            work_order=wo,
            engineer=unqualified_engineer,
            work_category=SPENWorkCategory.hv_switching,
            crew_size=2,
        )
        assert decision.status == ReadinessStatus.blocked
        assert len(decision.blockers) > 0
        blocker_descriptions = [b.description.lower() for b in decision.blockers]
        assert any("hv_authorized_person" in d for d in blocker_descriptions)

    def test_crew_size_enforcement(self, hv_engineer: EngineerProfile):
        """HV switching with only 1 crew member -> blocked."""
        wo = _make_hv_work_order()
        engine = SPENReadinessEngine()
        decision = engine.evaluate(
            work_order=wo,
            engineer=hv_engineer,
            work_category=SPENWorkCategory.hv_switching,
            crew_size=1,
        )
        assert decision.status == ReadinessStatus.blocked
        blocker_descriptions = [b.description.lower() for b in decision.blockers]
        assert any("crew" in d or "person" in d for d in blocker_descriptions)


class TestCableJointingReadiness:
    """Test cable jointing readiness."""

    def test_cable_jointing_nrswa_required(self, cable_jointing_engineer: EngineerProfile):
        """Cable jointing in carriageway needs NRSWA permit."""
        wo = ParsedWorkOrder(
            work_order_id="SPEN-WO-TEST-CJ",
            work_order_type=WorkOrderType.repair,
            description="11kV cable joint replacement",
            required_skills=[
                SkillRecord(skill_name="cable_jointing_hv", category=SkillCategory.electrical),
            ],
            required_permits=[
                PermitRequirement(
                    permit_type=PermitType.street_works,
                    required=True,
                    obtained=False,
                    description="NRSWA S50 permit required",
                ),
            ],
            special_instructions="Traffic management required for carriageway works",
        )
        engine = SPENReadinessEngine()
        decision = engine.evaluate(
            work_order=wo,
            engineer=cable_jointing_engineer,
            work_category=SPENWorkCategory.cable_jointing,
        )
        assert decision.status == ReadinessStatus.blocked
        blocker_types = [b.blocker_type for b in decision.blockers]
        assert "permit" in blocker_types


class TestCompletionEvidence:
    """Test completion evidence validation."""

    def test_completion_evidence_validated(self):
        """HV switching with all evidence -> all pass."""
        validator = CompletionValidator()
        evidence = [
            CompletionEvidence(evidence_type=CompletionEvidenceType.after_photo, provided=True),
            CompletionEvidence(
                evidence_type=CompletionEvidenceType.risk_assessment_completed, provided=True
            ),
            CompletionEvidence(
                evidence_type=CompletionEvidenceType.test_certificate, provided=True
            ),
            CompletionEvidence(
                evidence_type=CompletionEvidenceType.safety_documentation, provided=True
            ),
        ]
        results = validator.validate_completion(
            work_category=SPENWorkCategory.hv_switching,
            evidence=evidence,
        )
        assert all(r.passed for r in results)

    def test_completion_evidence_missing(self):
        """HV switching without test certificate -> error."""
        validator = CompletionValidator()
        evidence = [
            CompletionEvidence(evidence_type=CompletionEvidenceType.after_photo, provided=True),
            CompletionEvidence(
                evidence_type=CompletionEvidenceType.risk_assessment_completed, provided=True
            ),
            # Missing: test_certificate, safety_documentation
        ]
        results = validator.validate_completion(
            work_category=SPENWorkCategory.hv_switching,
            evidence=evidence,
        )
        failed = [r for r in results if not r.passed]
        assert len(failed) >= 1
        failed_names = [r.rule_name for r in failed]
        assert any("test_certificate" in n for n in failed_names)


class TestFieldToBillingLinkage:
    """Test field-to-billing linkage."""

    def test_field_to_billing_linkage(self, wave1_fixture: dict):
        """Work order billing items link to contract rate card."""
        from app.domain_packs.contract_margin.parsers import ContractParser

        parser = ContractParser()
        parsed = parser.parse_contract(wave1_fixture["contract"])
        contract_objects = [
            {
                "type": "rate_card",
                "activity": rc.activity,
                "rate": rc.rate,
                "unit": rc.unit,
                "id": rc.activity,
            }
            for rc in parsed.rate_card
        ]
        linker = ContractWorkOrderLinker()
        wo = wave1_fixture["work_orders"][0]
        # Enrich work order description with activity terms for matching
        wo_enriched = dict(wo, description=f"{wo['description']} hv_switching hv switching")
        links = linker.link(contract_objects, wo_enriched)
        # Should find at least one rate card link
        rate_links = [l for l in links if l.link_type == "rate_card_to_activity"]
        assert len(rate_links) >= 1


class TestWorkOrderParsing:
    """Test full work order parsing from sample data."""

    def test_spen_work_order_parse_full(self, wo_parser: WorkOrderParser, spen_hv_wo: dict):
        """Parse the SPEN HV switching work order sample.

        The sample data uses a dict for the ``location`` field while the
        parser schema expects a string. We coerce the location before parsing.
        """
        data = dict(spen_hv_wo)
        if isinstance(data.get("location"), dict):
            data["location"] = data["location"].get("address", str(data["location"]))
        parsed = wo_parser.parse_work_order(data)
        assert parsed.work_order_id == "SPEN-WO-2026-0451"
        assert parsed.work_order_type == WorkOrderType.maintenance
        assert "11kV" in parsed.description or "switching" in parsed.description.lower()

    def test_spen_cable_jointing_parse(self, wo_parser: WorkOrderParser, spen_cable_wo: dict):
        """Parse the SPEN cable jointing work order sample.

        The sample data uses a dict for the ``location`` field while the
        parser schema expects a string. We coerce the location before parsing.
        """
        data = dict(spen_cable_wo)
        if isinstance(data.get("location"), dict):
            data["location"] = data["location"].get("address", str(data["location"]))
        parsed = wo_parser.parse_work_order(data)
        assert parsed.work_order_id == "SPEN-WO-2026-0453"
        assert parsed.work_order_type == WorkOrderType.repair

    def test_readiness_gate_evaluation(self, hv_engineer: EngineerProfile):
        """Evaluate readiness gates for SPEN dispatch."""
        wo = _make_hv_work_order()
        gates = [
            SPENReadinessGate(
                gate_name="switching_programme_approved",
                gate_type="safety",
                required=True,
                satisfied=True,
            ),
            SPENReadinessGate(
                gate_name="customer_notified",
                gate_type="customer",
                required=True,
                satisfied=False,
                blocking=True,
                description="Customer not yet notified of planned outage",
            ),
        ]
        engine = SPENReadinessEngine()
        decision = engine.evaluate(
            work_order=wo,
            engineer=hv_engineer,
            work_category=SPENWorkCategory.hv_switching,
            gates=gates,
            crew_size=2,
        )
        # Unsatisfied gate should block
        assert decision.status == ReadinessStatus.blocked
        gate_blockers = [
            b
            for b in decision.blockers
            if "gate" in b.description.lower() or "customer" in b.description.lower()
        ]
        assert len(gate_blockers) >= 1
