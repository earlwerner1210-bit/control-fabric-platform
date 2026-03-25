"""Parsers for engineer profiles and accreditation documents.

Uses regex-based extraction to pull structured data from engineer
profile text, including skills, certifications, and availability.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from ..schemas.field_schemas import Accreditation, EngineerProfile, SkillRecord
from ..taxonomy.field_taxonomy import SkillCategory

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_SKILL_KEYWORDS: dict[SkillCategory, re.Pattern[str]] = {
    SkillCategory.electrical: re.compile(r"\b(electric|wiring|circuit|power|18th\s+edition)\b", re.I),
    SkillCategory.plumbing: re.compile(r"\b(plumb|pipe|water|drain|unvented)\b", re.I),
    SkillCategory.hvac: re.compile(r"\b(hvac|heating|ventilation|air\s+condition|f-gas|refrigerant)\b", re.I),
    SkillCategory.gas: re.compile(r"\b(gas\s+safe|gas\s+engineer|ccn1|acs|boiler|flue)\b", re.I),
    SkillCategory.fiber: re.compile(r"\b(fib[re]+|optical|splice|blown\s+fibre|gpon|ftth)\b", re.I),
    SkillCategory.general: re.compile(r"\b(general|multi[- ]?skill|handyman)\b", re.I),
}

_PROFICIENCY_KEYWORDS = {
    "expert": re.compile(r"\b(expert|senior|master|lead|advanced|10\+\s+years?)\b", re.I),
    "competent": re.compile(r"\b(competent|qualified|experienced|mid[- ]?level|5\+?\s+years?)\b", re.I),
    "trainee": re.compile(r"\b(trainee|apprentice|junior|entry|learning|1[- ]?2\s+years?)\b", re.I),
}

_ACCREDITATION_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("Gas Safe Register", "Gas Safe Register", re.compile(r"gas\s+safe\s+(?:register|registered|reg)", re.I)),
    ("18th Edition Wiring", "IET / BSI", re.compile(r"18th\s+edition|bs\s*7671", re.I)),
    ("CSCS Card", "CSCS", re.compile(r"cscs\s+card|construction\s+skills", re.I)),
    ("IPAF Licence", "IPAF", re.compile(r"ipaf|powered\s+access", re.I)),
    ("PASMA Certificate", "PASMA", re.compile(r"pasma|mobile\s+access\s+tower", re.I)),
    ("Confined Space", "City & Guilds", re.compile(r"confined\s+space\s+(?:cert|trained|qualified)", re.I)),
    ("F-Gas Certificate", "City & Guilds", re.compile(r"f[- ]?gas\s+(?:cert|qualified|registered)", re.I)),
    ("ECS Card", "JIB / ECS", re.compile(r"ecs\s+card|jib\s+card", re.I)),
    ("First Aid", "Various", re.compile(r"first\s+aid\s+(?:at\s+work|trained|cert)", re.I)),
    ("Asbestos Awareness", "UKATA", re.compile(r"asbestos\s+(?:awareness|trained|cert)", re.I)),
]

_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")
_YEARS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\s*(?:experience|exp)?", re.I)
_CERT_NUMBER_PATTERN = re.compile(r"(?:cert(?:ificate)?|reg(?:istration)?|licence|card)\s*(?:#|no|number)?\s*[:=]?\s*([\w\-/]+)", re.I)

_FIELD_PATTERNS = {
    "name": re.compile(r"(?:name|engineer)\s*[:=]\s*(.+?)(?:\n|$)", re.I),
    "employee_number": re.compile(r"(?:employee|staff|badge|id)\s*(?:number|no|#)?\s*[:=]\s*([\w\-]+)", re.I),
    "location": re.compile(r"(?:base|location|depot|office)\s*[:=]\s*(.+?)(?:\n|$)", re.I),
    "travel_radius": re.compile(r"(?:travel|radius|range)\s*[:=]\s*(\d+)\s*(?:km|miles?)?", re.I),
}


class EngineerProfileParser:
    """Parser for extracting structured engineer profile data from text."""

    def parse_profile(self, text: str) -> EngineerProfile:
        """Parse engineer profile text into an EngineerProfile.

        Args:
            text: Raw text description of an engineer's profile.

        Returns:
            EngineerProfile with all extractable fields populated.
        """
        name = self._extract_field(text, "name") or "Unknown Engineer"
        employee_number = self._extract_field(text, "employee_number")
        location = self._extract_field(text, "location") or ""

        travel_str = self._extract_field(text, "travel_radius")
        travel_radius = float(travel_str) if travel_str else 50.0

        skills = self._extract_skills(text)
        accreditations = self._extract_accreditations(text)

        available = not bool(re.search(r"\b(unavailable|on\s+leave|off\s+sick|absent)\b", text, re.I))

        # Check for current assignment
        assignment_match = re.search(r"(?:current|assigned\s+to|working\s+on)\s*[:=]?\s*([\w\-]+)", text, re.I)
        current_assignment = assignment_match.group(1) if assignment_match else None

        return EngineerProfile(
            name=name,
            employee_number=employee_number,
            skills=skills,
            accreditations=accreditations,
            base_location=location,
            max_travel_radius_km=travel_radius,
            available=available,
            current_assignment=current_assignment,
        )

    def _extract_skills(self, text: str) -> list[SkillRecord]:
        """Extract skill records from profile text."""
        skills: list[SkillRecord] = []
        for category, pattern in _SKILL_KEYWORDS.items():
            matches = pattern.finditer(text)
            for match in matches:
                # Get context around the match for proficiency detection
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end]

                proficiency = "competent"
                for level, prof_pattern in _PROFICIENCY_KEYWORDS.items():
                    if prof_pattern.search(context):
                        proficiency = level
                        break

                years = 0.0
                years_match = _YEARS_PATTERN.search(context)
                if years_match:
                    years = float(years_match.group(1))

                # Avoid duplicates for same category
                if not any(s.category == category for s in skills):
                    skills.append(
                        SkillRecord(
                            category=category,
                            name=match.group(0).strip(),
                            proficiency_level=proficiency,
                            years_experience=years,
                        )
                    )
        return skills

    def _extract_accreditations(self, text: str) -> list[Accreditation]:
        """Extract accreditation records from profile text."""
        accreditations: list[Accreditation] = []
        for name, issuer, pattern in _ACCREDITATION_PATTERNS:
            if pattern.search(text):
                # Get context for date extraction
                match = pattern.search(text)
                if match:
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 150)
                    context = text[start:end]

                    dates = _DATE_PATTERN.findall(context)
                    issued = None
                    expiry = None
                    if dates:
                        try:
                            issued = date.fromisoformat(dates[0])
                        except ValueError:
                            pass
                        if len(dates) > 1:
                            try:
                                expiry = date.fromisoformat(dates[1])
                            except ValueError:
                                pass

                    cert_match = _CERT_NUMBER_PATTERN.search(context)
                    cert_number = cert_match.group(1) if cert_match else None

                    # Determine skill categories
                    categories: list[SkillCategory] = []
                    for cat, skill_pattern in _SKILL_KEYWORDS.items():
                        if skill_pattern.search(name) or skill_pattern.search(context):
                            categories.append(cat)

                    is_mandatory = bool(re.search(r"\b(mandatory|legally\s+required|statutory)\b", context, re.I))

                    accreditations.append(
                        Accreditation(
                            name=name,
                            issuing_body=issuer,
                            certificate_number=cert_number,
                            issued_date=issued,
                            expiry_date=expiry,
                            categories=categories,
                            is_mandatory=is_mandatory,
                        )
                    )
        return accreditations

    def _extract_field(self, text: str, field_name: str) -> Optional[str]:
        """Extract a named field value from text."""
        pattern = _FIELD_PATTERNS.get(field_name)
        if pattern:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        return None


class AccreditationParser:
    """Parser specifically for accreditation and certification documents."""

    def parse_accreditations(self, text: str) -> list[Accreditation]:
        """Parse accreditation document text into Accreditation records.

        Args:
            text: Raw text of an accreditation document or list.

        Returns:
            List of Accreditation objects found in the text.
        """
        accreditations: list[Accreditation] = []
        for name, issuer, pattern in _ACCREDITATION_PATTERNS:
            if pattern.search(text):
                dates = _DATE_PATTERN.findall(text)
                issued = None
                expiry = None
                if dates:
                    try:
                        issued = date.fromisoformat(dates[0])
                    except ValueError:
                        pass
                    if len(dates) > 1:
                        try:
                            expiry = date.fromisoformat(dates[1])
                        except ValueError:
                            pass

                cert_match = _CERT_NUMBER_PATTERN.search(text)
                cert_number = cert_match.group(1) if cert_match else None

                accreditations.append(
                    Accreditation(
                        name=name,
                        issuing_body=issuer,
                        certificate_number=cert_number,
                        issued_date=issued,
                        expiry_date=expiry,
                    )
                )
        return accreditations
