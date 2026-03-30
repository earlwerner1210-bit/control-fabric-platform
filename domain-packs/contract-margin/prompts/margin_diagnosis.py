"""Prompt templates for LLM-assisted margin diagnosis and billability explanation.

These templates are version-controlled and treated as code. Changes should go
through the standard review process.
"""

MARGIN_DIAGNOSIS_SYSTEM_PROMPT = """\
You are a telecom margin assurance analyst specialising in contract intelligence \
and revenue leakage detection. You have deep expertise in:

- Master Services Agreements (MSAs) and associated work/change orders
- Rate card analysis and billability assessment
- SLA compliance and penalty exposure
- Scope management and change order governance

Your role is to analyse contract data, work history, and identified leakage \
triggers to produce clear, actionable margin diagnoses. Always:

1. Ground your analysis in specific contract clauses and evidence.
2. Quantify financial impact wherever possible.
3. Prioritise recommendations by recovery potential.
4. Use precise, professional language suitable for executive stakeholders.
5. Flag any data gaps that limit your analysis confidence.

Do NOT speculate beyond the provided data. If information is insufficient, \
state what additional data is needed.
"""

MARGIN_DIAGNOSIS_USER_TEMPLATE = """\
## Contract Summary
{contract_summary}

## Work History
{work_history}

## Identified Leakage Triggers
{leakage_triggers}

## Question
{question}

---

Please provide a structured margin diagnosis covering:
1. **Verdict**: Overall margin health (healthy / at_risk / leaking / critical)
2. **Key Findings**: Numbered list of specific leakage instances with evidence
3. **Financial Impact**: Quantified impact per finding and total
4. **Recovery Recommendations**: Prioritised actions with estimated recovery
5. **Risk Factors**: Ongoing risks and mitigation suggestions
"""

BILLABILITY_EXPLANATION_TEMPLATE = """\
## Billability Assessment

**Event**: {event_description}
**Contract**: {contract_title} ({contract_type})
**Decision**: {billable_decision}
**Confidence**: {confidence:.0%}

### Rule Results
{rule_results}

### Evidence
{evidence}

---

Please explain this billability decision in plain language suitable for a \
project manager. Cover:
1. Why the event is or is not billable
2. Which contract clauses support this determination
3. What actions could change the outcome (if not billable)
4. Any risks to be aware of
"""

RECOVERY_RECOMMENDATION_TEMPLATE = """\
## Recovery Recommendation

**Leakage Driver**: {driver}
**Estimated Leakage**: {currency} {estimated_leakage:,.2f}
**Priority**: {priority}

### Context
{context}

### Evidence
{evidence}

---

Please draft a detailed recovery recommendation covering:
1. **Immediate Actions**: Steps to take within the next 5 business days
2. **Documentation Required**: Specific documents or approvals needed
3. **Stakeholder Communication**: Who to engage and suggested talking points
4. **Timeline**: Realistic timeline for recovery
5. **Risk of Non-Action**: What happens if this is not addressed
"""
