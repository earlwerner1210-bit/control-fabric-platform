"""Telco Ops eval cases."""

TELCO_OPS_EVAL_CASES = [
    # ------------------------------------------------------------------
    # 1. P1 auto-escalation
    # ------------------------------------------------------------------
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
    # ------------------------------------------------------------------
    # 2. P3 investigate
    # ------------------------------------------------------------------
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
    # ------------------------------------------------------------------
    # 3. Resolved -> close
    # ------------------------------------------------------------------
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
    # ------------------------------------------------------------------
    # 4. SLA breach -> management escalation for P2
    # ------------------------------------------------------------------
    {
        "name": "sla_breach_management_escalation",
        "domain": "telco_ops",
        "workflow_type": "incident_dispatch_reconcile",
        "description": (
            "P2 incident that has breached its SLA should escalate to management level"
        ),
        "input_payload": {
            "incident": {
                "incident_id": "INC-004",
                "severity": "p2",
                "state": "investigating",
                "affected_services": ["voip_gateway"],
                "assigned_to": "engineering_team",
                "tags": ["sla_breach"],
                "created_at": "2026-03-25T06:00:00Z",
                "timeline": [
                    {"timestamp": "2026-03-25T06:00:00Z", "event_type": "created", "actor": "monitoring", "description": "Incident created"},
                    {"timestamp": "2026-03-25T10:05:00Z", "event_type": "sla_breach", "actor": "system", "description": "SLA breached at 245 min"},
                ],
            },
            "sla_breached": True,
        },
        "expected_output": {
            "escalate": True,
            "escalation_level": "management",
            "escalation_owner": "service_delivery_manager",
        },
    },
    # ------------------------------------------------------------------
    # 5. Runbook matched for incident
    # ------------------------------------------------------------------
    {
        "name": "runbook_matched",
        "domain": "telco_ops",
        "workflow_type": "incident_dispatch_reconcile",
        "description": (
            "An investigating incident with a matching runbook available should "
            "recommend dispatch with the runbook reference"
        ),
        "input_payload": {
            "incident": {
                "incident_id": "INC-005",
                "severity": "p3",
                "state": "investigating",
                "affected_services": ["dns_resolver"],
                "assigned_to": "engineering_team",
                "title": "DNS resolution failures in east region",
                "description": "Intermittent DNS lookup failures reported by multiple customers.",
            },
            "runbooks": [
                {
                    "runbook_id": "RB-DNS-001",
                    "title": "DNS Resolution Failure Runbook",
                    "applicable_services": ["dns_resolver"],
                    "applicable_severity": ["p2", "p3"],
                    "steps": [
                        {"step_number": 1, "action": "Check DNS service health", "expected_result": "Service status returned", "automated": True, "timeout_minutes": 5},
                        {"step_number": 2, "action": "Flush DNS cache", "expected_result": "Cache cleared", "automated": True, "timeout_minutes": 3},
                        {"step_number": 3, "action": "Verify upstream resolvers", "expected_result": "All resolvers responding", "automated": False, "timeout_minutes": 10},
                    ],
                    "estimated_time_minutes": 20,
                    "success_rate": 0.85,
                    "last_updated": "2026-01-15",
                },
            ],
        },
        "expected_output": {
            "next_action": "dispatch",
            "runbook_id": "RB-DNS-001",
            "runbook_applicable": True,
        },
    },
    # ------------------------------------------------------------------
    # 6. Dispatch needed — hardware failure
    # ------------------------------------------------------------------
    {
        "name": "dispatch_needed_hardware",
        "domain": "telco_ops",
        "workflow_type": "incident_dispatch_reconcile",
        "description": (
            "A P1 incident involving hardware failure with service outage should "
            "require on-site dispatch"
        ),
        "input_payload": {
            "incident": {
                "incident_id": "INC-006",
                "severity": "p1",
                "state": "investigating",
                "affected_services": ["core_network"],
                "title": "Core router hardware failure — site B",
                "description": (
                    "Power supply unit failure on core router CR-B-01. "
                    "Remote restart unsuccessful. Hardware replacement required."
                ),
                "tags": ["hardware", "onsite"],
            },
            "service_state": {
                "service_id": "svc-core-network",
                "service_name": "core_network",
                "state": "outage",
                "impact_level": "critical",
                "affected_customers": 12500,
                "dependencies": ["power_infra", "cooling"],
                "recovery_eta_minutes": 120,
            },
        },
        "expected_output": {
            "dispatch_needed": True,
            "hardware_failure_detected": True,
            "severity_requires_onsite": True,
        },
    },
    # ------------------------------------------------------------------
    # 7. Incident / work-order mismatch
    # ------------------------------------------------------------------
    {
        "name": "incident_wo_mismatch",
        "domain": "telco_ops",
        "workflow_type": "incident_dispatch_reconcile",
        "description": (
            "Incident shows resolved but corresponding work order shows in-progress "
            "— reconciliation should flag mismatch"
        ),
        "input_payload": {
            "incident_state": {
                "incident_id": "INC-007",
                "state": "resolved",
                "severity": "p2",
                "assigned_to": "engineer_a",
                "root_cause": "Fiber cut on span 42",
            },
            "work_order_state": {
                "work_order_id": "WO-007",
                "state": "in_progress",
                "assigned_to": "field_tech_b",
                "work_performed": "",
                "created_at": "2026-03-25T08:30:00Z",
            },
        },
        "expected_output": {
            "reconciliation_status": "mismatched",
            "mismatch_fields": ["state", "assigned_to"],
            "has_recommendations": True,
        },
    },
    # ------------------------------------------------------------------
    # 8. Cascading failure — multiple services
    # ------------------------------------------------------------------
    {
        "name": "cascading_failure",
        "domain": "telco_ops",
        "workflow_type": "incident_dispatch_reconcile",
        "description": (
            "P1 incident with multiple affected services where a dependency "
            "chain causes cascading impact should escalate to management"
        ),
        "input_payload": {
            "incident": {
                "incident_id": "INC-008",
                "severity": "p1",
                "state": "investigating",
                "affected_services": ["core_network", "voice_platform", "billing"],
                "title": "Major outage — core network cascading to voice and billing",
                "description": (
                    "Core network failure propagating to dependent voice platform "
                    "and billing systems. Multiple regions affected."
                ),
                "tags": ["cascading", "multi-service"],
            },
            "service_states": [
                {
                    "service_id": "svc-core",
                    "service_name": "core_network",
                    "state": "outage",
                    "impact_level": "critical",
                    "affected_customers": 50000,
                    "dependencies": [],
                },
                {
                    "service_id": "svc-voice",
                    "service_name": "voice_platform",
                    "state": "degraded",
                    "impact_level": "major",
                    "affected_customers": 30000,
                    "dependencies": ["core_network"],
                },
                {
                    "service_id": "svc-billing",
                    "service_name": "billing",
                    "state": "degraded",
                    "impact_level": "major",
                    "affected_customers": 50000,
                    "dependencies": ["core_network"],
                },
            ],
        },
        "expected_output": {
            "escalate": True,
            "escalation_level": "management",
            "cascading_failures_detected": True,
            "affected_service_count": 3,
        },
    },
]
