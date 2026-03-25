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
    # ==================================================================
    # Vodafone UK managed-services eval cases
    # ==================================================================
    # ------------------------------------------------------------------
    # 9. Vodafone P1 core network outage
    # ------------------------------------------------------------------
    {
        "name": "vodafone_p1_core_network_outage",
        "domain": "telco_ops",
        "workflow_type": "vodafone_managed_services",
        "description": (
            "P1 core network outage should trigger L3 escalation with bridge call, "
            "MIM process activation, and field dispatch"
        ),
        "input_payload": {
            "incident": {
                "incident_id": "VF-INC-001",
                "severity": "p1",
                "state": "new",
                "title": "Core MSC failure — London region complete outage",
                "description": (
                    "MSC-LON-01 has suffered a total failure. All voice calls in "
                    "the London region are failing. HLR lookup timeouts observed. "
                    "Approximately 250,000 subscribers affected."
                ),
                "affected_services": ["core_network", "voice_platform"],
                "tags": ["outage", "major_incident"],
                "created_at": "2026-03-25T02:15:00Z",
            },
            "service_domain": "core_network",
            "sla_status": {
                "response_sla": "within",
                "resolution_sla": "within",
                "update_overdue": False,
                "minutes_to_breach": 225,
                "bridge_call_required": True,
            },
        },
        "expected_output": {
            "escalate": True,
            "escalation_level": "management",
            "bridge_call_required": True,
            "dispatch_needed": True,
            "next_action": "dispatch",
        },
    },
    # ------------------------------------------------------------------
    # 10. Vodafone P2 RAN degradation
    # ------------------------------------------------------------------
    {
        "name": "vodafone_p2_ran_degradation",
        "domain": "telco_ops",
        "workflow_type": "vodafone_managed_services",
        "description": (
            "P2 RAN degradation without full outage should trigger L2 escalation "
            "and remote remediation first"
        ),
        "input_payload": {
            "incident": {
                "incident_id": "VF-INC-002",
                "severity": "p2",
                "state": "investigating",
                "title": "eNodeB sector degradation — Birmingham cluster",
                "description": (
                    "Multiple eNodeB sectors in Birmingham showing elevated RSSI "
                    "and throughput degradation. Suspected radio interference. "
                    "Approx 15,000 subscribers experiencing poor data speeds."
                ),
                "affected_services": ["ran_radio"],
                "tags": [],
                "created_at": "2026-03-25T08:30:00Z",
            },
            "service_domain": "ran_radio",
            "sla_status": {
                "response_sla": "within",
                "resolution_sla": "within",
                "update_overdue": False,
                "minutes_to_breach": 420,
                "bridge_call_required": False,
            },
        },
        "expected_output": {
            "escalate": True,
            "escalation_level": "l2",
            "next_action": "remote_remediation",
            "dispatch_needed": False,
        },
    },
    # ------------------------------------------------------------------
    # 11. Vodafone P1 SLA breached
    # ------------------------------------------------------------------
    {
        "name": "vodafone_p1_sla_breached",
        "domain": "telco_ops",
        "workflow_type": "vodafone_managed_services",
        "description": (
            "P1 incident with 5 hours elapsed exceeds 4-hour resolution SLA — "
            "should trigger management escalation"
        ),
        "input_payload": {
            "incident": {
                "incident_id": "VF-INC-003",
                "severity": "p1",
                "state": "investigating",
                "title": "GGSN data plane failure — nationwide impact",
                "description": (
                    "GGSN-CORE-01 data plane failure causing nationwide mobile "
                    "data connectivity issues. Investigation ongoing for 5 hours "
                    "without resolution. Vendor engaged."
                ),
                "affected_services": ["core_network"],
                "assigned_to": "senior_engineering",
                "tags": ["outage", "major_incident"],
                "created_at": "2026-03-25T01:00:00Z",
                "timeline": [
                    {"timestamp": "2026-03-25T01:00:00Z", "event_type": "created", "actor": "monitoring", "description": "Incident auto-created by NMS"},
                    {"timestamp": "2026-03-25T01:10:00Z", "event_type": "acknowledged", "actor": "noc_operator", "description": "Acknowledged by NOC"},
                    {"timestamp": "2026-03-25T01:30:00Z", "event_type": "escalation", "actor": "system", "description": "Escalated to L3"},
                    {"timestamp": "2026-03-25T06:00:00Z", "event_type": "sla_breach", "actor": "system", "description": "Resolution SLA breached at 300 min"},
                ],
            },
            "service_domain": "core_network",
            "sla_status": {
                "response_sla": "within",
                "resolution_sla": "breached",
                "update_overdue": True,
                "minutes_to_breach": 0,
                "bridge_call_required": True,
            },
            "current_time_minutes": 300,
        },
        "expected_output": {
            "escalate": True,
            "escalation_level": "management",
            "sla_breached": True,
            "management_escalation": True,
        },
    },
    # ------------------------------------------------------------------
    # 12. Vodafone closure blocked — no RCA
    # ------------------------------------------------------------------
    {
        "name": "vodafone_closure_blocked_no_rca",
        "domain": "telco_ops",
        "workflow_type": "vodafone_managed_services",
        "description": (
            "P1 incident resolved but RCA not submitted — closure should be blocked"
        ),
        "input_payload": {
            "incident": {
                "incident_id": "VF-INC-004",
                "severity": "p1",
                "state": "resolved",
                "title": "IMS platform failure — VoLTE service impact",
                "description": "IMS CSCF failure resolved by failover. RCA pending.",
                "affected_services": ["voip_ims"],
                "tags": ["major_incident"],
                "created_at": "2026-03-24T14:00:00Z",
            },
            "closure_gates": [
                {"prerequisite": "service_restored", "satisfied": True, "evidence_ref": "SR-001"},
                {"prerequisite": "customer_notified", "satisfied": True, "evidence_ref": "COMMS-001"},
                {"prerequisite": "rca_submitted", "satisfied": False, "evidence_ref": ""},
                {"prerequisite": "problem_record_created", "satisfied": True, "evidence_ref": "PRB-001"},
            ],
            "major_incident": {
                "incident_id": "VF-INC-004",
                "phase": "rca_pending",
                "bridge_call_id": "BC-004",
                "bridge_participants": ["noc", "ims_team", "vendor"],
                "customer_comms_sent": [{"type": "email", "timestamp": "2026-03-24T15:00:00Z"}],
                "rca_status": "not_started",
                "rca_due_date": "2026-03-27",
                "problem_record_id": "PRB-001",
            },
        },
        "expected_output": {
            "closure_allowed": False,
            "blocked_by": ["rca_submitted"],
            "mandatory_gates_unsatisfied": 1,
        },
    },
    # ------------------------------------------------------------------
    # 13. Vodafone dispatch — hardware failure
    # ------------------------------------------------------------------
    {
        "name": "vodafone_dispatch_hardware_failure",
        "domain": "telco_ops",
        "workflow_type": "vodafone_managed_services",
        "description": (
            "Hardware failure should trigger immediate dispatch without "
            "requiring remote remediation first"
        ),
        "input_payload": {
            "incident": {
                "incident_id": "VF-INC-005",
                "severity": "p1",
                "state": "investigating",
                "title": "RRU failure at cell site BHM-042",
                "description": (
                    "Remote Radio Unit hardware failure at Birmingham cell site "
                    "BHM-042. VSWR alarm triggered. Sector 2 offline. "
                    "Hardware replacement required."
                ),
                "affected_services": ["ran_radio"],
                "tags": ["hardware"],
                "created_at": "2026-03-25T06:00:00Z",
            },
            "remote_remediation_attempted": False,
            "has_runbook": True,
            "service_domain": "ran_radio",
            "incident_category": "hardware_failure",
        },
        "expected_output": {
            "next_action": "dispatch",
            "dispatch_needed": True,
            "remote_required_first": False,
        },
    },
    # ------------------------------------------------------------------
    # 14. Vodafone dispatch — software, remote first
    # ------------------------------------------------------------------
    {
        "name": "vodafone_dispatch_software_remote_first",
        "domain": "telco_ops",
        "workflow_type": "vodafone_managed_services",
        "description": (
            "Software bug should require remote remediation before dispatch"
        ),
        "input_payload": {
            "incident": {
                "incident_id": "VF-INC-006",
                "severity": "p2",
                "state": "investigating",
                "title": "SMSC message queue stall — software bug",
                "description": (
                    "SMSC-01 experiencing message queue stall after overnight "
                    "patch. SMS delivery delays across the platform. Suspected "
                    "software regression in queue handler module."
                ),
                "affected_services": ["vas_platforms"],
                "tags": [],
                "created_at": "2026-03-25T07:00:00Z",
            },
            "remote_remediation_attempted": False,
            "has_runbook": True,
            "service_domain": "vas_platforms",
            "incident_category": "software_bug",
        },
        "expected_output": {
            "next_action": "remote_remediation",
            "dispatch_needed": False,
            "remote_required_first": True,
        },
    },
    # ------------------------------------------------------------------
    # 15. Vodafone repeated incident escalation
    # ------------------------------------------------------------------
    {
        "name": "vodafone_repeated_incident_escalate",
        "domain": "telco_ops",
        "workflow_type": "vodafone_managed_services",
        "description": (
            "4th incident on the same service within 30 days should "
            "trigger L3 escalation regardless of severity"
        ),
        "input_payload": {
            "incident": {
                "incident_id": "VF-INC-007",
                "severity": "p3",
                "state": "new",
                "title": "Recurring provisioning failure — SIM activation",
                "description": (
                    "SIM activation failures recurring on the provisioning "
                    "platform. This is the 4th incident in 30 days. Previous "
                    "incidents: VF-INC-101, VF-INC-102, VF-INC-103."
                ),
                "affected_services": ["provisioning"],
                "tags": [],
                "created_at": "2026-03-25T09:00:00Z",
            },
            "service_domain": "provisioning",
            "sla_status": {
                "response_sla": "within",
                "resolution_sla": "within",
                "update_overdue": False,
                "minutes_to_breach": 1400,
                "bridge_call_required": False,
            },
            "repeat_count": 4,
        },
        "expected_output": {
            "escalate": True,
            "escalation_level": "l3",
            "reason_contains": "Repeated incident",
        },
    },
    # ------------------------------------------------------------------
    # 16. Vodafone fibre cut — dispatch + NRSWA
    # ------------------------------------------------------------------
    {
        "name": "vodafone_fibre_cut_dispatch_plus_nrswa",
        "domain": "telco_ops",
        "workflow_type": "vodafone_managed_services",
        "description": (
            "Fibre cut should trigger immediate dispatch with NRSWA "
            "permit coordination"
        ),
        "input_payload": {
            "incident": {
                "incident_id": "VF-INC-008",
                "severity": "p1",
                "state": "investigating",
                "title": "Fibre cut on trunk route Manchester–Leeds",
                "description": (
                    "Major fibre cut detected on trunk route between Manchester "
                    "and Leeds exchanges. Third-party contractor damage during "
                    "road works. Multiple DWDM circuits affected. NRSWA permit "
                    "required for emergency excavation."
                ),
                "affected_services": ["transport_network"],
                "tags": ["fibre_cut", "outage"],
                "created_at": "2026-03-25T10:00:00Z",
            },
            "remote_remediation_attempted": False,
            "has_runbook": True,
            "service_domain": "transport_network",
            "incident_category": "fibre_cut",
        },
        "expected_output": {
            "next_action": "dispatch",
            "dispatch_needed": True,
            "nrswa_coordination": True,
            "reason_contains": "NRSWA",
        },
    },
]
