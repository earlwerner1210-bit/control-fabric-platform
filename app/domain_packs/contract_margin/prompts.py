"""Contract & Margin prompt templates."""

MARGIN_DIAGNOSIS_SYSTEM_PROMPT = """You are an expert commercial analyst specializing in contract margin assurance.

Your role is to:
1. Analyze contract terms, obligations, and rate structures
2. Identify revenue leakage patterns
3. Assess billability of work activities
4. Detect penalty exposure
5. Recommend recovery actions

Always base your analysis on the provided evidence. Never speculate beyond the data.
Return your response as structured JSON matching the requested output schema."""

MARGIN_DIAGNOSIS_USER_TEMPLATE = """Analyze the following contract and work history for margin issues.

## Contract Summary
{contract_summary}

## Work History
{work_history}

## Detected Leakage Triggers
{leakage_triggers}

## Question
{question}

Provide a structured analysis with:
- verdict: one of [billable, non_billable, under_recovery, penalty_risk, unknown]
- leakage_drivers: list of identified leakage causes
- recovery_recommendations: list of actionable recovery steps
- executive_summary: brief narrative summary
- confidence: float between 0 and 1"""

BILLABILITY_EXPLANATION_TEMPLATE = """Given the following contract rate card and work activity, explain the billability determination.

## Rate Card
{rate_card}

## Activity
{activity}

## Preliminary Decision
{decision}

Explain why this activity is or is not billable, citing specific contract terms."""

RECOVERY_RECOMMENDATION_TEMPLATE = """Based on the following leakage analysis, provide recovery recommendations.

## Leakage Triggers
{triggers}

## Contract Context
{contract_context}

Provide specific, actionable recommendations to recover lost revenue or mitigate ongoing leakage."""
