"""Parsers for field work orders and permits.

Uses regex-based extraction to pull structured data from semi-structured
work order text, including job details, site information, skills, and permits.
"""

from __future__ import annotations

import re
from datetime import date, time
from typing import Optional

from ..schemas.field_schemas import (
    FieldJob,
    ParsedWorkOrder,
    PermitRequirement,
)
from ..taxonomy.field_taxonomy import (
    PermitType,
    SkillCategory,
    WorkOrderType,
)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_WO_TYPE_KEYWORDS: dict[WorkOrderType, re.Pattern[str]] = {
    WorkOrderType.emergency: re.compile(r"\b(emergency|urgent fault|critical failure)\b", re.I),
    WorkOrderType.installation: re.compile(r"\b(install|new connection|provision|commissioning)\b", re.I),
    WorkOrderType.repair: re.compile(r"\b(repair|fix|fault|breakdown|restore)\b", re.I),
    WorkOrderType.maintenance: re.compile(r"\b(maintenance|preventive|scheduled service|routine)\b", re.I),
    WorkOrderType.inspection: re.compile(r"\b(inspection|survey|audit|assessment|check)\b", re.I),
    WorkOrderType.upgrade: re.compile(r"\b(upgrade|replacement|modernis|retrofit)\b", re.I),
}

_SKILL_KEYWORDS: dict[SkillCategory, re.Pattern[str]] = {
    SkillCategory.electrical: re.compile(r"\b(electric|wiring|circuit|power|voltage|transformer)\b", re.I),
    SkillCategory.plumbing: re.compile(r"\b(plumb|pipe|water|drain|sewage)\b", re.I),
    SkillCategory.hvac: re.compile(r"\b(hvac|heating|ventilation|air\s+condition|cooling)\b", re.I),
    SkillCategory.gas: re.compile(r"\b(gas|boiler|flue|combustion)\b", re.I),
    SkillCategory.fiber: re.compile(r"\b(fib[re]+|optical|splice|ont|olt|gpon)\b", re.I),
    SkillCategory.general: re.compile(r"\b(general|handyman|multi[- ]?skill)\b", re.I),
}

_PERMIT_KEYWORDS: dict[PermitType, re.Pattern[str]] = {
    PermitType.street_works: re.compile(r"\b(street\s+works?|road\s+(closure|works?)|traffic\s+management)\b", re.I),
    PermitType.building_access: re.compile(r"\b(building\s+access|site\s+access|key\s+holder|access\s+control)\b", re.I),
    PermitType.confined_space: re.compile(r"\b(confined\s+space|manhole|chamber|underground)\b", re.I),
    PermitType.hot_works: re.compile(r"\b(hot\s+works?|welding|soldering|brazing|grinding)\b", re.I),
    PermitType.height_works: re.compile(r"\b(height|elevated|ladder|scaffold|cherry\s+picker|aerial)\b", re.I),
}

_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")
_TIME_PATTERN = re.compile(r"(\d{2}:\d{2})")
_POSTCODE_PATTERN = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", re.I)
_PHONE_PATTERN = re.compile(r"(\+?\d[\d\s\-]{7,15}\d)")

_FIELD_PATTERNS = {
    "customer": re.compile(r"(?:customer|client|account)\s*[:=]\s*(.+?)(?:\n|$)", re.I),
    "address": re.compile(r"(?:address|site|location)\s*[:=]\s*(.+?)(?:\n|$)", re.I),
    "contact": re.compile(r"(?:contact|phone|tel|mobile)\s*[:=]\s*(.+?)(?:\n|$)", re.I),
    "priority": re.compile(r"(?:priority|urgency)\s*[:=]\s*(low|normal|high|critical)", re.I),
    "title": re.compile(r"(?:title|subject|summary|wo\s*title)\s*[:=]\s*(.+?)(?:\n|$)", re.I),
    "wo_id": re.compile(r"(?:work\s*order\s*(?:id|number|ref|#))\s*[:=]?\s*([\w\-]+)", re.I),
}

_HAZARD_KEYWORDS = re.compile(
    r"\b(asbestos|live\s+electrical|confined\s+space|height|chemical|gas\s+leak|"
    r"excavation|traffic|moving\s+machinery|hot\s+surface)\b",
    re.I,
)

