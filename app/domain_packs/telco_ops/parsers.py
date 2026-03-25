"""Telco Ops domain parsers."""

from __future__ import annotations

import re

from app.domain_packs.telco_ops.schemas import (
    IncidentSeverity,
    IncidentState,
    ParsedIncident,
    ParsedRunbook,
)


class IncidentParser:
    """Parse incident/ticket documents."""

    def parse_incident(self, text_or_payload: str | dict) -> ParsedIncident:
        if isinstance(text_or_payload, dict):
            return self._from_json(text_or_payload)
        return self._from_text(text_or_payload)

    def _from_json(self, data: dict) -> ParsedIncident:
        severity = data.get("severity", "p3").lower()
        state = data.get("state", data.get("status", "new")).lower()
        return ParsedIncident(
            incident_id=data.get("incident_id", data.get("id", "unknown")),
            title=data.get("title", ""),
            description=data.get("description", ""),
            severity=IncidentSeverity(severity) if severity in IncidentSeverity.__members__ else IncidentSeverity.p3,
            state=IncidentState(state) if state in IncidentState.__members__ else IncidentState.new,
            affected_services=data.get("affected_services", []),
            reported_by=data.get("reported_by", ""),
            assigned_to=data.get("assigned_to", ""),
            created_at=data.get("created_at", ""),
            timeline=data.get("timeline", []),
            tags=data.get("tags", []),
        )

    def _from_text(self, text: str) -> ParsedIncident:
        inc_id_match = re.search(r'INC[-_]?(\w+)', text)
        severity_match = re.search(r'(P[1-4])', text, re.IGNORECASE)
        return ParsedIncident(
            incident_id=inc_id_match.group(0) if inc_id_match else "unknown",
            description=text[:1000],
            severity=IncidentSeverity(severity_match.group(1).lower()) if severity_match else IncidentSeverity.p3,
        )


class RunbookParser:
    """Parse runbook documents."""

    def parse_runbook(self, text_or_payload: str | dict) -> ParsedRunbook:
        if isinstance(text_or_payload, dict):
            return self._from_json(text_or_payload)
        return ParsedRunbook(runbook_id="unknown", title="", description=text_or_payload[:500] if isinstance(text_or_payload, str) else "")

    def _from_json(self, data: dict) -> ParsedRunbook:
        return ParsedRunbook(
            runbook_id=data.get("runbook_id", data.get("id", "unknown")),
            title=data.get("title", ""),
            description=data.get("description", ""),
            applicable_services=data.get("applicable_services", []),
            steps=data.get("steps", []),
            decision_points=data.get("decision_points", []),
            escalation_criteria=data.get("escalation_criteria", []),
            estimated_resolution_minutes=data.get("estimated_resolution_minutes", 0),
        )
