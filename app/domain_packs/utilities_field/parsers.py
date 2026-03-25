"""Utilities Field domain parsers."""

from __future__ import annotations

import json
import re
from typing import Any

from app.domain_packs.utilities_field.schemas import (
    Accreditation,
    EngineerProfile,
    ParsedWorkOrder,
    PermitRequirement,
    PermitType,
    SkillCategory,
    SkillRecord,
    WorkOrderType,
)


class WorkOrderParser:
    """Parse work order documents."""

    def parse_work_order(self, text_or_payload: str | dict) -> ParsedWorkOrder:
        if isinstance(text_or_payload, dict):
            return self._from_json(text_or_payload)
        return self._from_text(text_or_payload)

    def _from_json(self, data: dict) -> ParsedWorkOrder:
        skills = [
            SkillRecord(
                skill_name=s if isinstance(s, str) else s.get("skill_name", s.get("skill", "")),
                category=SkillCategory(s.get("category", "general")) if isinstance(s, dict) else SkillCategory.general,
            )
            for s in data.get("required_skills", [])
        ]
        permits = [
            PermitRequirement(
                permit_type=PermitType(p.get("permit_type", "building_access")),
                description=p.get("description", ""),
                required=p.get("required", True),
                obtained=p.get("obtained", False),
            )
            for p in data.get("required_permits", [])
        ]
        wo_type = data.get("work_order_type", data.get("type", "maintenance"))
        return ParsedWorkOrder(
            work_order_id=data.get("work_order_id", data.get("id", "unknown")),
            work_order_type=WorkOrderType(wo_type) if wo_type in WorkOrderType.__members__ else WorkOrderType.maintenance,
            description=data.get("description", ""),
            location=data.get("location", ""),
            scheduled_date=data.get("scheduled_date"),
            priority=data.get("priority", "normal"),
            required_skills=skills,
            required_permits=permits,
            prerequisites=data.get("prerequisites", []),
            estimated_duration_hours=data.get("estimated_duration_hours", 0),
            customer=data.get("customer", ""),
        )

    def _from_text(self, text: str) -> ParsedWorkOrder:
        wo_id_match = re.search(r'WO[-_]?(\w+)', text)
        return ParsedWorkOrder(
            work_order_id=wo_id_match.group(0) if wo_id_match else "unknown",
            description=text[:500],
        )


class EngineerProfileParser:
    """Parse engineer profile documents."""

    def parse_profile(self, text_or_payload: str | dict) -> EngineerProfile:
        if isinstance(text_or_payload, dict):
            return self._from_json(text_or_payload)
        return EngineerProfile(engineer_id="unknown", name="Unknown")

    def _from_json(self, data: dict) -> EngineerProfile:
        skills = [
            SkillRecord(
                skill_name=s.get("skill_name", s.get("name", "")),
                category=SkillCategory(s.get("category", "general")) if s.get("category") in SkillCategory.__members__ else SkillCategory.general,
                level=s.get("level", "qualified"),
                expiry_date=s.get("expiry_date"),
            )
            for s in data.get("skills", [])
        ]
        accreditations = [
            Accreditation(
                name=a.get("name", ""),
                issuing_body=a.get("issuing_body", ""),
                valid_from=a.get("valid_from"),
                valid_to=a.get("valid_to"),
                is_valid=a.get("is_valid", True),
            )
            for a in data.get("accreditations", [])
        ]
        return EngineerProfile(
            engineer_id=data.get("engineer_id", data.get("id", "unknown")),
            name=data.get("name", "Unknown"),
            skills=skills,
            accreditations=accreditations,
            availability=data.get("availability", "available"),
            location=data.get("location", ""),
        )