_SAFETY_EQUIPMENT = re.compile(
    r"\b(hard\s+hat|hi[- ]?vis|safety\s+boots|goggles|gloves|harness|"
    r"respirator|ear\s+protection|face\s+shield|gas\s+detector)\b",
    re.I,
)


def _parse_date(text: str) -> Optional[date]:
    """Extract first ISO date from text."""
    match = _DATE_PATTERN.search(text)
    if match:
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            pass
    return None


def _parse_time(text: str) -> Optional[time]:
    """Extract first HH:MM time from text."""
    match = _TIME_PATTERN.search(text)
    if match:
        try:
            return time.fromisoformat(match.group(1))
        except ValueError:
            pass
    return None


class WorkOrderParser:
    """Parser for extracting structured work order data from text."""

    def parse_work_order(self, text: str) -> ParsedWorkOrder:
        """Parse work order text into a structured ParsedWorkOrder.

        Args:
            text: Raw work order text.

        Returns:
            ParsedWorkOrder with all extractable fields populated.
        """
        wo_type = self._detect_work_order_type(text)
        required_skills = self._detect_required_skills(text)
        required_permits = self._detect_permits(text)
        jobs = self._extract_jobs(text, required_skills)

        # Extract field values
        customer = self._extract_field(text, "customer")
        address = self._extract_field(text, "address")
        contact = self._extract_field(text, "contact")
        priority = self._extract_field(text, "priority") or "normal"
        title = self._extract_field(text, "title") or text.split("\n")[0].strip()[:200]
        wo_id = self._extract_field(text, "wo_id")

        # Extract postcode from address or text
        postcode_match = _POSTCODE_PATTERN.search(address or text)
        postcode = postcode_match.group(1).upper() if postcode_match else ""

        # Extract phone
        phone = ""
        if contact:
            phone_match = _PHONE_PATTERN.search(contact)
            phone = phone_match.group(1).strip() if phone_match else contact

        # Extract dates/times
        scheduled_date = _parse_date(text)
        times = _TIME_PATTERN.findall(text)
        time_start = None
        time_end = None
        if times:
            try:
                time_start = time.fromisoformat(times[0])
            except ValueError:
                pass
            if len(times) > 1:
                try:
                    time_end = time.fromisoformat(times[1])
                except ValueError:
                    pass

        return ParsedWorkOrder(
            work_order_id=wo_id or "",
            work_order_type=wo_type,
            title=title,
            description=text,
            customer_name=customer or "",
            site_address=address or "",
            site_postcode=postcode,
            contact_phone=phone,
            scheduled_date=scheduled_date,
            scheduled_time_start=time_start,
            scheduled_time_end=time_end,
            jobs=jobs,
            required_skills=required_skills,
            required_permits=required_permits,
            priority=priority.lower(),
        )

    def _detect_work_order_type(self, text: str) -> WorkOrderType:
        """Detect work order type from keywords."""
        for wo_type, pattern in _WO_TYPE_KEYWORDS.items():
            if pattern.search(text):
                return wo_type
        return WorkOrderType.maintenance

    def _detect_required_skills(self, text: str) -> list[SkillCategory]:
        """Detect required skill categories from text."""
        skills: list[SkillCategory] = []
        for category, pattern in _SKILL_KEYWORDS.items():
            if pattern.search(text):
                skills.append(category)
        return skills if skills else [SkillCategory.general]

    def _detect_permits(self, text: str) -> list[PermitRequirement]:
        """Detect required permits from text."""
        permits: list[PermitRequirement] = []
        for permit_type, pattern in _PERMIT_KEYWORDS.items():
            if pattern.search(text):
                permits.append(
                    PermitRequirement(
                        permit_type=permit_type,
                        status="pending",
                    )
                )
        return permits

    def _extract_jobs(self, text: str, skills: list[SkillCategory]) -> list[FieldJob]:
        """Extract individual jobs from work order text."""
        jobs: list[FieldJob] = []

        # Look for numbered task lists
        task_pattern = re.compile(r"(?:^|\n)\s*(?:\d+[.)]\s*|-\s*)(.+?)(?=\n\s*(?:\d+[.)]\s*|-\s*)|\Z)", re.DOTALL)
        task_section = re.search(r"(?:tasks?|jobs?|activities|steps?)\s*[:=]?\s*\n(.*?)(?:\n\n|\Z)", text, re.I | re.DOTALL)

        if task_section:
            for match in task_pattern.finditer(task_section.group(1)):
                task_text = match.group(1).strip()
                if len(task_text) > 5:
                    hazards = [h.group(0) for h in _HAZARD_KEYWORDS.finditer(task_text)]
                    safety_equip = [s.group(0) for s in _SAFETY_EQUIPMENT.finditer(task_text)]
                    jobs.append(
                        FieldJob(
                            description=task_text,
                            required_skills=skills,
                            hazards=hazards,
                            safety_equipment=safety_equip,
                        )
                    )

        # If no structured tasks found, create a single job from the work order
        if not jobs:
            hazards = [h.group(0) for h in _HAZARD_KEYWORDS.finditer(text)]
            safety_equip = [s.group(0) for s in _SAFETY_EQUIPMENT.finditer(text)]
            title = self._extract_field(text, "title") or "Field work"
            jobs.append(
                FieldJob(
                    description=title,
                    required_skills=skills,
                    hazards=hazards,
                    safety_equipment=safety_equip,
                )
            )

        return jobs

    def _extract_field(self, text: str, field_name: str) -> Optional[str]:
        """Extract a named field from text."""
        pattern = _FIELD_PATTERNS.get(field_name)
        if pattern:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        return None


