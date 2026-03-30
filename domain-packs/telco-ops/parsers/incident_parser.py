"""Parsers for incident tickets and reports.

Uses regex-based extraction to parse semi-structured incident text into
typed domain objects.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..schemas.telco_schemas import ParsedIncident, ServiceStateMapping
from ..taxonomy.telco_taxonomy import (
    EscalationLevel,
    IncidentSeverity,
    IncidentState,
    ServiceState,
)

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_SEVERITY_KEYWORDS: dict[IncidentSeverity, re.Pattern[str]] = {
    IncidentSeverity.p1: re.compile(
        r"\b(P1|priority\s*1|critical|sev[- ]?1|major\s+outage)\b", re.I
    ),
    IncidentSeverity.p2: re.compile(r"\b(P2|priority\s*2|high|sev[- ]?2|significant)\b", re.I),
    IncidentSeverity.p3: re.compile(r"\b(P3|priority\s*3|medium|sev[- ]?3|moderate)\b", re.I),
    IncidentSeverity.p4: re.compile(r"\b(P4|priority\s*4|low|sev[- ]?4|minor)\b", re.I),
}

_STATE_KEYWORDS: dict[IncidentState, re.Pattern[str]] = {
    IncidentState.new: re.compile(r"\b(new|opened|raised|reported)\b", re.I),
    IncidentState.acknowledged: re.compile(r"\b(acknowledged|accepted|assigned)\b", re.I),
    IncidentState.investigating: re.compile(
        r"\b(investigating|in\s+progress|diagnosing|troubleshooting)\b", re.I
    ),
    IncidentState.resolved: re.compile(r"\b(resolved|fixed|repaired|restored)\b", re.I),
    IncidentState.closed: re.compile(r"\b(closed|completed|archived)\b", re.I),
}

_SERVICE_STATE_KEYWORDS: dict[ServiceState, re.Pattern[str]] = {
    ServiceState.outage: re.compile(r"\b(outage|down|offline|unavailable|total\s+loss)\b", re.I),
    ServiceState.degraded: re.compile(r"\b(degraded|impaired|slow|intermittent|partial)\b", re.I),
    ServiceState.maintenance: re.compile(
        r"\b(maintenance|planned\s+work|scheduled\s+downtime)\b", re.I
    ),
    ServiceState.active: re.compile(r"\b(active|operational|healthy|normal|up)\b", re.I),
    ServiceState.provisioning: re.compile(
        r"\b(provisioning|setup|deploying|commissioning)\b", re.I
    ),
}

_DATETIME_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)"
)

_FIELD_PATTERNS = {
    "incident_id": re.compile(
        r"(?:incident|ticket|id|ref|#)\s*[:=]?\s*(INC[- ]?[\w\-]+|\w+-\d+)", re.I
    ),
    "title": re.compile(r"(?:title|subject|summary)\s*[:=]\s*(.+?)(?:\n|$)", re.I),
    "reporter": re.compile(
        r"(?:reported\s+by|reporter|raised\s+by|from)\s*[:=]?\s*(.+?)(?:\n|$)", re.I
    ),
    "assigned_to": re.compile(r"(?:assigned\s+to|owner|assignee)\s*[:=]?\s*(.+?)(?:\n|$)", re.I),
    "root_cause": re.compile(
        r"(?:root\s+cause|rca|cause)\s*[:=]\s*(.+?)(?:\n\n|\Z)", re.I | re.DOTALL
    ),
    "resolution": re.compile(
        r"(?:resolution|fix|solution|workaround)\s*[:=]\s*(.+?)(?:\n\n|\Z)", re.I | re.DOTALL
    ),
}

_AFFECTED_SERVICE_PATTERN = re.compile(
    r"(?:affected|impacted)\s+(?:service|system)\s*[:=]?\s*(.+?)(?:\n|$)",
    re.I,
)

_CUSTOMER_COUNT_PATTERN = re.compile(
    r"(\d[\d,]*)\s*(?:customers?|users?|subscribers?|accounts?)\s*(?:affected|impacted)?",
    re.I,
)

_RECURRING_PATTERN = re.compile(
    r"\b(recurring|repeat|happened\s+before|previous\s+occurrence|recurrence)\b",
    re.I,
)

_TAG_PATTERN = re.compile(r"(?:tags?|labels?|categories?)\s*[:=]\s*(.+?)(?:\n|$)", re.I)


def _parse_datetime(text: str) -> datetime | None:
    """Parse first datetime from text."""
    match = _DATETIME_PATTERN.search(text)
    if match:
        try:
            dt_str = match.group(1).replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except ValueError:
            pass
    return None


class IncidentParser:
    """Parser for extracting structured incident data from text."""

    def parse_incident(self, text: str) -> ParsedIncident:
        """Parse incident text into a ParsedIncident.

        Args:
            text: Raw incident text (ticket content, email, etc.).

        Returns:
            ParsedIncident with all extractable fields populated.
        """
        severity = self._detect_severity(text)
        state = self._detect_state(text)

        incident_id = self._extract_field(text, "incident_id")
        title = self._extract_field(text, "title") or text.split("\n")[0].strip()[:200]
        reporter = self._extract_field(text, "reporter")
        assigned_to = self._extract_field(text, "assigned_to")
        root_cause = self._extract_field(text, "root_cause")
        resolution = self._extract_field(text, "resolution")

        # Extract timestamps
        timestamps = _DATETIME_PATTERN.findall(text)
        reported_at = None
        acknowledged_at = None
        resolved_at = None

        if timestamps:
            try:
                reported_at = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))
            except ValueError:
                pass
            if len(timestamps) > 1 and state != IncidentState.new:
                try:
                    acknowledged_at = datetime.fromisoformat(timestamps[1].replace("Z", "+00:00"))
                except ValueError:
                    pass
            if len(timestamps) > 2 and state in (IncidentState.resolved, IncidentState.closed):
                try:
                    resolved_at = datetime.fromisoformat(timestamps[2].replace("Z", "+00:00"))
                except ValueError:
                    pass

        # Detect affected services
        affected_services = self._extract_affected_services(text)

        # Escalation level
        escalation = EscalationLevel.l1
        if severity == IncidentSeverity.p1:
            escalation = EscalationLevel.l2
        if re.search(r"\b(management|director|VP|CTO)\b", text, re.I):
            escalation = EscalationLevel.management
        elif re.search(r"\b(L3|level\s*3|specialist|architect)\b", text, re.I):
            escalation = EscalationLevel.l3
        elif re.search(r"\b(L2|level\s*2|senior|escalat)\b", text, re.I):
            escalation = EscalationLevel.l2

        # Tags
        tags: list[str] = []
        tag_match = _TAG_PATTERN.search(text)
        if tag_match:
            tags = [t.strip() for t in tag_match.group(1).split(",") if t.strip()]

        # Recurring
        is_recurring = bool(_RECURRING_PATTERN.search(text))
        recurrence_match = re.search(r"(\d+)\s*(?:times?|occurrences?|repeats?)", text, re.I)
        recurrence_count = (
            int(recurrence_match.group(1)) if recurrence_match else (1 if is_recurring else 0)
        )

        # Related incidents
        related_ids: list[str] = []
        for match in re.finditer(r"(INC[- ]?[\w\-]+)", text):
            rid = match.group(1)
            if rid != incident_id:
                related_ids.append(rid)

        return ParsedIncident(
            incident_id=incident_id or ParsedIncident.model_fields["incident_id"].default_factory(),
            title=title,
            description=text,
            severity=severity,
            state=state,
            escalation_level=escalation,
            reported_at=reported_at,
            acknowledged_at=acknowledged_at,
            resolved_at=resolved_at,
            reporter=reporter or "",
            assigned_to=assigned_to,
            affected_services=affected_services,
            tags=tags,
            related_incident_ids=list(set(related_ids)),
            root_cause=root_cause,
            resolution_notes=resolution,
            is_recurring=is_recurring,
            recurrence_count=recurrence_count,
        )

    def _detect_severity(self, text: str) -> IncidentSeverity:
        """Detect incident severity from keywords, checking P1 first."""
        for severity, pattern in _SEVERITY_KEYWORDS.items():
            if pattern.search(text):
                return severity
        return IncidentSeverity.p3

    def _detect_state(self, text: str) -> IncidentState:
        """Detect current incident state from keywords."""
        # Check terminal states first
        for state in (
            IncidentState.closed,
            IncidentState.resolved,
            IncidentState.investigating,
            IncidentState.acknowledged,
            IncidentState.new,
        ):
            if _STATE_KEYWORDS[state].search(text):
                return state
        return IncidentState.new

    def _extract_field(self, text: str, field_name: str) -> str | None:
        """Extract a named field value from text."""
        pattern = _FIELD_PATTERNS.get(field_name)
        if pattern:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        return None

    def _extract_affected_services(self, text: str) -> list[ServiceStateMapping]:
        """Extract affected services and their states."""
        services: list[ServiceStateMapping] = []

        service_match = _AFFECTED_SERVICE_PATTERN.search(text)
        if service_match:
            service_names = [s.strip() for s in service_match.group(1).split(",")]
            for name in service_names:
                if not name:
                    continue
                # Detect service state from context
                state = ServiceState.degraded
                for svc_state, pattern in _SERVICE_STATE_KEYWORDS.items():
                    if pattern.search(text):
                        state = svc_state
                        break

                # Detect customer count
                customers = 0
                count_match = _CUSTOMER_COUNT_PATTERN.search(text)
                if count_match:
                    customers = int(count_match.group(1).replace(",", ""))

                services.append(
                    ServiceStateMapping(
                        service_id=name.lower().replace(" ", "_"),
                        service_name=name,
                        state=state,
                        affected_customers=customers,
                    )
                )

        return services


class TicketParser:
    """Lightweight parser for structured ticket formats (key: value)."""

    def parse_ticket(self, text: str) -> dict[str, str]:
        """Parse a structured ticket into key-value pairs.

        Args:
            text: Ticket text with key: value lines.

        Returns:
            Dictionary of field name to value.
        """
        fields: dict[str, str] = {}
        current_key: str | None = None
        current_value_lines: list[str] = []

        for line in text.split("\n"):
            kv_match = re.match(r"^(\w[\w\s]*?)\s*[:=]\s*(.*)$", line)
            if kv_match:
                # Save previous field
                if current_key:
                    fields[current_key] = "\n".join(current_value_lines).strip()
                current_key = kv_match.group(1).strip().lower().replace(" ", "_")
                current_value_lines = [kv_match.group(2).strip()]
            elif current_key:
                current_value_lines.append(line)

        # Save last field
        if current_key:
            fields[current_key] = "\n".join(current_value_lines).strip()

        return fields
