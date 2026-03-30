"""Contract text parser using regex and structured extraction patterns.

Extracts clauses, SLA tables, rate cards, obligations, penalties, and billable
events from semi-structured contract text. Designed for telecom master services
agreements and associated work/change orders.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date

from ..schemas.contract_schemas import (
    BillableEvent,
    ExtractedClause,
    Obligation,
    ParsedContract,
    PenaltyCondition,
    RateCardEntry,
    SLAEntry,
)
from ..taxonomy.contract_taxonomy import BillableCategory, ClauseType, ContractType

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_SECTION_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:Section|Clause|Article)\s+([\d.]+)[:\s\-]+(.+?)(?=\n\s*(?:Section|Clause|Article)\s+[\d.]|\Z)",
    re.IGNORECASE | re.DOTALL,
)

_SLA_ROW_PATTERN = re.compile(
    r"(?P<metric>[\w\s/]+?)\s*[|,]\s*(?P<target>[\d.]+)\s*(?P<unit>%|ms|hours?|minutes?|seconds?)\s*[|,]\s*(?P<period>monthly|quarterly|annually|weekly|daily)",
    re.IGNORECASE,
)

_RATE_ROW_PATTERN = re.compile(
    r"(?P<role>[\w\s/]+?)\s*[|,]\s*(?P<currency>[A-Z]{3})?\s*(?P<rate>[\d,.]+)\s*(?:/\s*(?P<unit>hour|day|month|unit|item))?",
    re.IGNORECASE,
)

_DATE_PATTERN = re.compile(
    r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})"
    r"|(?P<day2>\d{1,2})\s+(?P<month2>January|February|March|April|May|June|July|August|September|October|November|December)\s+(?P<year2>\d{4})"
    r"|(?P<month3>January|February|March|April|May|June|July|August|September|October|November|December)\s+(?P<day3>\d{1,2}),?\s+(?P<year3>\d{4})",
    re.IGNORECASE,
)

_OBLIGATION_KEYWORDS = re.compile(
    r"\b(shall|must|is required to|is obligated to|will ensure|agrees to|undertakes to)\b",
    re.IGNORECASE,
)

_PENALTY_KEYWORDS = re.compile(
    r"\b(penalty|liquidated damages|service credit|credit note|deduction|withhold|forfeit)\b",
    re.IGNORECASE,
)

_BILLABLE_KEYWORDS = re.compile(
    r"\b(billable|chargeable|invoiceable|compensat|reimburse|fee|charge|payment)\b",
    re.IGNORECASE,
)

_MONTH_MAP = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# Clause-type keyword mapping
_CLAUSE_TYPE_KEYWORDS: dict[ClauseType, re.Pattern[str]] = {
    ClauseType.obligation: re.compile(r"\b(obligation|shall|must|required)\b", re.I),
    ClauseType.penalty: re.compile(
        r"\b(penalty|liquidated damages|service credit|deduction)\b", re.I
    ),
    ClauseType.sla: re.compile(r"\b(service level|SLA|uptime|availability|response time)\b", re.I),
    ClauseType.rate: re.compile(
        r"\b(rate card|pricing|fee schedule|hourly rate|daily rate)\b", re.I
    ),
    ClauseType.scope: re.compile(r"\b(scope of work|deliverable|in scope|out of scope)\b", re.I),
    ClauseType.termination: re.compile(r"\b(terminat|cancel|expir|end of term)\b", re.I),
    ClauseType.liability: re.compile(
        r"\b(liability|liable|cap on liability|limitation of liability)\b", re.I
    ),
    ClauseType.indemnity: re.compile(r"\b(indemnif|hold harmless|defend and indemnify)\b", re.I),
}

# Contract-type keyword mapping
_CONTRACT_TYPE_KEYWORDS: dict[ContractType, re.Pattern[str]] = {
    ContractType.master_services: re.compile(r"\b(master service|MSA|framework agreement)\b", re.I),
    ContractType.work_order: re.compile(r"\b(work order|statement of work|SOW)\b", re.I),
    ContractType.change_order: re.compile(
        r"\b(change order|change request|variation order)\b", re.I
    ),
    ContractType.framework: re.compile(r"\b(framework|blanket agreement|umbrella)\b", re.I),
    ContractType.amendment: re.compile(r"\b(amendment|addendum|supplement)\b", re.I),
}


def _parse_date_match(match: re.Match[str]) -> date | None:
    """Convert a regex date match into a date object."""
    try:
        if match.group("year"):
            return date(
                int(match.group("year")), int(match.group("month")), int(match.group("day"))
            )
        if match.group("year2"):
            month_num = _MONTH_MAP.get(match.group("month2").lower())
            if month_num:
                return date(int(match.group("year2")), month_num, int(match.group("day2")))
        if match.group("year3"):
            month_num = _MONTH_MAP.get(match.group("month3").lower())
            if month_num:
                return date(int(match.group("year3")), month_num, int(match.group("day3")))
    except (ValueError, TypeError):
        pass
    return None


def _extract_first_date(text: str) -> date | None:
    """Extract the first date found in text."""
    match = _DATE_PATTERN.search(text)
    if match:
        return _parse_date_match(match)
    return None


def _extract_all_dates(text: str) -> list[date]:
    """Extract all dates found in text."""
    dates: list[date] = []
    for match in _DATE_PATTERN.finditer(text):
        d = _parse_date_match(match)
        if d:
            dates.append(d)
    return dates


def _classify_clause(text: str) -> ClauseType:
    """Classify a clause by scanning for keyword patterns."""
    best_type = ClauseType.scope  # default
    best_count = 0
    for clause_type, pattern in _CLAUSE_TYPE_KEYWORDS.items():
        count = len(pattern.findall(text))
        if count > best_count:
            best_count = count
            best_type = clause_type
    return best_type


def _detect_contract_type(text: str) -> ContractType:
    """Detect the contract type from the document text."""
    for contract_type, pattern in _CONTRACT_TYPE_KEYWORDS.items():
        if pattern.search(text):
            return contract_type
    return ContractType.master_services


def _extract_parties(text: str) -> list[str]:
    """Extract party names from the contract preamble."""
    parties: list[str] = []
    # Pattern: "between X and Y" or "between X (party A) and Y (party B)"
    between_match = re.search(
        r"between\s+(.+?)\s+(?:and|&)\s+(.+?)(?:\.|,|\n)",
        text[:2000],
        re.IGNORECASE,
    )
    if between_match:
        for group in between_match.groups():
            party = re.sub(r"\s*\(.*?\)\s*", "", group).strip().strip("\"'")
            if party and len(party) < 200:
                parties.append(party)
    return parties


def _extract_amount(text: str) -> float | None:
    """Extract a monetary amount from text."""
    match = re.search(
        r"(?:USD|GBP|EUR|\$|£|€)\s*([\d,]+(?:\.\d{2})?)",
        text,
        re.IGNORECASE,
    )
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


class ContractParser:
    """Parser for extracting structured data from contract documents.

    Uses regex-based extraction to identify sections, clauses, SLA tables,
    rate cards, obligations, penalties, and billable events.
    """

    def parse_contract(self, text: str) -> ParsedContract:
        """Parse a full contract document into a structured representation.

        Args:
            text: Raw contract text.

        Returns:
            A ParsedContract with all extracted components populated.
        """
        contract_type = _detect_contract_type(text)
        parties = _extract_parties(text)
        clauses = self.extract_clauses(text)
        sla_entries = self.extract_sla_table(text)
        rate_card = self.extract_rate_card(text)
        obligations = self.extract_obligations(clauses)
        penalties = self.extract_penalties(clauses)
        billable_events = self.extract_billable_events(clauses)

        dates = _extract_all_dates(text[:3000])
        effective_date = dates[0] if dates else None
        expiry_date = dates[1] if len(dates) > 1 else None

        # Detect billing category from text
        billing_category: BillableCategory | None = None
        billing_patterns: dict[BillableCategory, re.Pattern[str]] = {
            BillableCategory.time_and_materials: re.compile(r"\btime\s+and\s+materials?\b", re.I),
            BillableCategory.fixed_price: re.compile(r"\bfixed\s+price\b", re.I),
            BillableCategory.milestone: re.compile(r"\bmilestone\b", re.I),
            BillableCategory.cost_plus: re.compile(r"\bcost\s*\+\s*|cost\s+plus\b", re.I),
            BillableCategory.retainer: re.compile(r"\bretainer\b", re.I),
        }
        for cat, pattern in billing_patterns.items():
            if pattern.search(text):
                billing_category = cat
                break

        # Extract title from first line or heading
        title_match = re.match(r"^\s*(?:#+\s*)?(.+?)(?:\n|$)", text)
        title = title_match.group(1).strip() if title_match else "Untitled Contract"

        total_value = _extract_amount(text[:5000])

        return ParsedContract(
            contract_type=contract_type,
            title=title,
            parties=parties,
            effective_date=effective_date,
            expiry_date=expiry_date,
            billing_category=billing_category,
            total_value=total_value,
            clauses=clauses,
            sla_entries=sla_entries,
            rate_card=rate_card,
            obligations=obligations,
            penalties=penalties,
            billable_events=billable_events,
            raw_text_hash=hashlib.sha256(text.encode()).hexdigest(),
        )

    def extract_clauses(self, text: str) -> list[ExtractedClause]:
        """Extract individual clauses from contract text.

        Looks for sections delimited by 'Section X.Y', 'Clause X.Y', or
        'Article X.Y' patterns.
        """
        clauses: list[ExtractedClause] = []
        for idx, match in enumerate(_SECTION_PATTERN.finditer(text)):
            section_ref = match.group(1).strip()
            clause_text = match.group(2).strip()
            clause_type = _classify_clause(clause_text)

            dates = _extract_all_dates(clause_text)
            effective = dates[0] if dates else None
            expiry = dates[1] if len(dates) > 1 else None

            clauses.append(
                ExtractedClause(
                    clause_id=f"CL-{idx + 1:04d}",
                    clause_type=clause_type,
                    section_ref=section_ref,
                    text=clause_text,
                    effective_date=effective,
                    expiry_date=expiry,
                )
            )
        return clauses

    def extract_sla_table(self, text: str) -> list[SLAEntry]:
        """Extract SLA metrics from tabular or delimited data in contract text."""
        entries: list[SLAEntry] = []
        for match in _SLA_ROW_PATTERN.finditer(text):
            try:
                entries.append(
                    SLAEntry(
                        metric_name=match.group("metric").strip(),
                        target_value=float(match.group("target")),
                        unit=match.group("unit").strip(),
                        measurement_period=match.group("period").strip().lower(),
                    )
                )
            except (ValueError, TypeError):
                continue
        return entries

    def extract_rate_card(self, text: str) -> list[RateCardEntry]:
        """Extract rate card entries from contract text."""
        entries: list[RateCardEntry] = []
        for match in _RATE_ROW_PATTERN.finditer(text):
            try:
                rate_str = match.group("rate").replace(",", "")
                currency = match.group("currency") or "USD"
                unit = match.group("unit") or "hourly"
                entries.append(
                    RateCardEntry(
                        role_or_item=match.group("role").strip(),
                        rate=float(rate_str),
                        currency=currency.upper(),
                        rate_unit=unit.lower(),
                    )
                )
            except (ValueError, TypeError):
                continue
        return entries

    def extract_obligations(self, clauses: list[ExtractedClause]) -> list[Obligation]:
        """Extract obligations from already-extracted clauses.

        Identifies sentences containing obligation language ('shall', 'must',
        'is required to', etc.) within obligation and scope clauses.
        """
        obligations: list[Obligation] = []
        for clause in clauses:
            if clause.clause_type not in (ClauseType.obligation, ClauseType.scope, ClauseType.sla):
                continue
            sentences = re.split(r"[.;]\s+", clause.text)
            for sentence in sentences:
                if _OBLIGATION_KEYWORDS.search(sentence):
                    # Try to identify the obligated party
                    party_match = re.match(
                        r"^([\w\s]+?)\s+(?:shall|must|is required)", sentence, re.I
                    )
                    party = party_match.group(1).strip() if party_match else "Provider"
                    obligations.append(
                        Obligation(
                            description=sentence.strip(),
                            obligated_party=party,
                            due_date=clause.effective_date,
                            linked_clause_ids=[clause.clause_id],
                        )
                    )
        return obligations

    def extract_penalties(self, clauses: list[ExtractedClause]) -> list[PenaltyCondition]:
        """Extract penalty conditions from clauses identified as penalty or SLA type."""
        penalties: list[PenaltyCondition] = []
        for clause in clauses:
            if not _PENALTY_KEYWORDS.search(clause.text):
                continue
            amount = _extract_amount(clause.text)

            # Look for a formula pattern
            formula_match = re.search(
                r"(\d+%\s+of\s+.+?(?:per\s+\w+)?)",
                clause.text,
                re.I,
            )
            formula = formula_match.group(1).strip() if formula_match else None

            # Look for cap
            cap_match = re.search(
                r"(?:cap|maximum|not\s+exceed)\s*(?:of\s+)?(?:USD|GBP|EUR|\$|£|€)?\s*([\d,]+)",
                clause.text,
                re.I,
            )
            cap = float(cap_match.group(1).replace(",", "")) if cap_match else None

            # Determine penalty type
            penalty_type = "liquidated_damages"
            if re.search(r"service\s+credit", clause.text, re.I):
                penalty_type = "service_credit"
            elif re.search(r"terminat", clause.text, re.I):
                penalty_type = "termination_right"

            penalties.append(
                PenaltyCondition(
                    trigger_condition=clause.text[:300],
                    penalty_type=penalty_type,
                    amount=amount,
                    amount_formula=formula,
                    cap=cap,
                    linked_clause_ids=[clause.clause_id],
                )
            )
        return penalties

    def extract_billable_events(self, clauses: list[ExtractedClause]) -> list[BillableEvent]:
        """Extract billable events from scope and rate clauses."""
        events: list[BillableEvent] = []
        for clause in clauses:
            if not _BILLABLE_KEYWORDS.search(clause.text):
                continue

            # Detect billing category
            category = BillableCategory.time_and_materials
            if re.search(r"fixed\s+price", clause.text, re.I):
                category = BillableCategory.fixed_price
            elif re.search(r"milestone", clause.text, re.I):
                category = BillableCategory.milestone
            elif re.search(r"cost\s*\+|cost\s+plus", clause.text, re.I):
                category = BillableCategory.cost_plus

            requires_approval = bool(re.search(r"(?:prior|pre)[- ]?approv", clause.text, re.I))

            # Extract excluded activities
            excluded: list[str] = []
            excl_match = re.search(r"(?:exclud|not\s+(?:include|cover))[^.]*", clause.text, re.I)
            if excl_match:
                excluded.append(excl_match.group(0).strip())

            events.append(
                BillableEvent(
                    description=clause.text[:500],
                    category=category,
                    requires_approval=requires_approval,
                    excluded_activities=excluded,
                    linked_clause_ids=[clause.clause_id],
                )
            )
        return events