class FieldJobParser:
    """Parser for individual field job descriptions."""

    def parse_job(self, text: str) -> FieldJob:
        """Parse a job description text into a FieldJob."""
        skills: list[SkillCategory] = []
        for category, pattern in _SKILL_KEYWORDS.items():
            if pattern.search(text):
                skills.append(category)

        hazards = [h.group(0) for h in _HAZARD_KEYWORDS.finditer(text)]
        safety_equip = [s.group(0) for s in _SAFETY_EQUIPMENT.finditer(text)]

        # Estimate duration from keywords
        duration = 1.0
        dur_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)", text, re.I)
        if dur_match:
            duration = float(dur_match.group(1))

        priority = "normal"
        if re.search(r"\b(emergency|critical|urgent)\b", text, re.I):
            priority = "critical"
        elif re.search(r"\bhigh\b", text, re.I):
            priority = "high"

        return FieldJob(
            description=text.strip()[:500],
            required_skills=skills or [SkillCategory.general],
            estimated_duration_hours=duration,
            priority=priority,
            hazards=hazards,
            safety_equipment=safety_equip,
        )


class PermitParser:
    """Parser for permit requirement documents."""

    def parse_permit(self, text: str) -> list[PermitRequirement]:
        """Parse permit text and extract all permit requirements."""
        permits: list[PermitRequirement] = []
        for permit_type, pattern in _PERMIT_KEYWORDS.items():
            if pattern.search(text):
                # Try to extract reference number
                ref_match = re.search(r"(?:ref|reference|permit\s*#|number)\s*[:=]?\s*([\w\-/]+)", text, re.I)
                ref = ref_match.group(1) if ref_match else None

                # Try to extract status
                status = "pending"
                if re.search(r"\b(approved|granted|issued)\b", text, re.I):
                    status = "approved"
                elif re.search(r"\b(rejected|denied|refused)\b", text, re.I):
                    status = "rejected"
                elif re.search(r"\b(expired|lapsed)\b", text, re.I):
                    status = "expired"

                # Extract conditions
                conditions: list[str] = []
                cond_match = re.search(r"(?:conditions?|restrictions?)\s*[:=]\s*(.+?)(?:\n\n|\Z)", text, re.I | re.DOTALL)
                if cond_match:
                    for line in cond_match.group(1).strip().split("\n"):
                        line = line.strip().lstrip("-*# ")
                        if line:
                            conditions.append(line)

                permits.append(
                    PermitRequirement(
                        permit_type=permit_type,
                        status=status,
                        reference_number=ref,
                        valid_from=_parse_date(text),
                        conditions=conditions,
                    )
                )
        return permits
