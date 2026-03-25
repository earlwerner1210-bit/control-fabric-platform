"""Telco Ops domain parsers."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.domain_packs.telco_ops.schemas import (
    ImpactLevel,
    IncidentSeverity,
    IncidentState,
    IncidentTimeline,
    OwnershipRuleObject,
    ParsedIncident,
    ParsedRunbook,
    RunbookReferenceObject,
    RunbookStep,
    ServiceState,
    ServiceStateObject,
    TimelineEvent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"p1": 0, "p2": 1, "p3": 2, "p4": 3}

_INCIDENT_CATEGORIES = {
    "network": [
        "network", "latency", "packet loss", "dns", "bgp", "ospf", "routing",
        "firewall", "switch", "router", "bandwidth", "connectivity", "link",
    ],
    "hardware": [
        "hardware", "disk", "cpu", "memory", "power", "fan", "psu",
        "motherboard", "nic", "raid", "drive", "chassis",
    ],
    "software": [
        "software", "application", "crash", "bug", "exception", "error",
        "timeout", "deadlock", "memory leak", "segfault", "core dump",
    ],
    "config": [
        "config", "configuration", "misconfigured", "policy", "acl",
        "certificate", "cert", "ssl", "tls", "credential",
    ],
    "security": [
        "security", "breach", "intrusion", "ddos", "dos", "malware",
        "ransomware", "unauthorized", "vulnerability", "exploit",
    ],
    "capacity": [
        "capacity", "utilization", "threshold", "saturation", "exhaustion",
        "scaling", "overload", "congestion", "queue", "full",
    ],
}

_SYMPTOM_PATTERNS = [
    re.compile(r"(?:experiencing|observing|reporting|seeing|noticed)\s+(.+?)(?:\.|$)", re.IGNORECASE),
    re.compile(r"(?:symptom|issue|problem|failure):\s*(.+?)(?:\.|$)", re.IGNORECASE),
    re.compile(r"(?:unable to|cannot|can't|could not)\s+(.+?)(?:\.|$)", re.IGNORECASE),
    re.compile(r"(?:high|elevated|increased|abnormal|excessive)\s+(.+?)(?:\.|$)", re.IGNORECASE),
    re.compile(r"(?:loss of|no|missing)\s+(.+?)(?:\.|$)", re.IGNORECASE),
]


def _minutes_between(ts1: str, ts2: str) -> int:
    """Best-effort minute diff between two ISO-ish timestamps."""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt1 = datetime.strptime(ts1, fmt).replace(tzinfo=timezone.utc)
            dt2 = datetime.strptime(ts2, fmt).replace(tzinfo=timezone.utc)
            return max(0, int((dt2 - dt1).total_seconds() / 60))
        except (ValueError, TypeError):
            continue
    return 0


# ---------------------------------------------------------------------------
# IncidentParser
# ---------------------------------------------------------------------------


class IncidentParser:
    """Parse incident/ticket documents."""

    def parse_incident(self, text_or_payload: str | dict) -> ParsedIncident:
        if isinstance(text_or_payload, dict):
            return self._from_json(text_or_payload)
        return self._from_text(text_or_payload)

    # -- core parsers -------------------------------------------------------

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
            updated_at=data.get("updated_at", ""),
            timeline=data.get("timeline", []),
            tags=data.get("tags", []),
        )

    def _from_text(self, text: str) -> ParsedIncident:
        inc_id_match = re.search(r"INC[-_]?(\w+)", text)
        severity_match = re.search(r"(P[1-4])", text, re.IGNORECASE)
        title_match = re.search(r"(?:title|subject):\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
        services_match = re.findall(r"(?:service|system):\s*(\S+)", text, re.IGNORECASE)

        return ParsedIncident(
            incident_id=inc_id_match.group(0) if inc_id_match else "unknown",
            title=title_match.group(1).strip() if title_match else "",
            description=text[:1000],
            severity=(
                IncidentSeverity(severity_match.group(1).lower())
                if severity_match
                else IncidentSeverity.p3
            ),
            affected_services=services_match,
        )

    # -- timeline -----------------------------------------------------------

    def extract_timeline(self, data: dict) -> IncidentTimeline:
        """Build a structured ``IncidentTimeline`` from raw event data."""
        raw_events: list[dict] = data.get("timeline", data.get("events", []))
        if not raw_events:
            return IncidentTimeline()

        events: list[TimelineEvent] = []
        for evt in raw_events:
            events.append(
                TimelineEvent(
                    timestamp=evt.get("timestamp", evt.get("time", "")),
                    event_type=evt.get("event_type", evt.get("type", "note")),
                    actor=evt.get("actor", evt.get("user", "system")),
                    description=evt.get("description", evt.get("message", "")),
                    state_change=evt.get("state_change"),
                )
            )

        # Sort chronologically
        events.sort(key=lambda e: e.timestamp)

        # Compute duration
        total_minutes = 0
        if len(events) >= 2:
            total_minutes = _minutes_between(events[0].timestamp, events[-1].timestamp)

        # SLA status heuristic
        sla_status = "within"
        breach_at: str | None = None
        sla_limit = data.get("sla_minutes")
        if sla_limit and total_minutes > sla_limit:
            sla_status = "breached"
            # estimate when breach would have happened
            breach_at = events[0].timestamp  # placeholder — real impl would compute offset
        elif sla_limit and total_minutes > sla_limit * 0.8:
            sla_status = "warning"

        return IncidentTimeline(
            events=events,
            total_duration_minutes=total_minutes,
            sla_status=sla_status,
            breach_at=breach_at,
        )

    # -- symptoms -----------------------------------------------------------

    def extract_symptoms(self, text: str) -> list[str]:
        """Extract symptom descriptions from free-text."""
        symptoms: list[str] = []
        for pattern in _SYMPTOM_PATTERNS:
            for match in pattern.finditer(text):
                symptom = match.group(1).strip().rstrip(".,;")
                if symptom and symptom not in symptoms:
                    symptoms.append(symptom)
        return symptoms

    # -- classification -----------------------------------------------------

    def classify_incident_category(self, text: str) -> str:
        """Categorise incident text into one of the standard categories."""
        text_lower = text.lower()
        scores: dict[str, int] = {}
        for category, keywords in _INCIDENT_CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[category] = score
        if not scores:
            return "unknown"
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    # -- related incidents --------------------------------------------------

    def detect_related_incidents(
        self,
        incident: ParsedIncident,
        history: list[ParsedIncident],
    ) -> list[str]:
        """Return IDs of potentially related incidents from *history*."""
        related: list[str] = []
        for past in history:
            if past.incident_id == incident.incident_id:
                continue
            # same affected services
            shared_services = set(incident.affected_services) & set(past.affected_services)
            if shared_services:
                related.append(past.incident_id)
                continue
            # similar title keywords (jaccard)
            inc_words = set(incident.title.lower().split())
            past_words = set(past.title.lower().split())
            if inc_words and past_words:
                overlap = len(inc_words & past_words) / max(len(inc_words | past_words), 1)
                if overlap >= 0.4:
                    related.append(past.incident_id)
                    continue
            # shared tags
            if set(incident.tags) & set(past.tags):
                related.append(past.incident_id)
        return related

    # -- customer impact ----------------------------------------------------

    def extract_customer_impact(self, data: dict) -> dict:
        """Parse affected customers, services, and revenue impact."""
        return {
            "affected_customers": data.get("affected_customers", data.get("customer_count", 0)),
            "affected_services": data.get("affected_services", []),
            "revenue_impact_usd": data.get("revenue_impact_usd", data.get("revenue_impact", 0)),
            "region": data.get("region", "unknown"),
            "segment": data.get("customer_segment", "unknown"),
            "impact_description": data.get("impact_description", ""),
        }


# ---------------------------------------------------------------------------
# RunbookParser
# ---------------------------------------------------------------------------


class RunbookParser:
    """Parse runbook documents."""

    def parse_runbook(self, text_or_payload: str | dict) -> ParsedRunbook:
        if isinstance(text_or_payload, dict):
            return self._from_json(text_or_payload)
        return ParsedRunbook(
            runbook_id="unknown",
            title="",
            description=text_or_payload[:500] if isinstance(text_or_payload, str) else "",
        )

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

    # -- runbook matching ---------------------------------------------------

    def match_runbook_to_incident(
        self,
        incident: ParsedIncident,
        runbooks: list[RunbookReferenceObject],
    ) -> RunbookReferenceObject | None:
        """Find the best-matching runbook for the given incident.

        Scoring:
        - +3 per overlapping applicable_service
        - +2 if incident severity is in applicable_severity
        - +1 per keyword overlap between incident title/description and runbook title
        """
        if not runbooks:
            return None

        best: RunbookReferenceObject | None = None
        best_score = 0

        for rb in runbooks:
            score = 0
            # service overlap
            shared = set(incident.affected_services) & set(rb.applicable_services)
            score += len(shared) * 3
            # severity match
            if incident.severity.value in rb.applicable_severity:
                score += 2
            # keyword overlap
            inc_words = set((incident.title + " " + incident.description).lower().split())
            rb_words = set(rb.title.lower().split())
            score += len(inc_words & rb_words)

            if score > best_score:
                best_score = score
                best = rb

        if best_score == 0:
            return None
        return best

    # -- automation candidates ----------------------------------------------

    def extract_automation_candidates(self, steps: list[RunbookStep]) -> list[RunbookStep]:
        """Return steps that are flagged or likely candidates for automation."""
        candidates: list[RunbookStep] = []
        automation_keywords = {"restart", "reboot", "ping", "check", "verify", "run", "execute", "clear", "flush"}
        for step in steps:
            if step.automated:
                candidates.append(step)
                continue
            action_lower = step.action.lower()
            if any(kw in action_lower for kw in automation_keywords):
                candidates.append(step)
        return candidates

    # -- applicability validation -------------------------------------------

    def validate_runbook_applicability(
        self,
        runbook: RunbookReferenceObject,
        incident: ParsedIncident,
    ) -> bool:
        """Return True if the runbook is applicable to the incident."""
        # Must share at least one service
        if runbook.applicable_services and incident.affected_services:
            if not set(runbook.applicable_services) & set(incident.affected_services):
                return False
        # Severity must match if runbook constrains it
        if runbook.applicable_severity:
            if incident.severity.value not in runbook.applicable_severity:
                return False
        return True


# ---------------------------------------------------------------------------
# ServiceStateParser
# ---------------------------------------------------------------------------


class ServiceStateParser:
    """Parse and analyse service state information."""

    def parse_service_state(self, data: dict) -> ServiceStateObject:
        """Build a ``ServiceStateObject`` from raw payload."""
        raw_state = data.get("state", data.get("status", "active")).lower()
        state = ServiceState(raw_state) if raw_state in ServiceState.__members__ else ServiceState.active

        raw_impact = data.get("impact_level", "negligible").lower()
        impact = ImpactLevel(raw_impact) if raw_impact in ImpactLevel.__members__ else ImpactLevel.negligible

        return ServiceStateObject(
            service_id=data.get("service_id", data.get("id", "unknown")),
            service_name=data.get("service_name", data.get("name", "")),
            state=state,
            last_state_change=data.get("last_state_change", ""),
            affected_customers=data.get("affected_customers", 0),
            impact_level=impact,
            dependencies=data.get("dependencies", []),
            recovery_eta_minutes=data.get("recovery_eta_minutes"),
        )

    def detect_state_transitions(self, history: list[dict]) -> list[dict]:
        """Identify state transitions from a chronological history list.

        Each item in *history* should have ``state`` and ``timestamp`` keys.
        """
        transitions: list[dict] = []
        prev_state: str | None = None
        for entry in sorted(history, key=lambda e: e.get("timestamp", "")):
            current_state = entry.get("state", "")
            if prev_state is not None and current_state != prev_state:
                transitions.append({
                    "from_state": prev_state,
                    "to_state": current_state,
                    "timestamp": entry.get("timestamp", ""),
                    "reason": entry.get("reason", ""),
                })
            prev_state = current_state
        return transitions

    def detect_cascading_failures(
        self,
        states: list[ServiceStateObject],
    ) -> list[dict]:
        """Detect potential cascading failures across services.

        A cascade is identified when a service is in outage/degraded and
        another service that lists it as a dependency is also degraded/outage.
        """
        # Build lookup: service_name -> state
        state_map: dict[str, ServiceStateObject] = {s.service_name: s for s in states}
        cascades: list[dict] = []

        for svc in states:
            if svc.state not in (ServiceState.outage, ServiceState.degraded):
                continue
            for dep_name in svc.dependencies:
                dep = state_map.get(dep_name)
                if dep and dep.state in (ServiceState.outage, ServiceState.degraded):
                    cascades.append({
                        "affected_service": svc.service_name,
                        "affected_state": svc.state.value,
                        "dependency_service": dep.service_name,
                        "dependency_state": dep.state.value,
                        "impact_level": svc.impact_level.value,
                    })
        return cascades


# ---------------------------------------------------------------------------
# EscalationMatrixParser
# ---------------------------------------------------------------------------


class EscalationMatrixParser:
    """Parse and resolve an escalation / ownership matrix."""

    def parse_matrix(self, data: list[dict]) -> list[OwnershipRuleObject]:
        """Parse a list of raw dicts into ``OwnershipRuleObject`` list."""
        rules: list[OwnershipRuleObject] = []
        for entry in data:
            rules.append(
                OwnershipRuleObject(
                    incident_type=entry.get("incident_type", "general"),
                    severity=entry.get("severity", "p3"),
                    primary_owner=entry.get("primary_owner", "service_desk"),
                    secondary_owner=entry.get("secondary_owner", ""),
                    escalation_chain=entry.get("escalation_chain", []),
                    time_to_own_minutes=entry.get("time_to_own_minutes", 15),
                )
            )
        return rules

    def resolve_owner(
        self,
        incident_type: str,
        severity: str,
        matrix: list[OwnershipRuleObject],
    ) -> str:
        """Find the primary owner for a given incident type + severity.

        Falls back through: exact match -> severity match -> type match -> default.
        """
        # Exact match
        for rule in matrix:
            if rule.incident_type == incident_type and rule.severity == severity:
                return rule.primary_owner
        # Severity-only match
        for rule in matrix:
            if rule.severity == severity:
                return rule.primary_owner
        # Type-only match
        for rule in matrix:
            if rule.incident_type == incident_type:
                return rule.primary_owner
        return "service_desk"
