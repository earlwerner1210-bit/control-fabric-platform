"""Telco Ops eval cases."""

TELCO_OPS_EVAL_CASES = [
    {
        "name": "p1_auto_escalate",
        "domain": "telco_ops",
        "workflow_type": "incident_dispatch_reconcile",
        "description": "P1 incident should trigger automatic L3 escalation",
        "input_payload": {
            "incident": {
                "incident_id": "INC-001",
                "severity": "p1",
                "state": "new",
                "affected_services": ["core_network"],
            },
        },
        "expected_output": {
            "escalate": True,
            "escalation_level": "l3",
            "next_action": "escalate",
        },
    },
    {
        "name": "p3_investigate",
        "domain": "telco_ops",
        "workflow_type": "incident_dispatch_reconcile",
        "description": "P3 incident should start investigation",
        "input_payload": {
            "incident": {
                "incident_id": "INC-002",
                "severity": "p3",
                "state": "new",
                "affected_services": ["email"],
            },
        },
        "expected_output": {
            "escalate": False,
            "next_action": "investigate",
        },
    },
    {
        "name": "resolved_close",
        "domain": "telco_ops",
        "workflow_type": "incident_dispatch_reconcile",
        "description": "Resolved incident should recommend closure",
        "input_payload": {
            "incident": {
                "incident_id": "INC-003",
                "severity": "p4",
                "state": "resolved",
                "affected_services": [],
            },
        },
        "expected_output": {
            "next_action": "close",
        },
    },
]
