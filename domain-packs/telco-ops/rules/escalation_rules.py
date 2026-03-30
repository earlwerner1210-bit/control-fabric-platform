"""Escalation rule engine for telecom incident management.

Determines when and how incidents should be escalated based on severity,
SLA timing, recurrence patterns, and cross-domain impact.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..schemas.telco_schemas import (
    EscalationDecision,
    ParsedIncident,
    ServiceStateMapping,
)
from ..taxonomy.telco_taxonomy import (
    EscalationLevel,
    IncidentSeverity,
    IncidentState,
    ServiceState,
)


class EscalationRuleEngine:
    """Evaluates incident data to determine appropriate escalation level.

    Rules:
    - severity_escalation: P1/P2 incidents auto-escalate
    - sla_breach_escalation: Escalate when SLA targets are at risk or breached
    - repeated_incident: Recurring incidents escalate for root cause analysis
    - cross_domain_impact: Incidents affecting multiple services escalate
    """

    def evaluate(
        self,
        incident: ParsedIncident,
        service_states: list[ServiceStateMapping] | None = None,
        current_time: datetime | None = None,
    ) -> EscalationDecision:
        """Run all escalation rules and return the highest required escalation.

        Args:
            incident: The incident to evaluate.
            service_states: Current state of related services.
            current_time: Override for current time (for testing).

        Returns:
            EscalationDecision with the recommended escalation level and reasoning.
        """
        now = current_time or datetime.now(UTC)
        service_states = service_states or [s for s in incident.affected_services]

        decisions: list[EscalationDecision] = []

        sev_decision = self._severity_escalation(incident)
        if sev_decision:
            decisions.append(sev_decision)

        sla_decision = self._sla_breach_escalation(incident, now)
        if sla_decision:
            decisions.append(sla_decision)

        recur_decision = self._repeated_incident(incident)
        if recur_decision:
            decisions.append(recur_decision)

        cross_decision = self._cross_domain_impact(incident, service_states)
        if cross_decision:
            decisions.append(cross_decision)

        if not decisions:
            return EscalationDecision(
                level=incident.escalation_level,
                reason="No escalation required. Current level is appropriate.",
                evidence_ids=[incident.incident_id],
                should_escalate=False,
            )

        # Pick the highest escalation level
        decisions.sort(key=lambda d: d.level.numeric_level, reverse=True)
        highest = decisions[0]

        # Combine reasons if multiple rules triggered
        if len(decisions) > 1:
            all_reasons = "; ".join(d.reason for d in decisions)
            all_evidence = []
            for d in decisions:
                all_evidence.extend(d.evidence_ids)
            highest = EscalationDecision(
                level=highest.level,
                owner=highest.owner,
                reason=all_reasons,
                evidence_ids=list(set(all_evidence)),
                urgency=highest.urgency,
                should_escalate=highest.level.is_higher_than(incident.escalation_level),
            )
        else:
            highest.should_escalate = highest.level.is_higher_than(incident.escalation_level)

        return highest

    def _severity_escalation(
        self,
        incident: ParsedIncident,
    ) -> EscalationDecision | None:
        """P1 incidents escalate to L2 minimum; P2 with outage to L2."""
        if incident.severity == IncidentSeverity.p1:
            return EscalationDecision(
                level=EscalationLevel.l2,
                reason="P1 incident requires automatic escalation to L2 (senior engineer).",
                evidence_ids=[incident.incident_id],
                urgency="critical",
            )

        if incident.severity == IncidentSeverity.p2:
            has_outage = any(s.state == ServiceState.outage for s in incident.affected_services)
            if has_outage:
                return EscalationDecision(
                    level=EscalationLevel.l2,
                    reason="P2 incident with active service outage requires L2 escalation.",
                    evidence_ids=[incident.incident_id],
                    urgency="urgent",
                )

        return None

    def _sla_breach_escalation(
        self,
        incident: ParsedIncident,
        now: datetime,
    ) -> EscalationDecision | None:
        """Escalate when SLA response or resolution targets are at risk."""
        if not incident.reported_at:
            return None

        reported = incident.reported_at
        if reported.tzinfo is None:
            reported = reported.replace(tzinfo=UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        elapsed_minutes = (now - reported).total_seconds() / 60
        resolution_target = incident.severity.sla_resolution_minutes
        response_target = incident.severity.sla_response_minutes

        # Check if response SLA is about to breach (unacknowledged)
        if incident.state == IncidentState.new and not incident.acknowledged_at:
            if elapsed_minutes > response_target * 0.75:
                return EscalationDecision(
                    level=EscalationLevel.l2,
                    reason=(
                        f"Response SLA at {elapsed_minutes / response_target:.0%} elapsed "
                        f"({elapsed_minutes:.0f}/{response_target} min) and incident unacknowledged."
                    ),
                    evidence_ids=[incident.incident_id],
                    urgency="urgent",
                )

        # Check resolution SLA
        if incident.state.is_active:
            pct_elapsed = elapsed_minutes / resolution_target if resolution_target > 0 else 1.0

            if pct_elapsed >= 1.0:
                return EscalationDecision(
                    level=EscalationLevel.l3,
                    reason=(
                        f"Resolution SLA BREACHED: {elapsed_minutes:.0f}/{resolution_target} minutes "
                        f"({pct_elapsed:.0%}). Immediate escalation to L3 required."
                    ),
                    evidence_ids=[incident.incident_id],
                    urgency="critical",
                )
            elif pct_elapsed >= 0.75:
                return EscalationDecision(
                    level=EscalationLevel.l3,
                    reason=(
                        f"Resolution SLA at {pct_elapsed:.0%}: {elapsed_minutes:.0f}/{resolution_target} minutes. "
                        f"Escalating to L3 to prevent breach."
                    ),
                    evidence_ids=[incident.incident_id],
                    urgency="urgent",
                )
            elif pct_elapsed >= 0.5:
                return EscalationDecision(
                    level=EscalationLevel.l2,
                    reason=(
                        f"Resolution SLA at {pct_elapsed:.0%}: {elapsed_minutes:.0f}/{resolution_target} minutes. "
                        f"Escalating to L2 for additional support."
                    ),
                    evidence_ids=[incident.incident_id],
                    urgency="normal",
                )

        return None

    def _repeated_incident(
        self,
        incident: ParsedIncident,
    ) -> EscalationDecision | None:
        """Recurring incidents escalate for root cause analysis."""
        if not incident.is_recurring:
            return None

        if incident.recurrence_count >= 3:
            return EscalationDecision(
                level=EscalationLevel.l3,
                reason=(
                    f"Incident has recurred {incident.recurrence_count} times. "
                    f"Escalating to L3 for root cause analysis and permanent fix."
                ),
                evidence_ids=[incident.incident_id] + incident.related_incident_ids,
                urgency="urgent",
            )

        if incident.recurrence_count >= 2:
            return EscalationDecision(
                level=EscalationLevel.l2,
                reason=(
                    f"Incident has recurred {incident.recurrence_count} times. "
                    f"Escalating to L2 for deeper investigation."
                ),
                evidence_ids=[incident.incident_id] + incident.related_incident_ids,
                urgency="normal",
            )

        return None

    def _cross_domain_impact(
        self,
        incident: ParsedIncident,
        service_states: list[ServiceStateMapping],
    ) -> EscalationDecision | None:
        """Incidents affecting multiple services or large customer bases escalate."""
        impacted_services = [s for s in service_states if s.state.is_impacted]
        total_customers = sum(s.affected_customers for s in impacted_services)

        if len(impacted_services) >= 3:
            return EscalationDecision(
                level=EscalationLevel.management,
                owner="Operations Director",
                reason=(
                    f"Cross-domain impact: {len(impacted_services)} services affected "
                    f"({total_customers:,} customers). Management escalation required."
                ),
                evidence_ids=[s.service_id for s in impacted_services],
                urgency="critical",
            )

        if total_customers >= 10000:
            return EscalationDecision(
                level=EscalationLevel.management,
                owner="Operations Director",
                reason=(
                    f"High customer impact: {total_customers:,} customers affected. "
                    f"Management escalation required."
                ),
                evidence_ids=[s.service_id for s in impacted_services],
                urgency="critical",
            )

        if total_customers >= 1000:
            return EscalationDecision(
                level=EscalationLevel.l3,
                reason=(
                    f"Significant customer impact: {total_customers:,} customers affected. "
                    f"L3 escalation recommended."
                ),
                evidence_ids=[s.service_id for s in impacted_services],
                urgency="urgent",
            )

        return None
