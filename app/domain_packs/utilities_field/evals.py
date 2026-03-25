"""Utilities Field eval cases."""

UTILITIES_FIELD_EVAL_CASES = [
    {
        "name": "ready_all_clear",
        "domain": "utilities_field",
        "workflow_type": "work_order_readiness",
        "description": "Engineer with all required skills and permits should be ready",
        "input_payload": {
            "work_order": {
                "work_order_id": "WO-001",
                "work_order_type": "maintenance",
                "required_skills": [{"skill_name": "fiber", "category": "fiber"}],
                "required_permits": [],
            },
            "engineer": {
                "engineer_id": "ENG-001",
                "name": "John Smith",
                "skills": [{"skill_name": "fiber", "category": "fiber", "level": "qualified"}],
                "accreditations": [],
            },
        },
        "expected_output": {"verdict": "ready"},
    },
    {
        "name": "blocked_missing_permit",
        "domain": "utilities_field",
        "workflow_type": "work_order_readiness",
        "description": "Missing required permit should block dispatch",
        "input_payload": {
            "work_order": {
                "work_order_id": "WO-002",
                "work_order_type": "installation",
                "required_skills": [],
                "required_permits": [{"permit_type": "street_works", "required": True, "obtained": False}],
            },
            "engineer": {"engineer_id": "ENG-002", "name": "Jane Doe", "skills": [], "accreditations": []},
        },
        "expected_output": {"verdict": "blocked"},
    },
    {
        "name": "blocked_missing_skill",
        "domain": "utilities_field",
        "workflow_type": "work_order_readiness",
        "description": "Missing required skill should block dispatch",
        "input_payload": {
            "work_order": {
                "work_order_id": "WO-003",
                "work_order_type": "repair",
                "required_skills": [{"skill_name": "gas", "category": "gas"}],
                "required_permits": [],
            },
            "engineer": {
                "engineer_id": "ENG-003",
                "name": "Bob Wilson",
                "skills": [{"skill_name": "electrical", "category": "electrical"}],
                "accreditations": [],
            },
        },
        "expected_output": {"verdict": "blocked"},
    },
]
