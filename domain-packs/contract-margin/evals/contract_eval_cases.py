"""Evaluation cases for contract margin domain pack.

Each case provides an input scenario, expected output, and description
to validate the correctness of parsing, billability, and leakage rules.
"""

from __future__ import annotations

CONTRACT_EVAL_CASES: list[dict] = [
    {
        "id": "eval-cm-001",
        "description": "Billable T&M work with matching rate card entry should be approved",
        "input": {
            "event": {
                "event_id": "EVT-001",
                "description": "Network configuration and testing",
                "activity_type": "network_configuration",
                "hours": 8.0,
                "role": "Senior Network Engineer",
                "has_approval": False,
                "sla_met": True,
            },
            "contract": {
                "contract_type": "master_services",
                "billing_category": "time_and_materials",
                "rate_card": [
                    {
                        "role_or_item": "Senior Network Engineer",
                        "rate": 150.0,
                        "currency": "USD",
                        "rate_unit": "hourly",
                    },
                ],
                "clauses": [
                    {
                        "clause_type": "scope",
                        "text": "In scope: network configuration, testing, and deployment activities.",
                    },
                ],
                "billable_events": [],
                "sla_entries": [],
            },
        },
        "expected_output": {
            "billable": True,
            "confidence_min": 0.8,
            "applicable_rate": 150.0,
        },
    },
    {
        "id": "eval-cm-002",
        "description": "Work performed by a role not in the rate card should be flagged as non-billable",
        "input": {
            "event": {
                "event_id": "EVT-002",
                "description": "Administrative support for project coordination",
                "activity_type": "admin_support",
                "hours": 4.0,
                "role": "Administrative Assistant",
                "has_approval": False,
                "sla_met": True,
            },
            "contract": {
                "contract_type": "work_order",
                "billing_category": "time_and_materials",
                "rate_card": [
                    {
                        "role_or_item": "Senior Network Engineer",
                        "rate": 150.0,
                        "currency": "USD",
                        "rate_unit": "hourly",
                    },
                    {
                        "role_or_item": "Project Manager",
                        "rate": 120.0,
                        "currency": "USD",
                        "rate_unit": "hourly",
                    },
                ],
                "clauses": [],
                "billable_events": [],
                "sla_entries": [],
            },
        },
        "expected_output": {
            "billable": False,
            "has_reason_containing": "No matching rate card entry",
        },
    },
    {
        "id": "eval-cm-003",
        "description": "Leakage detection: unbilled completed work should trigger unbilled_work driver",
        "input": {
            "contract": {
                "contract_type": "master_services",
                "billing_category": "time_and_materials",
                "rate_card": [
                    {
                        "role_or_item": "Field Engineer",
                        "rate": 100.0,
                        "currency": "USD",
                        "rate_unit": "hourly",
                    },
                ],
                "penalties": [],
            },
            "work_history": [
                {
                    "entry_id": "WH-001",
                    "description": "Site survey",
                    "role": "Field Engineer",
                    "hours": 6.0,
                    "actual_rate": 100.0,
                    "date": "2025-01-15",
                    "billed": False,
                    "in_original_scope": True,
                },
                {
                    "entry_id": "WH-002",
                    "description": "Equipment install",
                    "role": "Field Engineer",
                    "hours": 8.0,
                    "actual_rate": 100.0,
                    "date": "2025-01-16",
                    "billed": True,
                    "in_original_scope": True,
                },
                {
                    "entry_id": "WH-003",
                    "description": "Post-install testing",
                    "role": "Field Engineer",
                    "hours": 4.0,
                    "actual_rate": 100.0,
                    "date": "2025-01-17",
                    "billed": False,
                    "in_original_scope": True,
                },
            ],
        },
        "expected_output": {
            "has_trigger_driver": "unbilled_work",
            "unbilled_count": 2,
            "estimated_impact_min": 1000.0,
        },
    },
    {
        "id": "eval-cm-004",
        "description": "Contract parser should extract SLA entries from pipe-delimited table",
        "input": {
            "text": (
                "Master Services Agreement\n"
                "Between Acme Corp and TelcoProvider Inc.\n"
                "Effective Date: 2025-01-01\n\n"
                "Section 3.1: Service Level Targets\n"
                "The following SLA targets apply:\n"
                "Network Uptime | 99.95 % | monthly\n"
                "Response Time | 15 minutes | monthly\n"
                "Resolution Time | 4 hours | monthly\n\n"
                "Section 4.1: Rate Card\n"
                "Senior Engineer | USD 150 /hour\n"
                "Junior Engineer | USD 95 /hour\n"
            ),
        },
        "expected_output": {
            "sla_count": 3,
            "rate_card_count": 2,
            "contract_type": "master_services",
            "parties_contain": "Acme Corp",
        },
    },
]
