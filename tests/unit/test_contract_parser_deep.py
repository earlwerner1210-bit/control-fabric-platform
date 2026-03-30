"""Deep tests for ContractParser — Wave 1 extraction methods."""

from __future__ import annotations

import pytest

from app.domain_packs.contract_margin.parsers import ContractParser
from app.domain_packs.contract_margin.schemas import (
    ClauseType,
    ScopeType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def parser() -> ContractParser:
    return ContractParser()


NUMBERED_CONTRACT = """\
Master Services Agreement

1 General Provisions
This agreement governs the relationship between the parties.

1.1 Scope of Services
Provider shall deliver network maintenance and monitoring services.

1.2 Term
The term of this agreement is 36 months from the effective date.

2 Service Levels
The following service levels shall apply to all work performed.

2.1 Response Times
Provider shall respond to P1 incidents within 1 hour.

2.2 Resolution Times
Provider shall resolve P1 incidents within 4 hours.

3 Pricing and Payment
All work shall be invoiced monthly.

3.1 Rate Card
Standard maintenance: $125 per hour.

3.1.1 Overtime Rates
Overtime work shall be charged at 1.5x the standard rate.

3.1.2 Emergency Rates
Emergency callout shall be charged at 2.0x the standard rate.

4 Penalties
Failure to meet SLA response times shall result in a 5% penalty.

4.1 Liquidated Damages
Breach of resolution times shall incur liquidated damages of $5,000 per incident.
"""


ARTICLE_CONTRACT = """\
Article 1: Definitions
The following terms shall have the meanings set forth below.

Article 2: Scope of Work
Provider shall provide field maintenance services.

Article 3: Term and Termination
This agreement shall terminate upon 90 days written notice.
"""


SCHEDULE_CONTRACT = """\
Schedule A: Pricing
All rates are subject to annual review.

Schedule B: Service Levels
Response time targets are defined per priority level.

Schedule C: Scope
In scope services include network maintenance, monitoring, and repair.
"""


SCOPE_TEXT = """\
2.1 Services in scope include: network maintenance, monitoring, repair services.

2.2 Out of scope: capital equipment procurement, third-party software licensing.

2.3 The following services are conditional upon request: extended weekend support, holiday coverage.

3.1 Provider shall provide all scheduled maintenance activities.

3.2 Excluded from this agreement: data center relocation, hardware refresh.

3.3 Subject to customer approval: emergency overtime work, additional crew deployment.
"""


PAYMENT_TEXT_NET30 = """\
5.1 Payment Terms
All invoices shall be paid within 30 days of receipt. Monthly invoicing
shall apply. Currency: GBP. Late payment shall incur interest at 2% per month.
5% retention shall apply to all milestone payments.
"""


PAYMENT_TEXT_NET60 = """\
Payment is due net 60. Invoicing shall be quarterly. Currency: USD.
"""


BILLING_GATE_TEXT = """\
1.1 The provider shall obtain prior approval before commencing any variation work.

1.2 A signed daywork sheet must accompany all time-and-materials claims.

1.3 A completion certificate is required before final invoicing.

1.4 The provider shall submit as-built drawings within 14 days of completion.

1.5 All permits must be closed out before demobilisation.

1.6 A purchase order must be raised for all work exceeding the framework threshold.
"""


SPEN_CONTRACT_TEXT = """\
SPEN Managed Services Agreement

1 Scope of Services
Provider shall provide HV switching, LV fault repair, and cable jointing services.

1.1 In Scope
Services include: HV switching operations, LV fault repair, cable jointing.

1.2 Out of Scope
Excluded: overhead line construction, substation new-build.

2 Service Levels
P1: response 1hr, resolution 4hr
P2: response 2hr, resolution 8hr

3 Pricing
Standard maintenance: $125/hr
Emergency repair: $187.50/hr

4 Payment Terms
All invoices shall be paid within 30 days of receipt. Monthly invoicing.
Currency: GBP. Late payment interest at 1.5% per month.

5 Obligations
5.1 Provider shall maintain all safety certifications.
5.2 Provider must submit monthly progress reports.

6 Penalties
6.1 Failure to meet SLA response times shall result in 5% penalty.
6.2 Breach of safety requirements shall incur liquidated damages.

7 Billing Prerequisites
7.1 Prior approval is required for all variation work.
7.2 Completion certificate must be submitted before final payment.
"""


# ---------------------------------------------------------------------------
# Tests: extract_headings
# ---------------------------------------------------------------------------


class TestExtractHeadingsNumberedSections:
    def test_extracts_top_level_headings(self, parser: ContractParser):
        headings = parser.extract_headings(NUMBERED_CONTRACT)
        top_level = [h for h in headings if h["level"] == 1]
        assert len(top_level) >= 4
        section_numbers = [h["section_number"] for h in top_level]
        assert "1" in section_numbers
        assert "2" in section_numbers
        assert "3" in section_numbers
        assert "4" in section_numbers

    def test_extracts_sub_headings(self, parser: ContractParser):
        headings = parser.extract_headings(NUMBERED_CONTRACT)
        level2 = [h for h in headings if h["level"] == 2]
        assert len(level2) >= 4
        section_numbers = [h["section_number"] for h in level2]
        assert "1.1" in section_numbers
        assert "1.2" in section_numbers

    def test_heading_offsets_are_ordered(self, parser: ContractParser):
        headings = parser.extract_headings(NUMBERED_CONTRACT)
        offsets = [h["offset_start"] for h in headings]
        assert offsets == sorted(offsets)


class TestExtractHeadingsArticleFormat:
    def test_extracts_article_headings(self, parser: ContractParser):
        headings = parser.extract_headings(ARTICLE_CONTRACT)
        article_headings = [h for h in headings if h["level"] == 1]
        assert len(article_headings) >= 3
        texts = [h["heading_text"] for h in article_headings]
        assert any("Definitions" in t for t in texts)
        assert any("Scope" in t or "Work" in t for t in texts)


class TestExtractHeadingsScheduleFormat:
    def test_extracts_schedule_headings(self, parser: ContractParser):
        headings = parser.extract_headings(SCHEDULE_CONTRACT)
        schedule_headings = [h for h in headings if h["level"] == 1]
        assert len(schedule_headings) >= 3
        section_numbers = [h["section_number"] for h in schedule_headings]
        assert "A" in section_numbers or any("A" in s for s in section_numbers)


class TestExtractHeadingsHierarchy:
    def test_hierarchy_levels(self, parser: ContractParser):
        headings = parser.extract_headings(NUMBERED_CONTRACT)
        levels = set(h["level"] for h in headings)
        assert 1 in levels
        assert 2 in levels
        assert 3 in levels

    def test_sub_sub_section_detected(self, parser: ContractParser):
        headings = parser.extract_headings(NUMBERED_CONTRACT)
        level3 = [h for h in headings if h["level"] == 3]
        assert len(level3) >= 2
        section_numbers = [h["section_number"] for h in level3]
        assert "3.1.1" in section_numbers
        assert "3.1.2" in section_numbers


# ---------------------------------------------------------------------------
# Tests: extract_clause_segments
# ---------------------------------------------------------------------------


class TestExtractClauseSegmentsBasic:
    def test_segments_extracted(self, parser: ContractParser):
        segments = parser.extract_clause_segments(NUMBERED_CONTRACT)
        assert len(segments) > 0

    def test_segment_has_required_fields(self, parser: ContractParser):
        segments = parser.extract_clause_segments(NUMBERED_CONTRACT)
        for seg in segments:
            assert seg.id
            assert seg.clause_number
            assert seg.text
            assert seg.clause_type is not None
            assert seg.source_offset_start >= 0
            assert seg.source_offset_end > seg.source_offset_start


class TestExtractClauseSegmentsNested:
    def test_parent_child_relationship(self, parser: ContractParser):
        segments = parser.extract_clause_segments(NUMBERED_CONTRACT)
        seg_map = {s.id: s for s in segments}
        child_segments = [s for s in segments if s.parent_clause_id is not None]
        assert len(child_segments) > 0
        # Every child's parent_clause_id should match a valid segment pattern
        for child in child_segments:
            parent_number = ".".join(child.clause_number.split(".")[:-1])
            assert child.parent_clause_id == f"SEG-{parent_number}"


class TestExtractClauseSegmentsWithOffsets:
    def test_offsets_are_non_overlapping(self, parser: ContractParser):
        segments = parser.extract_clause_segments(NUMBERED_CONTRACT)
        sorted_segs = sorted(segments, key=lambda s: s.source_offset_start)
        for i in range(len(sorted_segs) - 1):
            assert sorted_segs[i].source_offset_end <= sorted_segs[i + 1].source_offset_start


class TestExtractClauseSegmentsTypeInference:
    def test_obligation_type_detected(self, parser: ContractParser):
        segments = parser.extract_clause_segments(NUMBERED_CONTRACT)
        obligation_segs = [s for s in segments if s.clause_type == ClauseType.obligation]
        assert len(obligation_segs) > 0

    def test_penalty_type_detected(self, parser: ContractParser):
        segments = parser.extract_clause_segments(NUMBERED_CONTRACT)
        penalty_segs = [s for s in segments if s.clause_type == ClauseType.penalty]
        assert len(penalty_segs) > 0

    def test_rate_type_detected(self, parser: ContractParser):
        segments = parser.extract_clause_segments(NUMBERED_CONTRACT)
        rate_segs = [s for s in segments if s.clause_type == ClauseType.rate]
        assert len(rate_segs) > 0


# ---------------------------------------------------------------------------
# Tests: extract_scope_boundaries
# ---------------------------------------------------------------------------


class TestExtractScopeBoundariesInScope:
    def test_in_scope_extracted(self, parser: ContractParser):
        boundaries = parser.extract_scope_boundaries(SCOPE_TEXT)
        in_scope = [b for b in boundaries if b.scope_type == ScopeType.in_scope]
        assert len(in_scope) >= 1
        activities = in_scope[0].activities
        assert len(activities) >= 2


class TestExtractScopeBoundariesOutOfScope:
    def test_out_of_scope_extracted(self, parser: ContractParser):
        boundaries = parser.extract_scope_boundaries(SCOPE_TEXT)
        out_scope = [b for b in boundaries if b.scope_type == ScopeType.out_of_scope]
        assert len(out_scope) >= 1


class TestExtractScopeBoundariesConditional:
    def test_conditional_extracted(self, parser: ContractParser):
        boundaries = parser.extract_scope_boundaries(SCOPE_TEXT)
        conditional = [b for b in boundaries if b.scope_type == ScopeType.conditional]
        assert len(conditional) >= 1


class TestExtractScopeBoundariesMixed:
    def test_all_scope_types_present(self, parser: ContractParser):
        boundaries = parser.extract_scope_boundaries(SCOPE_TEXT)
        types = set(b.scope_type for b in boundaries)
        assert ScopeType.in_scope in types
        assert ScopeType.out_of_scope in types
        assert ScopeType.conditional in types


# ---------------------------------------------------------------------------
# Tests: extract_payment_terms
# ---------------------------------------------------------------------------


class TestExtractPaymentTermsNet30:
    def test_payment_period_30(self, parser: ContractParser):
        terms = parser.extract_payment_terms(PAYMENT_TEXT_NET30)
        assert terms["payment_period_days"] == 30

    def test_currency_gbp(self, parser: ContractParser):
        terms = parser.extract_payment_terms(PAYMENT_TEXT_NET30)
        assert terms["currency"] == "GBP"

    def test_invoicing_monthly(self, parser: ContractParser):
        terms = parser.extract_payment_terms(PAYMENT_TEXT_NET30)
        assert terms["invoicing_frequency"] == "monthly"

    def test_late_payment_interest(self, parser: ContractParser):
        terms = parser.extract_payment_terms(PAYMENT_TEXT_NET30)
        assert terms["late_payment_interest"] == 2.0

    def test_retention_percentage(self, parser: ContractParser):
        terms = parser.extract_payment_terms(PAYMENT_TEXT_NET30)
        assert terms["retention_percentage"] == 5.0


class TestExtractPaymentTermsMonthly:
    def test_payment_period_60(self, parser: ContractParser):
        terms = parser.extract_payment_terms(PAYMENT_TEXT_NET60)
        assert terms["payment_period_days"] == 60

    def test_quarterly_invoicing(self, parser: ContractParser):
        terms = parser.extract_payment_terms(PAYMENT_TEXT_NET60)
        assert terms["invoicing_frequency"] == "quarterly"


class TestExtractPaymentTermsWithRetention:
    def test_retention_extracted(self, parser: ContractParser):
        text = "Retention of 10% shall be applied to all interim payments."
        terms = parser.extract_payment_terms(text)
        assert terms["retention_percentage"] == 10.0


# ---------------------------------------------------------------------------
# Tests: full pipeline and edge cases
# ---------------------------------------------------------------------------


class TestParseSpenContractFullPipeline:
    def test_full_parse(self, parser: ContractParser):
        result = parser.parse_contract(SPEN_CONTRACT_TEXT)
        assert result.title
        assert len(result.clauses) > 0
        assert len(result.sla_table) > 0
        assert len(result.rate_card) > 0


class TestParseContractPreservesLineage:
    def test_clause_ids_unique(self, parser: ContractParser):
        result = parser.parse_contract(NUMBERED_CONTRACT)
        ids = [c.id for c in result.clauses]
        assert len(ids) == len(set(ids))


class TestParseEmptyContract:
    def test_empty_string(self, parser: ContractParser):
        result = parser.parse_contract("")
        assert result.document_type == "contract"
        assert len(result.clauses) == 0


class TestParseContractWithDictInput:
    def test_dict_input(self, parser: ContractParser):
        data = {
            "document_type": "work_order",
            "title": "Work Order 001",
            "parties": ["Acme", "Widgets"],
            "clauses": [
                {"id": "WO-1", "type": "obligation", "text": "Deliver goods.", "section": "1.1"},
            ],
            "sla_table": [],
            "rate_card": [],
        }
        result = parser.parse_contract(data)
        assert result.document_type == "work_order"
        assert result.title == "Work Order 001"
        assert len(result.clauses) == 1


class TestExtractBillingGatesFromClauses:
    def test_billing_gates_from_text(self, parser: ContractParser):
        result = parser.parse_contract(BILLING_GATE_TEXT)
        gates = parser.extract_billing_gates(result.clauses)
        gate_types = [g.gate_type.value for g in gates]
        assert "prior_approval" in gate_types
        assert "daywork_sheet_signed" in gate_types
        assert "completion_certificate" in gate_types
        assert "as_built_submitted" in gate_types
        assert "permit_closed_out" in gate_types
        assert "purchase_order" in gate_types
