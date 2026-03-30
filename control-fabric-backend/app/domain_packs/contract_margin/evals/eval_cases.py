"""
Evaluation cases for the contract margin domain pack.

Each case is a self-contained scenario with input data and expected outputs
that can be used to validate the billability engine, leakage detection,
penalty analysis, and recovery recommendation logic.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Shared contract fixtures
# ---------------------------------------------------------------------------

_BASE_RATE_CARD = [
    {
        "activity": "Cable Jointing",
        "unit": "each",
        "rate": 350.00,
        "currency": "GBP",
        "effective_from": "2024-01-01",
        "effective_to": "2026-12-31",
        "multipliers": {"overtime": 1.5, "emergency": 2.0},
    },
    {
        "activity": "Overhead Line Repair",
        "unit": "hour",
        "rate": 85.00,
        "currency": "GBP",
        "effective_from": "2024-01-01",
        "effective_to": "2026-12-31",
        "multipliers": {"overtime": 1.5},
    },
    {
        "activity": "Pole Replacement",
        "unit": "each",
        "rate": 1200.00,
        "currency": "GBP",
        "effective_from": "2024-01-01",
        "effective_to": "2026-12-31",
        "multipliers": {},
    },
    {
        "activity": "Duct Installation",
        "unit": "metre",
        "rate": 45.00,
        "currency": "GBP",
        "effective_from": "2024-01-01",
        "effective_to": "2026-12-31",
        "multipliers": {},
    },
    {
        "activity": "Mobilisation",
        "unit": "each",
        "rate": 150.00,
        "currency": "GBP",
        "effective_from": "2024-01-01",
        "effective_to": "2026-12-31",
        "multipliers": {},
    },
    {
        "activity": "Subcontractor Management",
        "unit": "day",
        "rate": 500.00,
        "currency": "GBP",
        "effective_from": "2024-01-01",
        "effective_to": "2026-12-31",
        "multipliers": {},
    },
]

_BASE_SLA_TABLE = [
    {
        "priority": "critical",
        "response_time_hours": 2,
        "resolution_time_hours": 4,
        "availability": 99.9,
        "penalty_percentage": 5.0,
        "measurement_window": "monthly",
    },
    {
        "priority": "high",
        "response_time_hours": 4,
        "resolution_time_hours": 8,
        "availability": 99.5,
        "penalty_percentage": 3.0,
        "measurement_window": "monthly",
    },
    {
        "priority": "medium",
        "response_time_hours": 8,
        "resolution_time_hours": 24,
        "availability": 99.0,
        "penalty_percentage": 1.5,
        "measurement_window": "monthly",
    },
    {
        "priority": "low",
        "response_time_hours": 24,
        "resolution_time_hours": 72,
        "availability": 98.0,
        "penalty_percentage": 0.5,
        "measurement_window": "monthly",
    },
]

_BASE_CONTRACT = {
    "title": "Master Services Agreement — Network Maintenance",
    "document_type": "contract",
    "contract_type": "master_services",
    "parties": ["TelcoCorp Ltd", "FieldServices Inc"],
    "effective_date": "2024-01-01",
    "expiry_date": "2026-12-31",
    "governing_law": "England and Wales",
    "payment_terms": "30 days net",
    "clauses": [
        {
            "id": "CL-001",
            "type": "obligation",
            "text": "The Provider shall complete all cable jointing works within 5 calendar days of work order issuance. Evidence required: photograph, daywork_sheet, signed_approval.",
            "section": "Schedule 3",
            "confidence": 0.95,
            "risk_level": "medium",
        },
        {
            "id": "CL-002",
            "type": "penalty",
            "text": "Failure to meet P1 SLA response time shall result in a penalty of 5% of monthly invoice value, capped at 10000, with a grace period of 1 days and cure period of 3 days.",
            "section": "Schedule 5",
            "confidence": 0.92,
            "risk_level": "high",
        },
        {
            "id": "CL-003",
            "type": "scope",
            "text": "In-scope activities include maintenance, repair, and replacement of existing network assets. New construction and capacity expansion are out of scope.",
            "section": "Schedule 1",
            "confidence": 0.90,
            "risk_level": "medium",
        },
        {
            "id": "CL-004",
            "type": "re_attendance",
            "text": "Re-attendance due to provider fault shall not be billable. Re-attendance due to client instruction or third-party interference is billable at standard rates.",
            "section": "Schedule 4",
            "confidence": 0.88,
            "risk_level": "high",
        },
        {
            "id": "CL-005",
            "type": "billing",
            "text": "All invoices must be accompanied by a completed daywork sheet and photographic evidence of completed work. Invoices without supporting evidence will be rejected.",
            "section": "Schedule 6",
            "confidence": 0.93,
            "risk_level": "medium",
        },
    ],
    "sla_table": _BASE_SLA_TABLE,
    "rate_card": _BASE_RATE_CARD,
    "scope_boundaries": [
        {
            "scope_type": "in_scope",
            "description": "Maintenance, repair, and replacement of existing network assets",
            "activities": [
                "Cable Jointing",
                "Overhead Line Repair",
                "Pole Replacement",
                "Duct Installation",
            ],
            "conditions": [],
        },
        {
            "scope_type": "out_of_scope",
            "description": "New construction and capacity expansion",
            "activities": [
                "New Build Construction",
                "Capacity Expansion",
                "Greenfield Installation",
            ],
            "conditions": [],
        },
        {
            "scope_type": "conditional",
            "description": "Emergency works outside normal hours require pre-approval",
            "activities": ["Emergency Cable Repair"],
            "conditions": ["emergency_authorisation", "incident_reference"],
        },
    ],
}

# ---------------------------------------------------------------------------
# Evaluation cases
# ---------------------------------------------------------------------------

EVAL_CASES: list[dict[str, Any]] = [
    # 1. Clearly billable
    {
        "name": "clearly_billable",
        "domain": "contract_margin",
        "description": (
            "Standard cable jointing activity with all evidence present, "
            "within scope, active rate card, and below approval threshold."
        ),
        "input": {
            "contract": _BASE_CONTRACT,
            "activity": {
                "name": "Cable Jointing",
                "category": "standard",
                "value": 350.00,
                "quantity": 1,
                "scope": "in_scope",
                "evidence": ["photograph", "daywork_sheet", "signed_approval"],
                "hours": 4,
                "daywork_sheet": True,
            },
            "work_orders": [
                {
                    "activity": "Cable Jointing",
                    "status": "completed",
                    "billed": True,
                    "value": 350.00,
                    "reference": "WO-1001",
                },
            ],
            "incidents": [],
            "rate_card": _BASE_RATE_CARD,
        },
        "expected": {
            "verdict": "billable",
            "billable": True,
            "leakage_count": 0,
            "reasons": ["billable"],
        },
    },
    # 2. Missing approval for above-threshold work
    {
        "name": "missing_approval_non_billable",
        "domain": "contract_margin",
        "description": (
            "Pole replacement activity above approval threshold with no approval. "
            "All other evidence is present but the approval rule should fail."
        ),
        "input": {
            "contract": _BASE_CONTRACT,
            "activity": {
                "name": "Pole Replacement",
                "category": "standard",
                "value": 1200.00,
                "quantity": 1,
                "scope": "in_scope",
                "evidence": ["photograph", "daywork_sheet"],
                "hours": 6,
                "daywork_sheet": True,
            },
            "work_orders": [],
            "incidents": [],
            "rate_card": _BASE_RATE_CARD,
            "has_approval": False,
            "approval_threshold": 1000.00,
        },
        "expected": {
            "verdict": "non_billable",
            "billable": False,
            "leakage_count": 0,
            "reasons": ["approval_threshold"],
        },
    },
    # 3. Out of scope work
    {
        "name": "out_of_scope_work",
        "domain": "contract_margin",
        "description": (
            "New Build Construction activity explicitly listed as out of scope. "
            "Should be flagged as non-billable with a scope conflict."
        ),
        "input": {
            "contract": _BASE_CONTRACT,
            "activity": {
                "name": "New Build Construction",
                "category": "standard",
                "value": 5000.00,
                "quantity": 1,
                "scope": "out_of_scope",
                "evidence": ["photograph"],
                "hours": 16,
                "daywork_sheet": True,
            },
            "work_orders": [],
            "incidents": [],
            "rate_card": _BASE_RATE_CARD,
        },
        "expected": {
            "verdict": "non_billable",
            "billable": False,
            "leakage_count": 1,
            "reasons": ["out_of_scope", "no_rate_card"],
        },
    },
    # 4. Under-recovery due to reattendance (provider fault)
    {
        "name": "under_recovery_repeat_effort",
        "domain": "contract_margin",
        "description": (
            "Re-attendance for Cable Jointing due to provider fault. "
            "The repeat visit should not be billable per the re-attendance clause."
        ),
        "input": {
            "contract": _BASE_CONTRACT,
            "activity": {
                "name": "Cable Jointing",
                "category": "standard",
                "value": 350.00,
                "quantity": 1,
                "scope": "in_scope",
                "evidence": ["photograph", "daywork_sheet"],
                "hours": 3,
                "daywork_sheet": True,
                "billed_rate": 0.0,
                "is_reattendance": True,
                "reattendance_cause": "provider_fault",
            },
            "work_orders": [
                {
                    "activity": "Cable Jointing",
                    "status": "completed",
                    "billed": False,
                    "value": 350.00,
                    "reference": "WO-1010",
                },
            ],
            "incidents": [
                {
                    "activity": "Cable Jointing",
                    "cause": "provider_fault",
                    "resolution": "reattendance",
                },
            ],
            "rate_card": _BASE_RATE_CARD,
        },
        "expected": {
            "verdict": "non_billable",
            "billable": False,
            "leakage_count": 1,
            "reasons": ["reattendance_provider_fault", "unbilled_completed_work"],
        },
    },
    # 5. Penalty risk due to SLA breach
    {
        "name": "penalty_risk_sla_breach",
        "domain": "contract_margin",
        "description": (
            "P1 (critical) SLA response time was exceeded, triggering penalty "
            "exposure of 5% of monthly invoice value."
        ),
        "input": {
            "contract": _BASE_CONTRACT,
            "activity": {
                "name": "Cable Jointing",
                "category": "emergency",
                "value": 700.00,
                "quantity": 1,
                "scope": "in_scope",
                "evidence": [
                    "photograph",
                    "daywork_sheet",
                    "signed_approval",
                    "incident_reference",
                ],
                "hours": 5,
                "daywork_sheet": True,
            },
            "work_orders": [],
            "incidents": [],
            "rate_card": _BASE_RATE_CARD,
            "sla_performance": [
                {
                    "clause_id": "CL-002",
                    "trigger": "failure to meet P1 SLA response time",
                    "breached": True,
                    "breach_days": 5,
                    "severity": "critical",
                },
            ],
            "monthly_invoice_value": 100000.00,
        },
        "expected": {
            "verdict": "billable",
            "billable": True,
            "leakage_count": 0,
            "reasons": ["penalty_exposure"],
            "penalty_exposure_gt": 0,
        },
    },
    # 6. Field-valid but commercially invalid (expired rate card)
    {
        "name": "field_valid_commercial_invalid",
        "domain": "contract_margin",
        "description": (
            "Work was completed successfully in the field but the rate card "
            "entry has expired, making it commercially non-billable."
        ),
        "input": {
            "contract": _BASE_CONTRACT,
            "activity": {
                "name": "Cable Jointing",
                "category": "standard",
                "value": 350.00,
                "quantity": 1,
                "scope": "in_scope",
                "evidence": ["photograph", "daywork_sheet", "signed_approval"],
                "hours": 4,
                "daywork_sheet": True,
            },
            "work_orders": [],
            "incidents": [],
            "rate_card": [
                {
                    "activity": "Cable Jointing",
                    "unit": "each",
                    "rate": 350.00,
                    "currency": "GBP",
                    "effective_from": "2022-01-01",
                    "effective_to": "2023-12-31",
                    "multipliers": {},
                },
            ],
            "work_date": "2025-06-15",
        },
        "expected": {
            "verdict": "non_billable",
            "billable": False,
            "leakage_count": 0,
            "reasons": ["expired_rate_card"],
        },
    },
    # 7. Incident-linked non-billable rework
    {
        "name": "incident_linked_non_billable",
        "domain": "contract_margin",
        "description": (
            "Overhead line repair triggered by an incident caused by provider. "
            "Linked incident makes the rework non-billable."
        ),
        "input": {
            "contract": _BASE_CONTRACT,
            "activity": {
                "name": "Overhead Line Repair",
                "category": "standard",
                "value": 340.00,
                "quantity": 4,
                "scope": "in_scope",
                "evidence": ["photograph"],
                "hours": 4,
                "daywork_sheet": False,
                "billed_rate": 85.00,
            },
            "work_orders": [
                {
                    "activity": "Overhead Line Repair",
                    "status": "completed",
                    "billed": False,
                    "value": 340.00,
                    "reference": "WO-2001",
                },
            ],
            "incidents": [
                {
                    "activity": "Overhead Line Repair",
                    "cause": "provider_damage",
                    "resolution": "repair_required",
                },
            ],
            "rate_card": _BASE_RATE_CARD,
        },
        "expected": {
            "verdict": "non_billable",
            "billable": False,
            "leakage_count": 2,
            "reasons": ["missing_daywork_sheet", "unbilled_completed_work"],
        },
    },
    # 8. Insufficient evidence
    {
        "name": "insufficient_evidence",
        "domain": "contract_margin",
        "description": (
            "Cable jointing work completed but daywork sheet is missing. "
            "The evidence rule should fail and leakage should be detected."
        ),
        "input": {
            "contract": _BASE_CONTRACT,
            "activity": {
                "name": "Cable Jointing",
                "category": "standard",
                "value": 350.00,
                "quantity": 1,
                "scope": "in_scope",
                "evidence": ["photograph"],
                "hours": 4,
                "daywork_sheet": False,
            },
            "work_orders": [],
            "incidents": [],
            "rate_card": _BASE_RATE_CARD,
        },
        "expected": {
            "verdict": "non_billable",
            "billable": False,
            "leakage_count": 1,
            "reasons": ["missing_evidence", "missing_daywork_sheet"],
        },
    },
    # 9. Ambiguous scope conflict
    {
        "name": "ambiguous_scope_conflict",
        "domain": "contract_margin",
        "description": (
            "Emergency Cable Repair is conditionally in scope but the required "
            "conditions (emergency_authorisation, incident_reference) are not met."
        ),
        "input": {
            "contract": _BASE_CONTRACT,
            "activity": {
                "name": "Emergency Cable Repair",
                "category": "emergency",
                "value": 700.00,
                "quantity": 1,
                "scope": "conditional",
                "evidence": ["photograph"],
                "hours": 3,
                "daywork_sheet": True,
                "conditions_met": [],
            },
            "work_orders": [],
            "incidents": [],
            "rate_card": _BASE_RATE_CARD,
        },
        "expected": {
            "verdict": "non_billable",
            "billable": False,
            "leakage_count": 1,
            "reasons": ["conditional_scope", "scope_creep_unpriced"],
        },
    },
    # 10. Recovery recommendation scenario
    {
        "name": "recovery_recommendation",
        "domain": "contract_margin",
        "description": (
            "Multiple leakage triggers present: unbilled work, rate under-recovery, "
            "and missing mobilisation charge. Should produce 3+ recovery recommendations."
        ),
        "input": {
            "contract": _BASE_CONTRACT,
            "activity": {
                "name": "Cable Jointing",
                "category": "standard",
                "value": 350.00,
                "quantity": 2,
                "scope": "in_scope",
                "evidence": ["photograph", "daywork_sheet", "signed_approval"],
                "hours": 8,
                "daywork_sheet": True,
                "billed_rate": 300.00,
                "mobilisation_charged": False,
                "materials_cost": 200.00,
                "billed_materials": 0.0,
            },
            "work_orders": [
                {
                    "activity": "Cable Jointing",
                    "status": "completed",
                    "billed": False,
                    "value": 350.00,
                    "reference": "WO-3001",
                },
                {
                    "activity": "Cable Jointing",
                    "status": "completed",
                    "billed": False,
                    "value": 350.00,
                    "reference": "WO-3002",
                },
            ],
            "incidents": [],
            "rate_card": _BASE_RATE_CARD,
        },
        "expected": {
            "verdict": "billable",
            "billable": True,
            "leakage_count": 4,
            "reasons": [
                "unbilled_completed_work",
                "rate_below_contract",
                "mobilisation_not_charged",
                "material_cost_passthrough",
            ],
            "min_recovery_recommendations": 3,
        },
    },
    # 11. Subcontractor margin leak
    {
        "name": "subcontractor_margin_leak",
        "domain": "contract_margin",
        "description": (
            "Subcontractor cost exceeds the billed revenue for pole replacement, "
            "creating a negative margin situation."
        ),
        "input": {
            "contract": _BASE_CONTRACT,
            "activity": {
                "name": "Pole Replacement",
                "category": "standard",
                "value": 1200.00,
                "quantity": 1,
                "scope": "in_scope",
                "evidence": ["photograph", "daywork_sheet", "signed_approval"],
                "hours": 8,
                "daywork_sheet": True,
                "billed_rate": 1200.00,
                "subcontractor_cost": 1500.00,
            },
            "work_orders": [],
            "incidents": [],
            "rate_card": _BASE_RATE_CARD,
        },
        "expected": {
            "verdict": "billable",
            "billable": True,
            "leakage_count": 1,
            "reasons": ["subcontractor_margin_leak"],
        },
    },
    # 12. Warranty period rework
    {
        "name": "warranty_period_rework",
        "domain": "contract_margin",
        "description": (
            "Duct installation rework performed after warranty expiry. "
            "The work should be billable but was not charged."
        ),
        "input": {
            "contract": _BASE_CONTRACT,
            "activity": {
                "name": "Duct Installation",
                "category": "standard",
                "value": 450.00,
                "quantity": 10,
                "scope": "in_scope",
                "evidence": ["photograph", "daywork_sheet"],
                "hours": 6,
                "daywork_sheet": True,
                "billed_rate": 45.00,
                "warranty_expiry": "2025-01-01",
                "work_date": "2025-06-15",
            },
            "work_orders": [],
            "incidents": [],
            "rate_card": _BASE_RATE_CARD,
        },
        "expected": {
            "verdict": "billable",
            "billable": True,
            "leakage_count": 1,
            "reasons": ["warranty_period_rework"],
        },
    },
]


def get_eval_cases() -> list[dict[str, Any]]:
    """Return all evaluation cases."""
    return EVAL_CASES


def get_eval_case_by_name(name: str) -> dict[str, Any] | None:
    """Lookup a single eval case by name."""
    for case in EVAL_CASES:
        if case["name"] == name:
            return case
    return None


def list_eval_case_names() -> list[str]:
    """Return the names of all eval cases."""
    return [case["name"] for case in EVAL_CASES]
