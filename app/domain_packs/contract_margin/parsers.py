"""Contract & Margin domain parsers."""

from __future__ import annotations

import json
import re
from typing import Any

from app.domain_packs.contract_margin.schemas import (
    BillableCategory,
    BillableEvent,
    BillingGate,
    BillingPrerequisite,
    ClauseType,
    ExtractedClause,
    Obligation,
    ParsedContract,
    PenaltyCondition,
    RateCardEntry,
    ReattendanceRule,
    SLAEntry,
    ServiceCreditRule,
    SPENRateCard,
    WorkCategory,
)


class ContractParser:
    """Parse contract documents into structured objects."""

    def parse_contract(self, text_or_payload: str | dict) -> ParsedContract:
        """Parse a contract from raw text or JSON payload."""
        if isinstance(text_or_payload, dict):
            return self._parse_from_json(text_or_payload)
        return self._parse_from_text(text_or_payload)

    def _parse_from_json(self, data: dict) -> ParsedContract:
        clauses = [
            ExtractedClause(
                id=c.get("id", f"CL-{i}"),
                type=ClauseType(c.get("type", "obligation")),
                text=c.get("text", ""),
                section=c.get("section", ""),
            )
            for i, c in enumerate(data.get("clauses", []))
        ]
        sla_table = [SLAEntry(**s) for s in data.get("sla_table", [])]
        rate_card = [RateCardEntry(**r) for r in data.get("rate_card", [])]

        return ParsedContract(
            document_type=data.get("document_type", "contract"),
            title=data.get("title", ""),
            parties=data.get("parties", []),
            clauses=clauses,
            sla_table=sla_table,
            rate_card=rate_card,
        )

    def _parse_from_text(self, text: str) -> ParsedContract:
        clauses = self.extract_clauses(text)
        sla_table = self.extract_sla_table(text)
        rate_card = self.extract_rate_card(text)
        title = self._extract_title(text)

        return ParsedContract(
            document_type="contract",
            title=title,
            clauses=clauses,
            sla_table=sla_table,
            rate_card=rate_card,
        )

    def extract_clauses(self, text: str) -> list[ExtractedClause]:
        """Extract clauses from contract text using pattern matching."""
        clauses: list[ExtractedClause] = []
        # Match section patterns like "3.1 Provider shall..."
        pattern = r'(\d+\.\d+)\s+(.+?)(?=\n\d+\.\d+|\n\n|\Z)'
        matches = re.findall(pattern, text, re.DOTALL)

        for i, (section, content) in enumerate(matches):
            content = content.strip()
            clause_type = self._classify_clause(content)
            clauses.append(
                ExtractedClause(
                    id=f"CL-{i+1:03d}",
                    type=clause_type,
                    text=content,
                    section=section,
                )
            )
        return clauses

    def extract_sla_table(self, text: str) -> list[SLAEntry]:
        """Extract SLA entries from text."""
        entries: list[SLAEntry] = []
        # Match patterns like "P1: response 1hr, resolution 4hr"
        pattern = r'(P[1-4])[:\s]+(?:response\s+)?(\d+)\s*(?:hr|hour).*?(?:resolution\s+)?(\d+)\s*(?:hr|hour)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        for priority, response, resolution in matches:
            entries.append(
                SLAEntry(
                    priority=priority.upper(),
                    response_time_hours=float(response),
                    resolution_time_hours=float(resolution),
                    availability="24x7" if priority.upper() in ("P1", "P2") else "business_hours",
                )
            )
        return entries

    def extract_rate_card(self, text: str) -> list[RateCardEntry]:
        """Extract rate card entries from text."""
        entries: list[RateCardEntry] = []
        # Match patterns like "$125/hr" or "125.00 per hour"
        pattern = r'(\w[\w\s]+?)[\s:]+\$?([\d,.]+)\s*(?:per|/)\s*(\w+)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        for activity, rate, unit in matches:
            try:
                entries.append(
                    RateCardEntry(
                        activity=activity.strip().lower().replace(" ", "_"),
                        rate=float(rate.replace(",", "")),
                        unit=unit.lower(),
                    )
                )
            except ValueError:
                continue
        return entries

    def extract_obligations(self, clauses: list[ExtractedClause]) -> list[Obligation]:
        return [
            Obligation(clause_id=c.id, description=c.text)
            for c in clauses
            if c.type == ClauseType.obligation
        ]

    def extract_penalties(self, clauses: list[ExtractedClause]) -> list[PenaltyCondition]:
        return [
            PenaltyCondition(
                clause_id=c.id,
                description=c.text,
                trigger=self._extract_penalty_trigger(c.text),
                penalty_amount=self._extract_penalty_amount(c.text),
            )
            for c in clauses
            if c.type == ClauseType.penalty
        ]

    def extract_billable_events(self, rate_card: list[RateCardEntry]) -> list[BillableEvent]:
        return [
            BillableEvent(
                activity=r.activity,
                rate=r.rate,
                unit=r.unit,
                category=BillableCategory.time_and_materials if r.unit in ("hour", "hr") else BillableCategory.fixed_price,
            )
            for r in rate_card
        ]

    def _classify_clause(self, text: str) -> ClauseType:
        lower = text.lower()
        if any(kw in lower for kw in ["shall", "must", "obligated", "required to"]):
            if any(kw in lower for kw in ["penalty", "breach", "failure", "liquidated"]):
                return ClauseType.penalty
            return ClauseType.obligation
        if any(kw in lower for kw in ["sla", "response time", "resolution time", "availability"]):
            return ClauseType.sla
        if any(kw in lower for kw in ["rate", "price", "cost", "fee", "charge"]):
            return ClauseType.rate
        if any(kw in lower for kw in ["scope", "services include", "deliverables"]):
            return ClauseType.scope
        if any(kw in lower for kw in ["terminate", "termination", "expiry"]):
            return ClauseType.termination
        return ClauseType.obligation

    def _extract_title(self, text: str) -> str:
        lines = text.strip().split("\n")
        return lines[0].strip() if lines else ""

    def _extract_penalty_trigger(self, text: str) -> str:
        match = re.search(r'(?:failure|breach|failure to)\s+(.+?)(?:\.|,)', text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_penalty_amount(self, text: str) -> str:
        match = re.search(r'(\d+%|\$[\d,.]+)', text)
        return match.group(1) if match else ""
