"""Evaluation cases for telco operations domain pack.

Each case provides an input scenario, expected output, and description
to validate escalation, action, and ownership logic.
"""

from __future__ import annotations

TELCO_EVAL_CASES: list[dict] = [
    {
        "id": "eval-to-001",
        "description": "P1 incident with service outage should auto-escalate to L2",
        "input": {
            "incident": {
                "incident_id": "INC-20260301-001",
                "title": "Core network outage affecting voice services",
                "severity": "p1",
                "state": "new",
                "escalation_level": "l1",
                "reported_at": "2026-03-01T10:00:00Z",
                "assigned_to": "John Smith",
                "affected_services": [
                    {
                        "service_id": "voice_core",
                        "service_name": "Voice Core Network",
                        "state": "outage",
                        "affected_customers": 25000,
                        "region": "North",
                    },
                ],
                "is_recurring": False,
                "recurrence_count": 0,
            },
        },
        "expected_output": {
            "should_escalate": True,
            "min_level": "l2",
            "urgency": "critical",
        },
    },
    {
        "id": "eval-to-002",
        "description": "Recurring P3 incident (3rd occurrence) should escalate to L3 for RCA",
        "input": {
            "incident": {
                "incident_id": "INC-20260315-042",
                "title": "Intermittent packet loss on access network segment",
                "severity": "p3",
                "state": "investigating",
                "escalation_level": "l1",
                "reported_at": "2026-03-15T14:30:00Z",
                "acknowledged_at": "2026-03-15T14:45:00Z",
                "assigned_to": "Alice Chen",
                "affected_services": [
                    {
                        "service_id": "access_network",
                        "service_name": "Access Network",
                        "state": "degraded",
                        "affected_customers": 150,
                        "region": "East",
                    },
                ],
                "is_recurring": True,
                "recurrence_count": 3,
                "related_incident_ids": ["INC-20260210-018", "INC-20260228-033"],
            },
        },
        "expected_output": {
            "should_escalate": True,
            "min_level": "l3",
            "reason_contains": "recurred",
        },
    },
    {
        "id": "eval-to-003",
        "description": "Unassigned P2 incident should have next action to assign owner",
        "input": {
            "incident": {
                "incident_id": "INC-20260320-007",
                "title": "Data service degradation in metro ring",
                "severity": "p2",
                "state": "new",
                "escalation_level": "l1",
                "reported_at": "2026-03-20T08:15:00Z",
                "assigned_to": None,
                "affected_services": [
                    {
                        "service_id": "data_metro",
                        "service_name": "Data Metro Ring",
                        "state": "degraded",
                        "affected_customers": 3200,
                        "region": "Metro",
                    },
                ],
                "is_recurring": False,
                "recurrence_count": 0,
            },
        },
        "expected_output": {
            "action_type": "escalate",
            "action_contains": "assign",
            "priority": "high",
        },
    },
]
