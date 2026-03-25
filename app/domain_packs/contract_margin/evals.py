"""Contract & Margin eval cases."""

CONTRACT_MARGIN_EVAL_CASES = [
    {
        "name": "billable_standard_maintenance",
        "domain": "contract_margin",
        "workflow_type": "margin_diagnosis",
        "description": "Standard maintenance activity should be billable at contract rate",
        "input_payload": {
            "activity": "standard_maintenance",
            "rate_card": [{"activity": "standard_maintenance", "rate": 125.0, "unit": "hour", "currency": "USD"}],
            "obligations": [{"text": "Provider shall deliver all scheduled maintenance", "section": "3.1"}],
        },
        "expected_output": {
            "verdict": "billable",
            "billable": True,
        },
    },
    {
        "name": "unbilled_completed_work_leakage",
        "domain": "contract_margin",
        "workflow_type": "margin_diagnosis",
        "description": "Completed work that was not billed should trigger leakage",
        "input_payload": {
            "work_history": [
                {"activity": "emergency_repair", "status": "completed", "billed": False, "estimated_value": 750},
            ],
        },
        "expected_output": {
            "verdict": "under_recovery",
            "leakage_drivers": ["unbilled_completed_work"],
        },
    },
    {
        "name": "penalty_risk_sla_breach",
        "domain": "contract_margin",
        "workflow_type": "margin_diagnosis",
        "description": "SLA breach should result in penalty risk verdict",
        "input_payload": {
            "sla_performance": {"sla_met": False, "breaches": 3},
            "penalty_objects": [{"label": "SLA penalty", "payload": {"text": "Failure to meet SLA response times"}}],
        },
        "expected_output": {
            "verdict": "penalty_risk",
        },
    },
    {
        "name": "out_of_scope_non_billable",
        "domain": "contract_margin",
        "workflow_type": "margin_diagnosis",
        "description": "Out-of-scope activity without change order should be non-billable",
        "input_payload": {
            "activity": "custom_software_development",
            "rate_card": [{"activity": "standard_maintenance", "rate": 125.0, "unit": "hour", "currency": "USD"}],
            "obligations": [{"text": "Network maintenance and equipment installation", "section": "2.1"}],
        },
        "expected_output": {
            "verdict": "non_billable",
            "billable": False,
        },
    },
    # ------------------------------------------------------------------
    # SPEN / Vodafone — UK utility managed services eval cases
    # ------------------------------------------------------------------
    {
        "name": "spen_planned_work_billable",
        "domain": "contract_margin",
        "workflow_type": "spen_billability",
        "description": "Planned cable jointing with all billing gates satisfied should be billable at base rate",
        "input_payload": {
            "activity": "CJ-001",
            "work_category": "cable_jointing",
            "rate_card": [
                {
                    "work_category": "cable_jointing",
                    "activity_code": "CJ-001",
                    "description": "11kV straight joint",
                    "unit": "each",
                    "base_rate": 485.00,
                    "currency": "GBP",
                },
            ],
            "billing_gates": [
                {"gate_type": "purchase_order", "description": "PO raised", "satisfied": True},
                {"gate_type": "completion_certificate", "description": "Completion cert signed", "satisfied": True},
            ],
            "is_reattendance": False,
            "time_of_day": "normal",
        },
        "expected_output": {
            "verdict": "billable",
            "billable": True,
            "rate_applied": 485.00,
        },
    },
    {
        "name": "spen_emergency_callout_premium",
        "domain": "contract_margin",
        "workflow_type": "spen_billability",
        "description": "Emergency HV fault repair at night should be billable at 1.5x emergency rate",
        "input_payload": {
            "activity": "HV-SWITCH-001",
            "work_category": "hv_switching",
            "rate_card": [
                {
                    "work_category": "hv_switching",
                    "activity_code": "HV-SWITCH-001",
                    "description": "HV switching operation — fault response",
                    "unit": "each",
                    "base_rate": 320.00,
                    "emergency_multiplier": 1.5,
                    "currency": "GBP",
                },
            ],
            "billing_gates": [
                {"gate_type": "purchase_order", "description": "Standing PO", "satisfied": True},
            ],
            "is_reattendance": False,
            "time_of_day": "emergency",
        },
        "expected_output": {
            "verdict": "billable",
            "billable": True,
            "rate_applied": 480.00,
        },
    },
    {
        "name": "spen_reattendance_provider_fault",
        "domain": "contract_margin",
        "workflow_type": "spen_billability",
        "description": "Re-attendance due to quality failure / provider fault should be non-billable",
        "input_payload": {
            "activity": "CJ-001",
            "work_category": "cable_jointing",
            "rate_card": [
                {
                    "work_category": "cable_jointing",
                    "activity_code": "CJ-001",
                    "description": "11kV straight joint",
                    "unit": "each",
                    "base_rate": 485.00,
                    "currency": "GBP",
                },
            ],
            "billing_gates": [
                {"gate_type": "purchase_order", "description": "PO raised", "satisfied": True},
                {"gate_type": "completion_certificate", "description": "Completion cert signed", "satisfied": True},
            ],
            "is_reattendance": True,
            "reattendance_trigger": "provider_fault",
            "time_of_day": "normal",
        },
        "expected_output": {
            "verdict": "non_billable",
            "billable": False,
        },
    },
    {
        "name": "spen_reattendance_customer_fault",
        "domain": "contract_margin",
        "workflow_type": "spen_billability",
        "description": "Re-visit due to customer cancellation should be billable at standard rate",
        "input_payload": {
            "activity": "LV-FAULT-002",
            "work_category": "lv_fault_repair",
            "rate_card": [
                {
                    "work_category": "lv_fault_repair",
                    "activity_code": "LV-FAULT-002",
                    "description": "LV underground fault repair",
                    "unit": "each",
                    "base_rate": 275.00,
                    "currency": "GBP",
                },
            ],
            "billing_gates": [
                {"gate_type": "purchase_order", "description": "Standing PO", "satisfied": True},
            ],
            "is_reattendance": True,
            "reattendance_trigger": "customer_fault",
            "time_of_day": "normal",
        },
        "expected_output": {
            "verdict": "billable",
            "billable": True,
            "rate_applied": 275.00,
        },
    },
    {
        "name": "spen_abortive_visit_no_claim",
        "domain": "contract_margin",
        "workflow_type": "spen_leakage",
        "description": "Abortive visit (customer no-access) not claimed as abortive — leakage trigger",
        "input_payload": {
            "work_history": [
                {
                    "activity": "metering_installation",
                    "status": "aborted",
                    "abortive": True,
                    "abortive_claimed": False,
                    "abortive_value": 150.00,
                    "category": "measured_work",
                },
            ],
        },
        "expected_output": {
            "leakage_drivers": ["abortive_visit_not_claimed"],
        },
    },
    {
        "name": "spen_missing_daywork_sheet",
        "domain": "contract_margin",
        "workflow_type": "spen_leakage",
        "description": "Daywork completed but daywork sheet unsigned — non-billable, leakage",
        "input_payload": {
            "work_history": [
                {
                    "activity": "emergency_civils_excavation",
                    "status": "completed",
                    "category": "daywork",
                    "daywork_sheet_signed": False,
                    "estimated_value": 1200.00,
                },
            ],
        },
        "expected_output": {
            "leakage_drivers": ["missing_daywork_sheet"],
        },
    },
    {
        "name": "spen_variation_no_change_order",
        "domain": "contract_margin",
        "workflow_type": "spen_leakage",
        "description": "Out-of-scope variation work performed without formal variation order — non-billable, leakage",
        "input_payload": {
            "work_history": [
                {
                    "activity": "additional_reinstatement",
                    "status": "completed",
                    "is_variation": True,
                    "variation_order_ref": "",
                    "estimated_value": 3500.00,
                    "billed": False,
                },
            ],
        },
        "expected_output": {
            "leakage_drivers": ["variation_work_no_change_order"],
        },
    },
    {
        "name": "spen_service_credit_sla_breach",
        "domain": "contract_margin",
        "workflow_type": "spen_service_credit",
        "description": "Response time SLA breached — service credit calculated at 2% capped at 10% of monthly invoice",
        "input_payload": {
            "sla_performance": {"response_time": 3.5},
            "credit_rules": [
                {
                    "sla_metric": "response_time",
                    "threshold_value": 2.0,
                    "credit_percentage": 2.0,
                    "cap_percentage": 10.0,
                    "measurement_period": "monthly",
                    "exclusions": ["force_majeure"],
                },
            ],
            "monthly_invoice_value": 50000.00,
        },
        "expected_output": {
            "breached": True,
            "credit_percentage": 2.0,
            "credit_value": 1000.00,
        },
    },
]
