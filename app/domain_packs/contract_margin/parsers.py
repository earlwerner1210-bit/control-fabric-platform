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
    ClauseSegment,
    ClauseType,
    ExtractedClause,
    Obligation,
    ParsedContract,
    PenaltyCondition,
    RateCardEntry,
    ReattendanceRule,
    ScopeBoundaryObject,
    ScopeType,
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
        sla_table = [self._normalize_sla_entry(s) for s in data.get("sla_table", [])]
        rate_card = [self._normalize_rate_entry(r) for r in data.get("rate_card", [])]

        return ParsedContract(
            document_type=data.get("document_type", "contract"),
            title=data.get("title", ""),
            parties=data.get("parties", []),
            clauses=clauses,
            sla_table=sla_table,
            rate_card=rate_card,
        )

    @staticmethod
    def _normalize_sla_entry(raw: dict) -> SLAEntry:
        """Normalize SLA entry from various field naming conventions."""
        priority = raw.get("priority") or raw.get("category", "")
        response_hours = raw.get("response_time_hours")
        if response_hours is None and raw.get("response_time_minutes") is not None:
            response_hours = raw["response_time_minutes"] / 60.0
        if response_hours is None:
            response_hours = 0.0
        resolution_hours = raw.get("resolution_time_hours") or 0.0
        return SLAEntry(
            priority=priority,
            response_time_hours=response_hours,
            resolution_time_hours=resolution_hours,
            availability=raw.get("availability", "business_hours"),
            penalty_percentage=raw.get("penalty_percentage"),
            measurement_window=raw.get("measurement_window", "monthly"),
        )

    @staticmethod
    def _normalize_rate_entry(raw: dict) -> RateCardEntry:
        """Normalize rate card entry from various field naming conventions."""
        activity = raw.get("activity") or raw.get("activity_code") or raw.get("description", "")
        rate = raw.get("rate") or raw.get("base_rate", 0.0)
        return RateCardEntry(
            activity=activity,
            unit=raw.get("unit", "each"),
            rate=rate,
            currency=raw.get("currency", "USD"),
            effective_from=raw.get("effective_from"),
            effective_to=raw.get("effective_to"),
            escalation_rate=raw.get("escalation_rate"),
            minimum_charge=raw.get("minimum_charge"),
            overtime_multiplier=raw.get("overtime_multiplier"),
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

    # -- new Wave-1 extraction methods -------------------------------------

    def extract_headings(self, text: str) -> list[dict]:
        """Extract document section headings with hierarchy.

        Returns list of dicts with:
        - heading_text: str
        - level: int (1=major, 2=sub, 3=sub-sub)
        - section_number: str (e.g. "3.1", "3.1.2")
        - offset_start: int
        - offset_end: int
        """
        headings: list[dict] = []

        # Pattern 1: numbered sections like "1.", "1.1", "1.1.1" followed by text
        numbered_pattern = re.compile(
            r'^[ \t]*((\d+(?:\.\d+)*)\.?)\s+([^\n]+)',
            re.MULTILINE,
        )
        for match in numbered_pattern.finditer(text):
            section_number = match.group(2)
            heading_text = match.group(3).strip()
            # Skip lines that look like body text (very long) or numeric-only
            if len(heading_text) > 200 or not heading_text:
                continue
            dot_count = section_number.count(".")
            level = min(dot_count + 1, 3)

            headings.append({
                "heading_text": heading_text,
                "level": level,
                "section_number": section_number,
                "offset_start": match.start(),
                "offset_end": match.end(),
            })

        # Pattern 2: "SECTION 1", "Article 1", "Schedule A/1"
        named_pattern = re.compile(
            r'^[ \t]*((?:SECTION|Article|Schedule)\s+([A-Za-z0-9]+))[:\s.\-]+\s*([^\n]*)',
            re.MULTILINE | re.IGNORECASE,
        )
        for match in named_pattern.finditer(text):
            section_id = match.group(2).strip()
            heading_text = match.group(3).strip() if match.group(3).strip() else match.group(1).strip()
            headings.append({
                "heading_text": heading_text,
                "level": 1,
                "section_number": section_id,
                "offset_start": match.start(),
                "offset_end": match.end(),
            })

        # Sort by offset_start for document order
        headings.sort(key=lambda h: h["offset_start"])
        return headings

    def extract_clause_segments(self, text: str) -> list[ClauseSegment]:
        """Extract fine-grained clause segments with positional offsets.

        Each segment preserves clause_number, heading, text content,
        clause_type (inferred from keywords), section_ref,
        parent_clause_id (for nested clauses), source offsets, and confidence.
        """
        segments: list[ClauseSegment] = []

        # Split text by section numbers (e.g. "1.", "1.1", "1.1.1")
        section_pattern = re.compile(
            r'^[ \t]*((\d+(?:\.\d+)*)\.?)\s+',
            re.MULTILINE,
        )
        matches = list(section_pattern.finditer(text))
        if not matches:
            return segments

        for idx, match in enumerate(matches):
            section_number = match.group(2)
            offset_start = match.start()
            # Content goes until the next section or end of text
            if idx + 1 < len(matches):
                offset_end = matches[idx + 1].start()
            else:
                offset_end = len(text)

            raw_content = text[match.end():offset_end].strip()
            if not raw_content:
                continue

            # Extract heading: first line of content (if short enough)
            lines = raw_content.split("\n", 1)
            first_line = lines[0].strip()
            heading = first_line if len(first_line) <= 120 else ""
            body_text = raw_content

            # Determine clause type by keyword matching
            clause_type = self._classify_clause(body_text)

            # Confidence based on keyword strength
            confidence = self._compute_segment_confidence(body_text, clause_type)

            # Determine parent clause id (e.g. "3.1" is child of "3")
            parent_clause_id: str | None = None
            parts = section_number.split(".")
            if len(parts) > 1:
                parent_number = ".".join(parts[:-1])
                parent_clause_id = f"SEG-{parent_number}"

            segment_id = f"SEG-{section_number}"

            segments.append(ClauseSegment(
                id=segment_id,
                clause_number=section_number,
                heading=heading,
                text=body_text,
                clause_type=clause_type,
                section_ref=section_number,
                parent_clause_id=parent_clause_id,
                source_offset_start=offset_start,
                source_offset_end=offset_end,
                confidence=confidence,
            ))

        return segments

    def _compute_segment_confidence(self, text: str, clause_type: ClauseType) -> float:
        """Compute confidence score based on keyword strength for a clause segment."""
        lower = text.lower()
        # Strong keyword matches yield higher confidence
        strong_keywords = {
            ClauseType.obligation: ["shall", "must", "required to", "obligated"],
            ClauseType.penalty: ["penalty", "liquidated damages", "breach"],
            ClauseType.sla: ["response time", "resolution time", "service level"],
            ClauseType.rate: ["rate", "price per", "fee schedule"],
            ClauseType.scope: ["in scope", "out of scope", "deliverables"],
            ClauseType.termination: ["terminate", "termination for cause"],
        }
        keywords = strong_keywords.get(clause_type, [])
        if not keywords:
            return 0.6

        match_count = sum(1 for kw in keywords if kw in lower)
        if match_count >= 2:
            return 0.95
        if match_count == 1:
            return 0.80
        return 0.60

    def extract_scope_boundaries(self, text: str | dict) -> list[ScopeBoundaryObject]:
        """Extract scope boundaries from contract text.

        Looks for:
        - "in scope" / "included" / "shall provide" -> in_scope
        - "out of scope" / "excluded" / "shall not include" -> out_of_scope
        - "conditional" / "subject to" / "upon request" -> conditional

        Returns ScopeBoundaryObject instances with activities, conditions, clause_refs.
        """
        if isinstance(text, dict):
            text = str(text)

        boundaries: list[ScopeBoundaryObject] = []

        _SCOPE_PATTERNS: list[tuple[re.Pattern, ScopeType]] = [
            (re.compile(
                r'(?:in[\s-]scope|included|shall\s+provide|services?\s+include)[:\s]*([^\n.]+)',
                re.IGNORECASE,
            ), ScopeType.in_scope),
            (re.compile(
                r'(?:out[\s-]of[\s-]scope|excluded|shall\s+not\s+include|not\s+included)[:\s]*([^\n.]+)',
                re.IGNORECASE,
            ), ScopeType.out_of_scope),
            (re.compile(
                r'(?:conditional(?:ly)?|subject\s+to|upon\s+request|where\s+approved)[:\s]*([^\n.]+)',
                re.IGNORECASE,
            ), ScopeType.conditional),
        ]

        for pattern, scope_type in _SCOPE_PATTERNS:
            for match in pattern.finditer(text):
                raw = match.group(1).strip()
                # Split comma/semicolon-separated activities
                activities = [
                    a.strip()
                    for a in re.split(r'[,;]', raw)
                    if a.strip()
                ]

                # Extract conditions for conditional scope
                conditions: list[str] = []
                if scope_type == ScopeType.conditional:
                    cond_match = re.search(
                        r'(?:subject\s+to|provided\s+that|if|where)\s+(.+?)(?:\.|$)',
                        match.group(0),
                        re.IGNORECASE,
                    )
                    if cond_match:
                        conditions.append(cond_match.group(1).strip())

                # Try to find a nearby section reference
                clause_refs: list[str] = []
                preceding = text[max(0, match.start() - 200):match.start()]
                ref_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', preceding)
                if ref_match:
                    clause_refs.append(ref_match.group(1))

                description = raw[:200] if raw else match.group(0).strip()[:200]

                boundaries.append(ScopeBoundaryObject(
                    scope_type=scope_type,
                    description=description,
                    conditions=conditions,
                    clause_refs=clause_refs,
                    activities=activities,
                ))

        return boundaries

    def extract_payment_terms(self, text: str | dict) -> dict:
        """Extract payment terms from contract text.

        Returns dict with:
        - payment_period_days: int (e.g. 30, 60, 90)
        - currency: str
        - invoicing_frequency: str (monthly, quarterly)
        - late_payment_interest: float | None
        - retention_percentage: float | None
        """
        if isinstance(text, dict):
            text = str(text)

        result: dict[str, Any] = {
            "payment_period_days": 30,
            "currency": "USD",
            "invoicing_frequency": "monthly",
            "late_payment_interest": None,
            "retention_percentage": None,
        }

        # Payment period: "net 30", "within 30 days", "30 days from invoice"
        period_match = re.search(
            r'(?:net\s+(\d+)|within\s+(\d+)\s+days|(\d+)\s+days\s+(?:from|of|after)\s+(?:invoice|receipt))',
            text,
            re.IGNORECASE,
        )
        if period_match:
            days = period_match.group(1) or period_match.group(2) or period_match.group(3)
            result["payment_period_days"] = int(days)

        # Currency
        currency_match = re.search(r'\b(USD|GBP|EUR|AUD|CAD)\b', text, re.IGNORECASE)
        if currency_match:
            result["currency"] = currency_match.group(1).upper()

        # Invoicing frequency
        if re.search(r'\bquarterly\b', text, re.IGNORECASE):
            result["invoicing_frequency"] = "quarterly"
        elif re.search(r'\bannually\b|\bannual\b', text, re.IGNORECASE):
            result["invoicing_frequency"] = "annually"
        elif re.search(r'\bweekly\b', text, re.IGNORECASE):
            result["invoicing_frequency"] = "weekly"
        elif re.search(r'\bmonthly\b', text, re.IGNORECASE):
            result["invoicing_frequency"] = "monthly"

        # Late payment interest: "interest at 2%", "2% per month late"
        interest_match = re.search(
            r'(?:interest|late\s+payment)[^.]*?(\d+(?:\.\d+)?)\s*%',
            text,
            re.IGNORECASE,
        )
        if interest_match:
            result["late_payment_interest"] = float(interest_match.group(1))

        # Retention: "5% retention", "retention of 5%"
        retention_match = re.search(
            r'(?:retention\s+(?:of\s+)?|retain\s+)(\d+(?:\.\d+)?)\s*%|(\d+(?:\.\d+)?)\s*%\s*retention',
            text,
            re.IGNORECASE,
        )
        if retention_match:
            pct = retention_match.group(1) or retention_match.group(2)
            result["retention_percentage"] = float(pct)

        return result

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
