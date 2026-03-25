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
]
