"""Telco Ops prompt templates."""

INCIDENT_SUMMARY_SYSTEM_PROMPT = """You are an expert telecommunications operations analyst.

Your role is to:
1. Analyze incident details and service states
2. Determine the appropriate next action
3. Recommend relevant runbooks
4. Identify escalation requirements
5. Generate evidence-backed operational notes

Always base your analysis on factual evidence. Return structured JSON."""

NEXT_ACTION_TEMPLATE = """Determine the next best action for this incident.

## Incident Details
{incident_details}

## Current Service State
{service_state}

## Available Runbooks
{runbooks}

## Escalation History
{escalation_history}

Provide:
- next_action: one of [investigate, escalate, dispatch, resolve, monitor, contact_customer, assign_engineer, close]
- owner: who should handle the next action
- rationale: evidence-backed reasoning"""

OPS_NOTE_TEMPLATE = """Generate an operational note for this incident.

## Incident
{incident}

## Analysis
{analysis}

## Recommendations
{recommendations}

Produce a concise operational note covering: summary, next action, runbook reference, and escalation status."""
