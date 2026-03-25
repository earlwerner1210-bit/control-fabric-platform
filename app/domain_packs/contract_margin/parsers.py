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

    # -- SPEN / Vodafone extraction helpers --------------------------------

    def extract_billing_gates(self, clauses: list[ExtractedClause]) -> list[BillingGate]:
        """Extract billing prerequisite gates from clause text.

        Scans obligation- and rate-type clauses for keywords that indicate
        a billing prerequisite must be satisfied before invoicing.
        """
        _GATE_KEYWORDS: dict[str, BillingPrerequisite] = {
            "prior approval": BillingPrerequisite.prior_approval,
            "purchase order": BillingPrerequisite.purchase_order,
            "variation order": BillingPrerequisite.variation_order,
            "daywork sheet": BillingPrerequisite.daywork_sheet_signed,
            "completion certificate": BillingPrerequisite.completion_certificate,
            "customer sign-off": BillingPrerequisite.customer_sign_off,
            "customer sign off": BillingPrerequisite.customer_sign_off,
            "as-built": BillingPrerequisite.as_built_submitted,
            "as built": BillingPrerequisite.as_built_submitted,
            "permit": BillingPrerequisite.permit_closed_out,
        }

        gates: list[BillingGate] = []
        seen: set[BillingPrerequisite] = set()

        for clause in clauses:
            lower = clause.text.lower()
            for keyword, gate_type in _GATE_KEYWORDS.items():
                if keyword in lower and gate_type not in seen:
                    gates.append(BillingGate(
                        gate_type=gate_type,
                        description=f"Extracted from clause {clause.id}: {clause.text[:120]}",
                    ))
                    seen.add(gate_type)

        return gates

    def extract_reattendance_rules(self, clauses: list[ExtractedClause]) -> list[ReattendanceRule]:
        """Extract re-attendance billing rules from clause text.

        Looks for clauses mentioning re-attendance, revisit, rework or
        similar terminology and maps them to structured rules.
        """
        _TRIGGER_PATTERNS: dict[str, dict] = {
            r"provider\s*fault|contractor\s*fault|quality\s*failure|rework": {
                "trigger": "provider_fault",
                "billable": False,
                "evidence_required": ["root_cause_report", "quality_nonconformance"],
                "description": "Provider-fault re-attendance is non-billable",
            },
            r"customer\s*fault|customer\s*cancel|no[\s-]access\s*customer": {
                "trigger": "customer_fault",
                "billable": True,
                "evidence_required": ["customer_confirmation", "site_attendance_record"],
                "description": "Customer-fault re-attendance is billable",
            },
            r"dno\s*fault|network\s*fault|distribution\s*fault": {
                "trigger": "dno_fault",
                "billable": True,
                "evidence_required": ["dno_instruction", "network_event_log"],
                "description": "DNO-fault re-attendance is billable",
            },
            r"third[\s-]party|external\s*damage": {
                "trigger": "third_party",
                "billable": True,
                "evidence_required": ["third_party_incident_ref", "site_report"],
                "description": "Third-party-caused re-attendance is billable",
            },
            r"weather|adverse\s*conditions|storm|flood": {
                "trigger": "weather",
                "billable": True,
                "evidence_required": ["weather_event_record", "risk_assessment"],
                "description": "Weather-related re-attendance is billable",
            },
        }

        rules: list[ReattendanceRule] = []
        seen_triggers: set[str] = set()

        for clause in clauses:
            lower = clause.text.lower()
            if not any(kw in lower for kw in ("reattend", "re-attend", "revisit", "re-visit", "rework", "re-work")):
                continue
            for pattern, rule_data in _TRIGGER_PATTERNS.items():
                if re.search(pattern, lower) and rule_data["trigger"] not in seen_triggers:
                    rules.append(ReattendanceRule(**rule_data))
                    seen_triggers.add(rule_data["trigger"])

        return rules

    def extract_service_credits(self, clauses: list[ExtractedClause]) -> list[ServiceCreditRule]:
        """Extract service credit mechanisms from clause text.

        Identifies SLA-linked credit clauses and parses metric, threshold,
        credit percentage, and cap where present.
        """
        _METRIC_PATTERNS: dict[str, str] = {
            r"response\s*time": "response_time",
            r"resolution\s*time|fix\s*time": "resolution_time",
            r"first[\s-]time\s*fix": "first_time_fix",
            r"appointment\s*kept|appointment\s*window": "appointment_kept",
        }

        rules: list[ServiceCreditRule] = []

        for clause in clauses:
            lower = clause.text.lower()
            if "service credit" not in lower and "credit" not in lower:
                continue

            for pattern, metric in _METRIC_PATTERNS.items():
                if not re.search(pattern, lower):
                    continue

                # Attempt to extract percentage values
                pct_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', clause.text)
                credit_pct = float(pct_matches[0]) if pct_matches else 5.0
                cap_pct = float(pct_matches[1]) if len(pct_matches) > 1 else 10.0

                # Attempt to extract threshold value (hours or percentage)
                threshold_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:hour|hr|h\b)', lower)
                if threshold_match:
                    threshold = float(threshold_match.group(1))
                else:
                    threshold_match = re.search(r'(\d+(?:\.\d+)?)\s*%', lower)
                    threshold = float(threshold_match.group(1)) / 100.0 if threshold_match else 0.0

                # Extract exclusions
                exclusions: list[str] = []
                if "force majeure" in lower:
                    exclusions.append("force_majeure")
                if "customer caused" in lower or "customer fault" in lower:
                    exclusions.append("customer_caused")

                rules.append(ServiceCreditRule(
                    sla_metric=metric,
                    threshold_value=threshold,
                    credit_percentage=credit_pct,
                    cap_percentage=cap_pct,
                    exclusions=exclusions,
                ))

        return rules


