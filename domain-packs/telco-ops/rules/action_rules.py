"""Action rule engine for determining next actions on telecom incidents.

Evaluates current incident and service state to recommend the next action,
including state transitions, runbook application, and owner assignment.
"""

from __future__ import annotations

from ..schemas.telco_schemas import (
    NextAction,
    ParsedIncident,
    ParsedRunbook,
    RunbookRecommendation,
    ServiceStateMapping,
)
from ..taxonomy.telco_taxonomy import (
    IncidentSeverity,
    IncidentState,
    ServiceState,
)


class ActionRuleEngine:
    """Determines the next recommended action for an incident based on
    current state, service state, and available runbooks.

    Rules:
    - valid_state_transition: Recommend the next valid state transition
    - runbook_available: Recommend applicable runbook if one exists
    - owner_assigned: Ensure an owner is assigned
    """

    def evaluate(
        self,
        incident: ParsedIncident,
        service_states: list[ServiceStateMapping] | None = None,
        available_runbooks: list[ParsedRunbook] | None = None,
    ) -> NextAction:
        """Determine the next action for an incident.

        Args:
            incident: The current incident.
            service_states: Current service states.
            available_runbooks: Available runbooks to match against.

        Returns:
            NextAction with recommended action and rationale.
        """
        service_states = service_states or incident.affected_services
        available_runbooks = available_runbooks or []

        # Rule 1: Check if owner is assigned
        owner_action = self._owner_assigned(incident)
        if owner_action:
            return owner_action

        # Rule 2: Determine next state transition
        transition_action = self._valid_state_transition(incident, service_states)

        # Rule 3: Check for applicable runbook
        runbook_rec = self._runbook_available(incident, available_runbooks)

        # Combine: if we have a runbook, enhance the transition action
        if runbook_rec and transition_action:
            transition_action.runbook_ref = runbook_rec.runbook_id
            transition_action.estimated_minutes = runbook_rec.estimated_resolution_minutes
            transition_action.rationale += (
                f" Recommended runbook: '{runbook_rec.runbook_title}' "
                f"(relevance: {runbook_rec.relevance_score:.0%})."
            )
        elif runbook_rec and not transition_action:
            return NextAction(
                action=f"Apply runbook: {runbook_rec.runbook_title}",
                action_type="investigate",
                owner=incident.assigned_to,
                priority=self._severity_to_priority(incident.severity),
                runbook_ref=runbook_rec.runbook_id,
                estimated_minutes=runbook_rec.estimated_resolution_minutes,
                rationale=(
                    f"Applicable runbook found with {runbook_rec.relevance_score:.0%} relevance. "
                    f"Matching criteria: {', '.join(runbook_rec.matching_criteria)}."
                ),
            )

        if transition_action:
            return transition_action

        # Fallback
        return NextAction(
            action="Continue monitoring incident. No specific action required at this time.",
            action_type="investigate",
            owner=incident.assigned_to,
            priority="normal",
            rationale="Incident is in progress with no immediate action triggers.",
        )

    def _valid_state_transition(
        self,
        incident: ParsedIncident,
        service_states: list[ServiceStateMapping],
    ) -> NextAction | None:
        """Recommend the next valid state transition."""
        valid_next = incident.state.valid_transitions()
        if not valid_next:
            return None

        current = incident.state
        priority = self._severity_to_priority(incident.severity)

        if current == IncidentState.new:
            return NextAction(
                action="Acknowledge the incident and begin initial assessment.",
                action_type="investigate",
                owner=incident.assigned_to,
                priority=priority,
                rationale="Incident is in 'new' state and needs acknowledgement to start SLA clock.",
            )

        if current == IncidentState.acknowledged:
            return NextAction(
                action="Begin investigation. Identify affected services and potential root cause.",
                action_type="investigate",
                owner=incident.assigned_to,
                priority=priority,
                rationale="Incident is acknowledged. Next step is active investigation.",
            )

        if current == IncidentState.investigating:
            # Check if services are restored
            all_restored = (
                all(
                    s.state in (ServiceState.active, ServiceState.maintenance)
                    for s in service_states
                )
                if service_states
                else False
            )

            if all_restored or incident.root_cause:
                return NextAction(
                    action="Mark incident as resolved. Document root cause and resolution.",
                    action_type="resolve",
                    owner=incident.assigned_to,
                    priority=priority,
                    rationale=(
                        "Services have been restored or root cause identified. "
                        "Document findings and resolve."
                    ),
                )
            else:
                return NextAction(
                    action="Continue investigation. Focus on root cause identification.",
                    action_type="investigate",
                    owner=incident.assigned_to,
                    priority=priority,
                    rationale="Investigation in progress. Services still impacted.",
                )

        if current == IncidentState.resolved:
            return NextAction(
                action="Verify resolution with affected parties and close the incident.",
                action_type="resolve",
                owner=incident.assigned_to,
                priority="normal",
                rationale="Incident is resolved. Confirm with stakeholders before closing.",
            )

        return None

    def _runbook_available(
        self,
        incident: ParsedIncident,
        runbooks: list[ParsedRunbook],
    ) -> RunbookRecommendation | None:
        """Find the most relevant runbook for the incident."""
        if not runbooks:
            return None

        best_match: RunbookRecommendation | None = None
        best_score = 0.0

        for rb in runbooks:
            score = 0.0
            criteria: list[str] = []

            # Severity match
            if incident.severity in rb.applicable_severity:
                score += 0.3
                criteria.append(f"severity {incident.severity.value} match")

            # Service match
            affected_names = {s.service_name.lower() for s in incident.affected_services}
            rb_services = {s.lower() for s in rb.applicable_services}
            service_overlap = affected_names & rb_services
            if service_overlap:
                score += 0.4
                criteria.append(f"service match: {', '.join(service_overlap)}")

            # Tag/keyword match
            incident_tags = set(t.lower() for t in incident.tags)
            rb_tags = set(t.lower() for t in rb.tags)
            tag_overlap = incident_tags & rb_tags
            if tag_overlap:
                score += 0.2
                criteria.append(f"tag match: {', '.join(tag_overlap)}")

            # Title similarity (simple keyword overlap)
            incident_words = set(incident.title.lower().split())
            rb_words = set(rb.title.lower().split())
            word_overlap = incident_words & rb_words - {
                "the",
                "a",
                "an",
                "is",
                "in",
                "on",
                "for",
                "of",
            }
            if len(word_overlap) >= 2:
                score += 0.1
                criteria.append(f"title keyword match: {', '.join(word_overlap)}")

            if score > best_score and score >= 0.3:
                best_score = score
                best_match = RunbookRecommendation(
                    runbook_id=rb.runbook_id,
                    runbook_title=rb.title,
                    relevance_score=min(1.0, round(score, 2)),
                    matching_criteria=criteria,
                    estimated_resolution_minutes=rb.estimated_total_minutes,
                )

        return best_match

    def _owner_assigned(
        self,
        incident: ParsedIncident,
    ) -> NextAction | None:
        """Check if the incident has an assigned owner."""
        if incident.state.is_active and not incident.assigned_to:
            priority = self._severity_to_priority(incident.severity)
            return NextAction(
                action="Assign an owner to this incident immediately.",
                action_type="escalate",
                owner=None,
                priority=priority,
                rationale=(
                    f"{incident.severity.value.upper()} incident has no assigned owner. "
                    f"An owner must be assigned before investigation can proceed."
                ),
            )
        return None

    def _severity_to_priority(self, severity: IncidentSeverity) -> str:
        """Map incident severity to action priority."""
        return {
            IncidentSeverity.p1: "critical",
            IncidentSeverity.p2: "high",
            IncidentSeverity.p3: "normal",
            IncidentSeverity.p4: "low",
        }.get(severity, "normal")
