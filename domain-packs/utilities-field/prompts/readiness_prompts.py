"""Prompt templates for LLM-assisted readiness assessment and dispatch recommendations.

These templates are version-controlled and treated as code. Changes should go
through the standard review process.
"""

READINESS_ASSESSMENT_SYSTEM_PROMPT = """\
You are a field operations readiness analyst specialising in utilities and \
telecom field workforce management. You have deep expertise in:

- Work order scheduling and dispatch optimisation
- Engineer skill matching and competency assessment
- Safety compliance and permit management
- Regulatory requirements for gas, electrical, and height works

Your role is to assess whether a work order is ready for dispatch and provide \
clear, actionable recommendations. Always:

1. Prioritise safety above all other considerations.
2. Verify regulatory compliance (Gas Safe, 18th Edition, IPAF/PASMA, etc.).
3. Consider practical constraints (travel time, equipment, weather).
4. Recommend alternatives when the primary option is blocked.
5. Flag any risks that could affect the engineer or public safety.

Do NOT recommend dispatch if any mandatory safety requirement is unmet. \
If information is insufficient to confirm safety, recommend escalation.
"""

READINESS_EXPLANATION_TEMPLATE = """\
## Readiness Assessment

**Work Order:** {work_order_title} ({work_order_type})
**Engineer:** {engineer_name}
**Status:** {readiness_status}
**Confidence:** {confidence:.0%}

### Skill Fit
- Overall fit: {skill_fit_score:.0%}
- Matched skills: {matched_skills}
- Missing skills: {missing_skills}

### Blockers
{blockers}

### Missing Prerequisites
{missing_prerequisites}

---

Please explain this readiness assessment in plain language suitable for a \
dispatch coordinator. Cover:
1. Whether this work order can be safely dispatched
2. What specific issues need resolution
3. Suggested next steps and alternatives
4. Any time-sensitive considerations
"""

DISPATCH_RECOMMENDATION_TEMPLATE = """\
## Dispatch Recommendation

**Work Order:** {work_order_id} — {work_order_title}
**Type:** {work_order_type}
**Priority:** {priority}
**Site:** {site_address}
**Scheduled:** {scheduled_date} {scheduled_time}

### Engineer Assessment
{engineer_assessment}

### Permits Status
{permits_status}

### Safety Considerations
{safety_notes}

---

Please provide a dispatch recommendation covering:
1. **Go/No-Go Decision**: Can this work order be dispatched now?
2. **Engineer Suitability**: Is the assigned engineer the best fit?
3. **Pre-Dispatch Checklist**: Any final checks before dispatch
4. **On-Site Instructions**: Key safety and operational notes for the engineer
5. **Contingency Plan**: What to do if the engineer encounters unexpected issues
"""
