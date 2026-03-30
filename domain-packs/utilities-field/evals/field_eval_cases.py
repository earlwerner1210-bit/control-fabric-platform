"""Evaluation cases for utilities field domain pack.

Each case provides an input scenario, expected output, and description
to validate readiness, safety, and skill matching logic.
"""

from __future__ import annotations

FIELD_EVAL_CASES: list[dict] = [
    {
        "id": "eval-uf-001",
        "description": "Fully qualified engineer with all permits should be marked ready",
        "input": {
            "work_order": {
                "work_order_type": "installation",
                "title": "Fibre ONT installation at residential property",
                "required_skills": ["fiber"],
                "jobs": [
                    {
                        "description": "Install fibre ONT and patch to customer router",
                        "required_skills": ["fiber"],
                        "hazards": [],
                        "safety_equipment": [],
                    },
                ],
                "required_permits": [],
                "scheduled_date": "2026-04-01",
                "priority": "normal",
            },
            "engineer": {
                "name": "Jane Smith",
                "skills": [
                    {
                        "category": "fiber",
                        "name": "Single-mode fibre splicing",
                        "proficiency_level": "expert",
                    },
                ],
                "accreditations": [],
                "available": True,
                "current_assignment": None,
            },
        },
        "expected_output": {
            "status": "ready",
            "skill_fit_min": 0.9,
            "blockers_count": 0,
        },
    },
    {
        "id": "eval-uf-002",
        "description": "Gas work without Gas Safe registration should be blocked",
        "input": {
            "work_order": {
                "work_order_type": "repair",
                "title": "Gas boiler repair at commercial site",
                "required_skills": ["gas"],
                "jobs": [
                    {
                        "description": "Diagnose and repair gas boiler fault",
                        "required_skills": ["gas"],
                        "hazards": ["gas"],
                        "safety_equipment": ["gas detector"],
                    },
                ],
                "required_permits": [],
                "scheduled_date": "2026-04-02",
                "priority": "high",
            },
            "engineer": {
                "name": "Bob Jones",
                "skills": [
                    {
                        "category": "plumbing",
                        "name": "General plumbing",
                        "proficiency_level": "competent",
                    },
                ],
                "accreditations": [],
                "available": True,
            },
        },
        "expected_output": {
            "status": "blocked",
            "has_blocker_category": "accreditation",
            "skill_fit_max": 0.6,
        },
    },
    {
        "id": "eval-uf-003",
        "description": "Work requiring confined space entry without certification should escalate",
        "input": {
            "work_order": {
                "work_order_type": "maintenance",
                "title": "Underground chamber inspection and cable replacement",
                "required_skills": ["fiber", "electrical"],
                "jobs": [
                    {
                        "description": "Enter confined space manhole chamber and replace fibre cable",
                        "required_skills": ["fiber"],
                        "hazards": ["confined space"],
                        "safety_equipment": ["harness", "gas detector", "hard hat"],
                    },
                ],
                "required_permits": [
                    {"permit_type": "confined_space", "status": "approved"},
                ],
                "scheduled_date": "2026-04-03",
                "priority": "normal",
            },
            "engineer": {
                "name": "Alice Chen",
                "skills": [
                    {
                        "category": "fiber",
                        "name": "Fibre splicing",
                        "proficiency_level": "competent",
                    },
                    {
                        "category": "electrical",
                        "name": "Low voltage wiring",
                        "proficiency_level": "competent",
                    },
                ],
                "accreditations": [],
                "available": True,
            },
        },
        "expected_output": {
            "status_in": ["blocked", "escalate"],
            "has_safety_blocker": True,
        },
    },
]
