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
                "required_permits": [
                    {"permit_type": "street_works", "required": True, "obtained": False}
                ],
            },
            "engineer": {
                "engineer_id": "ENG-002",
                "name": "Jane Doe",
                "skills": [],
                "accreditations": [],
            },
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
    # ------------------------------------------------------------------
    # SPEN / UK Utility Managed Services eval cases
    # ------------------------------------------------------------------
    {
        "name": "spen_hv_switching_ready",
        "domain": "utilities_field",
        "workflow_type": "spen_readiness",
        "description": "HV authorised engineer with all permits and accreditations should be ready for HV switching",
        "input_payload": {
            "work_order": {
                "work_order_id": "SPEN-WO-001",
                "work_order_type": "maintenance",
                "work_category": "hv_switching",
                "scheme_ref": "SPEN-SCH-2026-0451",
                "description": "11kV ring main unit switching for planned maintenance",
                "location": "Glasgow South 11kV Feeder 7",
                "customer_confirmed": True,
                "planned_outage": True,
                "notified_date": "2026-03-20",
                "required_skills": [{"skill_name": "hv_switching", "category": "electrical"}],
                "required_permits": [],
            },
            "engineer": {
                "engineer_id": "SPEN-ENG-101",
                "name": "Alistair MacLeod",
                "skills": [
                    {"skill_name": "hv_switching", "category": "electrical", "level": "expert"}
                ],
                "accreditations": [
                    {"name": "hv_authorized_person", "issuing_body": "SPEN", "is_valid": True},
                    {"name": "ecs_card", "issuing_body": "ECS", "is_valid": True},
                    {"name": "first_aid_at_work", "issuing_body": "Red Cross", "is_valid": True},
                ],
            },
            "work_category": "hv_switching",
        },
        "expected_output": {"verdict": "ready"},
    },
    {
        "name": "spen_hv_switching_blocked_no_auth",
        "domain": "utilities_field",
        "workflow_type": "spen_readiness",
        "description": "Engineer without HV Authorised Person accreditation should be blocked for HV switching",
        "input_payload": {
            "work_order": {
                "work_order_id": "SPEN-WO-002",
                "work_order_type": "maintenance",
                "work_category": "hv_switching",
                "scheme_ref": "SPEN-SCH-2026-0452",
                "description": "33kV circuit breaker switching operation",
                "location": "Edinburgh North 33kV Substation",
                "customer_confirmed": True,
                "planned_outage": True,
                "notified_date": "2026-03-18",
                "required_skills": [{"skill_name": "hv_switching", "category": "electrical"}],
                "required_permits": [],
            },
            "engineer": {
                "engineer_id": "SPEN-ENG-102",
                "name": "Craig Henderson",
                "skills": [
                    {"skill_name": "hv_switching", "category": "electrical", "level": "qualified"}
                ],
                "accreditations": [
                    {"name": "ecs_card", "issuing_body": "ECS", "is_valid": True},
                    {"name": "first_aid_at_work", "issuing_body": "Red Cross", "is_valid": True},
                ],
            },
            "work_category": "hv_switching",
        },
        "expected_output": {"verdict": "blocked"},
    },
    {
        "name": "spen_cable_jointing_missing_permit",
        "domain": "utilities_field",
        "workflow_type": "spen_readiness",
        "description": "Cable jointing in public highway without NRSWA street works permit should be blocked",
        "input_payload": {
            "work_order": {
                "work_order_id": "SPEN-WO-003",
                "work_order_type": "repair",
                "work_category": "cable_jointing",
                "scheme_ref": "SPEN-SCH-2026-0453",
                "description": "LV cable joint repair in footway adjacent to A77",
                "location": "Ayr, South Ayrshire, KA7 2DP",
                "customer_confirmed": False,
                "required_skills": [{"skill_name": "cable_jointing", "category": "electrical"}],
                "required_permits": [
                    {
                        "permit_type": "street_works",
                        "required": True,
                        "obtained": False,
                        "description": "NRSWA S50 permit for footway excavation",
                    }
                ],
            },
            "engineer": {
                "engineer_id": "SPEN-ENG-103",
                "name": "Darren Campbell",
                "skills": [
                    {"skill_name": "cable_jointing", "category": "electrical", "level": "expert"}
                ],
                "accreditations": [
                    {"name": "cable_jointer_approved", "issuing_body": "SPEN", "is_valid": True},
                    {"name": "cscs_card", "issuing_body": "CSCS", "is_valid": True},
                    {"name": "cat_and_genny", "issuing_body": "EUSR", "is_valid": True},
                ],
            },
            "work_category": "cable_jointing",
        },
        "expected_output": {"verdict": "blocked"},
    },
    {
        "name": "spen_metering_no_eighteen_edition",
        "domain": "utilities_field",
        "workflow_type": "spen_readiness",
        "description": "Metering installation engineer lacking 18th Edition qualification should be blocked",
        "input_payload": {
            "work_order": {
                "work_order_id": "SPEN-WO-004",
                "work_order_type": "installation",
                "work_category": "metering_installation",
                "scheme_ref": "SPEN-MTR-2026-1102",
                "description": "Single phase smart meter installation — domestic property",
                "location": "14 Buchanan Drive, Paisley, PA2 7NE",
                "customer_confirmed": True,
                "required_skills": [{"skill_name": "metering", "category": "electrical"}],
                "required_permits": [],
            },
            "engineer": {
                "engineer_id": "SPEN-ENG-104",
                "name": "Fiona Stewart",
                "skills": [
                    {"skill_name": "metering", "category": "electrical", "level": "qualified"}
                ],
                "accreditations": [
                    {"name": "ecs_card", "issuing_body": "ECS", "is_valid": True},
                ],
            },
            "work_category": "metering_installation",
        },
        "expected_output": {"verdict": "blocked"},
    },
    {
        "name": "spen_overhead_lines_crew_size",
        "domain": "utilities_field",
        "workflow_type": "spen_readiness",
        "description": "Overhead line work with single person crew should be blocked — requires 2-person crew",
        "input_payload": {
            "work_order": {
                "work_order_id": "SPEN-WO-005",
                "work_order_type": "maintenance",
                "work_category": "overhead_lines",
                "scheme_ref": "SPEN-OHL-2026-0089",
                "description": "11kV overhead line conductor repair — rural span",
                "location": "B7078 near Lesmahagow, South Lanarkshire",
                "customer_confirmed": False,
                "required_skills": [{"skill_name": "overhead_lines", "category": "electrical"}],
                "required_permits": [],
            },
            "engineer": {
                "engineer_id": "SPEN-ENG-105",
                "name": "Graeme Wallace",
                "skills": [
                    {"skill_name": "overhead_lines", "category": "electrical", "level": "expert"}
                ],
                "accreditations": [
                    {"name": "working_at_height", "issuing_body": "CITB", "is_valid": True},
                    {"name": "ipaf_mewp", "issuing_body": "IPAF", "is_valid": True},
                    {"name": "ecs_card", "issuing_body": "ECS", "is_valid": True},
                ],
            },
            "work_category": "overhead_lines",
            "crew_size": 1,
        },
        "expected_output": {"verdict": "blocked"},
    },
    {
        "name": "spen_new_connection_design_not_approved",
        "domain": "utilities_field",
        "workflow_type": "spen_readiness",
        "description": "New connection with unapproved scheme design should be blocked",
        "input_payload": {
            "work_order": {
                "work_order_id": "SPEN-WO-006",
                "work_order_type": "installation",
                "work_category": "new_connection",
                "scheme_ref": "SPEN-NC-2026-0334",
                "description": "New single-phase domestic connection — housing development plot 12",
                "location": "Phase 2, Dalmarnock Road Development, Glasgow, G40",
                "customer_confirmed": True,
                "required_skills": [{"skill_name": "new_connections", "category": "electrical"}],
                "required_permits": [],
                "dependencies": [
                    {
                        "type": "design",
                        "description": "scheme design",
                        "status": "pending",
                        "blocking": True,
                    }
                ],
            },
            "engineer": {
                "engineer_id": "SPEN-ENG-106",
                "name": "Ross Mackenzie",
                "skills": [
                    {"skill_name": "new_connections", "category": "electrical", "level": "expert"}
                ],
                "accreditations": [
                    {"name": "lv_authorized_person", "issuing_body": "SPEN", "is_valid": True},
                    {"name": "ecs_card", "issuing_body": "ECS", "is_valid": True},
                    {"name": "eighteen_edition", "issuing_body": "City & Guilds", "is_valid": True},
                    {"name": "cat_and_genny", "issuing_body": "EUSR", "is_valid": True},
                ],
            },
            "work_category": "new_connection",
        },
        "expected_output": {"verdict": "blocked"},
    },
    {
        "name": "spen_civils_no_cat_genny",
        "domain": "utilities_field",
        "workflow_type": "spen_readiness",
        "description": "Civils excavation engineer without CAT & Genny certification should be blocked",
        "input_payload": {
            "work_order": {
                "work_order_id": "SPEN-WO-007",
                "work_order_type": "maintenance",
                "work_category": "civils_excavation",
                "scheme_ref": "SPEN-CIV-2026-0211",
                "description": "Excavation for new LV cable duct — public footway",
                "location": "High Street, Kilmarnock, KA1 1HR",
                "customer_confirmed": False,
                "required_skills": [{"skill_name": "excavation", "category": "general"}],
                "required_permits": [
                    {
                        "permit_type": "street_works",
                        "required": True,
                        "obtained": True,
                        "reference": "NRSWA-2026-KA1-0098",
                    }
                ],
                "special_instructions": "Traffic management plan ref TM-2026-0098 approved.",
            },
            "engineer": {
                "engineer_id": "SPEN-ENG-107",
                "name": "Kevin Murray",
                "skills": [
                    {"skill_name": "excavation", "category": "general", "level": "qualified"}
                ],
                "accreditations": [
                    {"name": "cscs_card", "issuing_body": "CSCS", "is_valid": True},
                    {"name": "nrswa_operative", "issuing_body": "HAUC", "is_valid": True},
                ],
            },
            "work_category": "civils_excavation",
        },
        "expected_output": {"verdict": "blocked"},
    },
    {
        "name": "spen_completion_missing_evidence",
        "domain": "utilities_field",
        "workflow_type": "spen_completion",
        "description": "HV switching work completed but missing test certificate should fail completion validation",
        "input_payload": {
            "work_category": "hv_switching",
            "evidence": [
                {
                    "evidence_type": "after_photo",
                    "provided": True,
                    "reference": "IMG-2026-0451-01.jpg",
                },
                {
                    "evidence_type": "risk_assessment_completed",
                    "provided": True,
                    "reference": "RA-2026-0451",
                },
                {
                    "evidence_type": "safety_documentation",
                    "provided": True,
                    "reference": "HV-SD-2026-0451",
                },
            ],
        },
        "expected_output": {
            "verdict": "completion_invalid",
            "missing_evidence": ["test_certificate"],
        },
    },
]
