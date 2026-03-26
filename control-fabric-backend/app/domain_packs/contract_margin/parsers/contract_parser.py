"""
Contract document parser for the contract margin domain pack.

Handles both structured dict payloads (from upstream document processors)
and raw text input, extracting clauses, SLA tables, rate cards, scope
boundaries, obligations, penalties, and billable events.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any, Optional, Sequence, Union

from app.domain_packs.contract_margin.schemas.contract import (
    BillableCategory,
    BillableEvent,
    ClauseType,
    ContractType,
    ExtractedClause,
    Obligation,
    ParsedContract,
    PenaltyCondition,
    PriorityLevel,
    RateCardEntry,
    ScopeBoundary,
    ScopeType,
    SLAEntry,
)

# ---------------------------------------------------------------------------
# Keyword maps for clause classification
# ---------------------------------------------------------------------------

_CLAUSE_KEYWORD_MAP: dict[ClauseType, list[str]] = {
    ClauseType.obligation: ["shall", "must", "required to", "obligated", "responsible for"],
    ClauseType.sla: ["service level", "sla", "response time", "resolution time", "availability"],
    ClauseType.penalty: ["penalty", "liquidated damages", "service credit", "deduction", "abatement"],
    ClauseType.rate: ["rate", "price", "charge", "fee", "tariff", "cost per"],
    ClauseType.scope: ["scope", "in scope", "out of scope", "included", "excluded"],
    ClauseType.termination: ["termination", "terminate", "exit", "expiry", "cessation"],
    ClauseType.liability: ["liability", "indemnity", "indemnification", "limitation of liability"],
    ClauseType.billing: ["invoice", "billing", "payment", "remittance", "purchase order"],
    ClauseType.re_attendance: ["re-attendance", "reattendance", "repeat visit", "rework", "revisit"],
    ClauseType.evidence: ["evidence", "proof", "documentation", "daywork sheet", "photograph"],
    ClauseType.service_credit: ["service credit", "credit note", "rebate"],
    ClauseType.safety: ["safety", "health and safety", "risk assessment", "method statement"],
    ClauseType.nrswa: ["nrswa", "street works", "permit", "section 50", "notice"],
}

_PRIORITY_KEYWORDS: dict[PriorityLevel, list[str]] = {
    PriorityLevel.critical: ["critical", "p1", "priority 1", "emergency", "total loss"],
    PriorityLevel.high: ["high", "p2", "priority 2", "major", "significant"],
    PriorityLevel.medium: ["medium", "p3", "priority 3", "moderate", "standard"],
    PriorityLevel.low: ["low", "p4", "priority 4", "minor", "cosmetic"],
}

_SECTION_SPLIT_PATTERN = re.compile(
    r"(?:^|\n)(?:section|clause|article|schedule|appendix|annex)\s+[\d]+",
    re.IGNORECASE,
)


class ContractParser:
    """Extracts structured contract data from text or structured payloads."""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def parse_contract(self, text_or_payload: Union[str, dict]) -> ParsedContract:
        """Parse a contract from raw text or a structured dict payload.

        When *text_or_payload* is a dict the parser looks for pre-extracted
        keys such as ``clauses``, ``sla_table``, ``rate_card``, etc.  When it
        is a string the parser falls back to regex-based section splitting.
        """
        if isinstance(text_or_payload, dict):
            return self._parse_from_dict(text_or_payload)
        return self._parse_from_text(text_or_payload)

    # ------------------------------------------------------------------
    # Dict-based parsing
    # ------------------------------------------------------------------

    def _parse_from_dict(self, payload: dict) -> ParsedContract:
        raw_clauses = payload.get("clauses", [])
        clauses = [self._clause_from_dict(c) for c in raw_clauses] if raw_clauses else []

        sla_data = payload.get("sla_table") or payload.get("sla") or []
        sla_table = self.extract_sla_table(sla_data)

        rate_data = payload.get("rate_card") or payload.get("rates") or []
        rate_card = self.extract_rate_card(rate_data)

        scope_data = payload.get("scope_boundaries") or payload.get("scope") or []
        scope_boundaries = self.extract_scope_boundaries(scope_data)

        obligations = self.extract_obligations(clauses)
        penalties = self.extract_penalties(clauses)
        billable_events = self.extract_billable_events(rate_card)

        effective_date = self._parse_date(payload.get("effective_date"))
        expiry_date = self._parse_date(payload.get("expiry_date"))

        contract_type_raw = payload.get("contract_type", "master_services")
        try:
            contract_type = ContractType(contract_type_raw)
        except ValueError:
            contract_type = ContractType.master_services

        return ParsedContract(
            document_type=payload.get("document_type", "contract"),
            title=payload.get("title", ""),
            effective_date=effective_date,
            expiry_date=expiry_date,
            parties=payload.get("parties", []),
            contract_type=contract_type,
            governing_law=payload.get("governing_law", "England and Wales"),
            payment_terms=payload.get("payment_terms", "30 days net"),
            clauses=clauses,
            sla_table=sla_table,
            rate_card=rate_card,
            scope_boundaries=scope_boundaries,
            obligations=obligations,
            penalties=penalties,
            billable_events=billable_events,
        )

    @staticmethod
    def _clause_from_dict(raw: dict) -> ExtractedClause:
        clause_type_raw = raw.get("type", "obligation")
        try:
            clause_type = ClauseType(clause_type_raw)
        except ValueError:
            clause_type = ClauseType.obligation

        risk_raw = raw.get("risk_level", "medium")
        try:
            risk_level = PriorityLevel(risk_raw)
        except ValueError:
            risk_level = PriorityLevel.medium

        return ExtractedClause(
            id=raw.get("id", str(uuid.uuid4())),
            type=clause_type,
            text=raw.get("text", ""),
            section=raw.get("section", ""),
            confidence=float(raw.get("confidence", 0.9)),
            risk_level=risk_level,
        )

    # ------------------------------------------------------------------
    # Text-based parsing
    # ------------------------------------------------------------------

    def _parse_from_text(self, text: str) -> ParsedContract:
        clauses = self.extract_clauses(text)
        obligations = self.extract_obligations(clauses)
        penalties = self.extract_penalties(clauses)

        return ParsedContract(
            document_type="contract",
            title=self._extract_title(text),
            clauses=clauses,
            obligations=obligations,
            penalties=penalties,
        )

    def extract_clauses(self, text: str) -> list[ExtractedClause]:
        """Split text into sections and classify each as a clause."""
        sections = _SECTION_SPLIT_PATTERN.split(text)
        clauses: list[ExtractedClause] = []
        for idx, section_text in enumerate(sections):
            section_text = section_text.strip()
            if len(section_text) < 20:
                continue
            clause_type = self._classify_clause(section_text)
            risk_level = self._assess_risk(section_text, clause_type)
            clauses.append(
                ExtractedClause(
                    id=str(uuid.uuid4()),
                    type=clause_type,
                    text=section_text,
                    section=f"Section {idx + 1}",
                    confidence=0.75,
                    risk_level=risk_level,
                )
            )
        if not clauses and len(text.strip()) >= 20:
            clauses.append(
                ExtractedClause(
                    id=str(uuid.uuid4()),
                    type=self._classify_clause(text),
                    text=text.strip(),
                    section="Full Document",
                    confidence=0.5,
                    risk_level=PriorityLevel.medium,
                )
            )
        return clauses

    # ------------------------------------------------------------------
    # SLA extraction
    # ------------------------------------------------------------------

    def extract_sla_table(self, text_or_data: Union[str, list]) -> list[SLAEntry]:
        """Extract SLA entries from a list of dicts or raw text."""
        if isinstance(text_or_data, list):
            return [self._normalize_sla_entry(item) for item in text_or_data if isinstance(item, dict)]
        entries: list[SLAEntry] = []
        for line in text_or_data.splitlines():
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 3:
                priority = self._match_priority(parts[0])
                try:
                    response_h = float(re.sub(r"[^\d.]", "", parts[1]))
                    resolution_h = float(re.sub(r"[^\d.]", "", parts[2]))
                except (ValueError, IndexError):
                    continue
                penalty_pct = 0.0
                if len(parts) >= 4:
                    try:
                        penalty_pct = float(re.sub(r"[^\d.]", "", parts[3]))
                    except ValueError:
                        pass
                entries.append(SLAEntry(
                    priority=priority,
                    response_time_hours=response_h,
                    resolution_time_hours=resolution_h,
                    penalty_percentage=penalty_pct,
                ))
        return entries

    def _normalize_sla_entry(self, raw: dict) -> SLAEntry:
        """Normalise varying field names into a canonical SLAEntry."""
        priority_raw = raw.get("priority") or raw.get("category") or "medium"
        priority = self._match_priority(str(priority_raw))

        response_hours = raw.get("response_time_hours")
        if response_hours is None:
            response_minutes = raw.get("response_time_minutes", 60)
            response_hours = float(response_minutes) / 60.0
        response_hours = float(response_hours)

        resolution_hours = raw.get("resolution_time_hours")
        if resolution_hours is None:
            resolution_minutes = raw.get("resolution_time_minutes", 480)
            resolution_hours = float(resolution_minutes) / 60.0
        resolution_hours = float(resolution_hours)

        return SLAEntry(
            priority=priority,
            response_time_hours=max(response_hours, 0.01),
            resolution_time_hours=max(resolution_hours, 0.01),
            availability=float(raw.get("availability", 99.5)),
            penalty_percentage=float(raw.get("penalty_percentage", 0.0)),
            measurement_window=raw.get("measurement_window", "monthly"),
        )

    # ------------------------------------------------------------------
    # Rate card extraction
    # ------------------------------------------------------------------

    def extract_rate_card(self, text_or_data: Union[str, list]) -> list[RateCardEntry]:
        """Extract rate card entries from list of dicts or raw text."""
        if isinstance(text_or_data, list):
            return [self._normalize_rate_entry(item) for item in text_or_data if isinstance(item, dict)]
        entries: list[RateCardEntry] = []
        for line in text_or_data.splitlines():
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 3:
                activity = parts[0]
                unit = parts[1] if len(parts) > 3 else "each"
                try:
                    rate_val = float(re.sub(r"[^\d.]", "", parts[-1]))
                except ValueError:
                    continue
                entries.append(RateCardEntry(activity=activity, unit=unit, rate=rate_val))
        return entries

    def _normalize_rate_entry(self, raw: dict) -> RateCardEntry:
        """Normalise varying field names into a canonical RateCardEntry."""
        activity = raw.get("activity") or raw.get("activity_code") or raw.get("description") or "unknown"
        rate_val = raw.get("rate") or raw.get("base_rate") or raw.get("unit_rate") or 0.0

        effective_from = self._parse_date(raw.get("effective_from"))
        effective_to = self._parse_date(raw.get("effective_to"))

        multipliers: dict[str, float] = {}
        raw_mult = raw.get("multipliers", {})
        if isinstance(raw_mult, dict):
            for k, v in raw_mult.items():
                try:
                    multipliers[k] = float(v)
                except (ValueError, TypeError):
                    pass

        return RateCardEntry(
            activity=str(activity),
            unit=raw.get("unit", "each"),
            rate=float(rate_val),
            currency=raw.get("currency", "GBP"),
            effective_from=effective_from,
            effective_to=effective_to,
            multipliers=multipliers,
        )

    # ------------------------------------------------------------------
    # Scope, obligations, penalties, billable events
    # ------------------------------------------------------------------

    def extract_scope_boundaries(self, data: Union[list, dict, str]) -> list[ScopeBoundary]:
        """Extract scope boundaries from structured data."""
        if isinstance(data, str):
            return []
        items = data if isinstance(data, list) else [data]
        boundaries: list[ScopeBoundary] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            scope_raw = item.get("scope_type", "in_scope")
            try:
                scope_type = ScopeType(scope_raw)
            except ValueError:
                scope_type = ScopeType.in_scope
            boundaries.append(ScopeBoundary(
                scope_type=scope_type,
                description=item.get("description", ""),
                activities=item.get("activities", []),
                conditions=item.get("conditions", []),
            ))
        return boundaries

    def extract_obligations(self, clauses: list[ExtractedClause]) -> list[Obligation]:
        """Derive obligations from extracted clauses."""
        obligations: list[Obligation] = []
        for clause in clauses:
            if clause.type != ClauseType.obligation:
                continue
            evidence: list[str] = []
            text_lower = clause.text.lower()
            if "photograph" in text_lower or "photo" in text_lower:
                evidence.append("photograph")
            if "daywork" in text_lower or "day work" in text_lower:
                evidence.append("daywork_sheet")
            if "signature" in text_lower or "sign-off" in text_lower:
                evidence.append("signed_approval")
            if "report" in text_lower:
                evidence.append("completion_report")

            deadline = 30
            deadline_match = re.search(r"(\d+)\s*(?:calendar|business|working)?\s*days?", clause.text, re.IGNORECASE)
            if deadline_match:
                deadline = int(deadline_match.group(1))

            owner = "provider"
            if "client shall" in text_lower or "customer shall" in text_lower:
                owner = "client"
            elif "both parties" in text_lower or "jointly" in text_lower:
                owner = "both"

            obligations.append(Obligation(
                clause_id=clause.id,
                description=clause.text[:200],
                frequency="per_event",
                owner=owner,
                evidence_required=evidence,
                deadline_days=deadline,
            ))
        return obligations

    def extract_penalties(self, clauses: list[ExtractedClause]) -> list[PenaltyCondition]:
        """Derive penalty conditions from extracted clauses."""
        penalties: list[PenaltyCondition] = []
        for clause in clauses:
            if clause.type != ClauseType.penalty:
                continue
            text_lower = clause.text.lower()

            penalty_type = "percentage"
            if "fixed" in text_lower or "flat" in text_lower:
                penalty_type = "fixed"
            elif "liquidated" in text_lower:
                penalty_type = "liquidated_damages"
            elif "service credit" in text_lower:
                penalty_type = "service_credit"

            amount = 0.0
            amount_match = re.search(r"(\d+(?:\.\d+)?)\s*%", clause.text)
            if amount_match:
                amount = float(amount_match.group(1))
            else:
                gbp_match = re.search(r"[£$]\s*([\d,]+(?:\.\d+)?)", clause.text)
                if gbp_match:
                    amount = float(gbp_match.group(1).replace(",", ""))

            cap: Optional[float] = None
            cap_match = re.search(r"cap(?:ped)?\s*(?:at|of)?\s*[£$]?\s*([\d,]+(?:\.\d+)?)", clause.text, re.IGNORECASE)
            if cap_match:
                cap = float(cap_match.group(1).replace(",", ""))

            grace_days = 0
            grace_match = re.search(r"grace\s*(?:period)?\s*(?:of)?\s*(\d+)\s*days?", clause.text, re.IGNORECASE)
            if grace_match:
                grace_days = int(grace_match.group(1))

            cure_days = 0
            cure_match = re.search(r"cure\s*(?:period)?\s*(?:of)?\s*(\d+)\s*days?", clause.text, re.IGNORECASE)
            if cure_match:
                cure_days = int(cure_match.group(1))

            penalties.append(PenaltyCondition(
                clause_id=clause.id,
                description=clause.text[:200],
                trigger=self._extract_trigger(clause.text),
                penalty_type=penalty_type,
                penalty_amount=amount,
                cap=cap,
                grace_period_days=grace_days,
                cure_period_days=cure_days,
            ))
        return penalties

    def extract_billable_events(self, rate_card: list[RateCardEntry]) -> list[BillableEvent]:
        """Derive billable events from a rate card."""
        events: list[BillableEvent] = []
        for entry in rate_card:
            activity_lower = entry.activity.lower()
            category = BillableCategory.standard
            if "emergency" in activity_lower:
                category = BillableCategory.emergency
            elif "overtime" in activity_lower or "out of hours" in activity_lower:
                category = BillableCategory.overtime
            elif "material" in activity_lower:
                category = BillableCategory.materials
            elif "subcontract" in activity_lower:
                category = BillableCategory.subcontractor
            elif "mobilisation" in activity_lower or "mobilization" in activity_lower:
                category = BillableCategory.mobilisation

            prerequisites: list[str] = ["work_order_raised"]
            evidence: list[str] = ["completion_record"]
            if category == BillableCategory.emergency:
                prerequisites.append("emergency_authorisation")
                evidence.append("incident_reference")
            if category == BillableCategory.materials:
                prerequisites.append("material_order_approved")
                evidence.append("delivery_note")
            if category == BillableCategory.subcontractor:
                prerequisites.append("subcontractor_po_raised")
                evidence.append("subcontractor_invoice")

            events.append(BillableEvent(
                activity=entry.activity,
                category=category,
                rate=entry.rate,
                unit=entry.unit,
                prerequisites=prerequisites,
                evidence_required=evidence,
            ))
        return events

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_clause(text: str) -> ClauseType:
        text_lower = text.lower()
        best_type = ClauseType.obligation
        best_score = 0
        for ctype, keywords in _CLAUSE_KEYWORD_MAP.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_type = ctype
        return best_type

    @staticmethod
    def _assess_risk(text: str, clause_type: ClauseType) -> PriorityLevel:
        high_risk_types = {ClauseType.penalty, ClauseType.liability, ClauseType.termination}
        if clause_type in high_risk_types:
            return PriorityLevel.high
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["unlimited", "uncapped", "sole discretion"]):
            return PriorityLevel.critical
        if any(kw in text_lower for kw in ["material breach", "gross negligence"]):
            return PriorityLevel.high
        return PriorityLevel.medium

    @staticmethod
    def _match_priority(raw: str) -> PriorityLevel:
        raw_lower = raw.lower().strip()
        for level, keywords in _PRIORITY_KEYWORDS.items():
            if any(kw in raw_lower for kw in keywords):
                return level
        return PriorityLevel.medium

    @staticmethod
    def _extract_trigger(text: str) -> str:
        text_lower = text.lower()
        if "failure to" in text_lower:
            idx = text_lower.index("failure to")
            return text[idx: idx + 80].strip()
        if "breach" in text_lower:
            idx = text_lower.index("breach")
            return text[idx: idx + 80].strip()
        if "exceed" in text_lower:
            idx = text_lower.index("exceed")
            return text[idx: idx + 80].strip()
        return text[:80].strip()

    @staticmethod
    def _extract_title(text: str) -> str:
        first_line = text.strip().split("\n")[0].strip()
        if len(first_line) < 200:
            return first_line
        return first_line[:200]

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
        return None
