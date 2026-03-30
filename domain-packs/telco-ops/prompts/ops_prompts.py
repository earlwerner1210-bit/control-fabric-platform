"""Prompt templates for LLM-assisted incident summarisation and ops note generation.

These templates are version-controlled and treated as code. Changes should go
through the standard review process.
"""

INCIDENT_SUMMARY_SYSTEM_PROMPT = """\
You are a telecom operations analyst specialising in incident management and \
service assurance. You have deep expertise in:

- Network incident triage and root cause analysis
- Service level management and SLA tracking
- Escalation procedures and stakeholder communication
- Operational runbooks and standard operating procedures

Your role is to summarise incidents, recommend next actions, and generate \
operational notes for handoff. Always:

1. State the impact clearly: affected services, customer count, duration.
2. Distinguish between symptoms and root causes.
3. Recommend specific, actionable next steps with owners.
4. Reference applicable runbooks when available.
5. Flag SLA risk and escalation requirements.

Be concise and factual. Avoid speculation. If information is insufficient, \
state what is missing.
"""

NEXT_ACTION_TEMPLATE = """\
## Incident Context

**Incident ID:** {incident_id}
**Title:** {title}
**Severity:** {severity}
**State:** {state}
**Duration:** {duration_minutes:.0f} minutes
**Assigned To:** {assigned_to}

### Affected Services
{affected_services}

### Timeline
{timeline}

### Current Investigation Notes
{investigation_notes}

---

Based on the above context, recommend the next action. Include:
1. **Action**: Specific step to take (be precise)
2. **Owner**: Who should execute this action
3. **Priority**: How urgent is this (critical/high/normal/low)
4. **Runbook**: Reference any applicable runbook
5. **Rationale**: Why this is the right next step
"""

OPS_NOTE_TEMPLATE = """\
## Operational Note

**Incident:** {incident_id} — {title}
**Severity:** {severity} | **State:** {state}
**Author:** {author}
**Generated:** {generated_at}

### Summary
{summary}

### Service Impact
{service_state_explanation}

### Next Action
- **Action:** {next_action}
- **Owner:** {next_action_owner}
- **Priority:** {next_action_priority}
- **Est. Time:** {estimated_minutes} minutes

### Escalation
{escalation_status}

### Runbook Reference
{runbook_ref}

---

Please review this operational note and provide:
1. Any corrections to the summary or impact assessment
2. Additional context from related incidents
3. Confidence level in the recommended next action
4. Any risks or dependencies not captured above
"""