class SPENRateCardParser:
    """Parse SPEN electricity distribution rate card data."""

    def parse_rate_card(self, data: list[dict]) -> list[SPENRateCard]:
        """Parse a list of rate card dictionaries into typed SPENRateCard models.

        Each dict should contain at minimum: ``work_category``, ``activity_code``,
        ``description``, ``unit``, and ``base_rate``.
        """
        cards: list[SPENRateCard] = []
        for entry in data:
            try:
                work_cat = entry.get("work_category", "")
                # Normalise to enum value
                if isinstance(work_cat, str):
                    work_cat = work_cat.lower().replace(" ", "_").replace("-", "_")
                cards.append(SPENRateCard(
                    work_category=WorkCategory(work_cat),
                    activity_code=str(entry.get("activity_code", "")),
                    description=str(entry.get("description", "")),
                    unit=str(entry.get("unit", "each")),
                    base_rate=float(entry.get("base_rate", 0.0)),
                    emergency_multiplier=float(entry.get("emergency_multiplier", 1.5)),
                    overtime_multiplier=float(entry.get("overtime_multiplier", 1.3)),
                    weekend_multiplier=float(entry.get("weekend_multiplier", 1.5)),
                    currency=str(entry.get("currency", "GBP")),
                    effective_from=str(entry.get("effective_from", "")),
                    effective_to=str(entry.get("effective_to", "")),
                    requires_approval_above=(
                        float(entry["requires_approval_above"])
                        if entry.get("requires_approval_above") is not None
                        else None
                    ),
                ))
            except (ValueError, KeyError):
                continue
        return cards

    def parse_from_table(self, rows: list[dict]) -> list[SPENRateCard]:
        """Parse tabular rate card data (e.g. from spreadsheet export).

        Accepts rows with column names that may use human-readable headers.
        Normalises column names before delegating to ``parse_rate_card``.
        """
        _COLUMN_MAP: dict[str, str] = {
            "category": "work_category",
            "work category": "work_category",
            "code": "activity_code",
            "activity code": "activity_code",
            "activity": "activity_code",
            "desc": "description",
            "rate": "base_rate",
            "base rate": "base_rate",
            "price": "base_rate",
            "uom": "unit",
            "unit of measure": "unit",
            "emergency": "emergency_multiplier",
            "overtime": "overtime_multiplier",
            "weekend": "weekend_multiplier",
            "ccy": "currency",
            "from": "effective_from",
            "to": "effective_to",
            "approval threshold": "requires_approval_above",
        }

        normalised: list[dict] = []
        for row in rows:
            mapped: dict = {}
            for key, value in row.items():
                canonical = _COLUMN_MAP.get(key.lower().strip(), key.lower().strip().replace(" ", "_"))
                mapped[canonical] = value
            normalised.append(mapped)

        return self.parse_rate_card(normalised)
