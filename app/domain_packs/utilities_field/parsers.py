"""Utilities Field domain parsers."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.domain_packs.utilities_field.schemas import (
    Accreditation,
    EngineerProfile,
    ExceptionType,
    FieldExceptionClassification,
    MaterialRequirement,
    MissingPrerequisite,
    ParsedWorkOrder,
    PermitRequirement,
    PermitType,
    PreconditionType,
    RepeatVisitRisk,
    RiskLevel,
    SafetyPreconditionObject,
    SkillCategory,
    SkillFitAnalysis,
    SkillRecord,
    WorkOrderType,
)


# ---------------------------------------------------------------------------
# Work order type -> required safety preconditions mapping
# ---------------------------------------------------------------------------

_SAFETY_MAP: dict[str, list[dict]] = {
    "confined_space": [
        {"type": PreconditionType.certification, "desc": "Confined space entry certification required"},
        {"type": PreconditionType.risk_assessment, "desc": "Confined space risk assessment required"},
        {"type": PreconditionType.ppe, "desc": "Gas monitor and harness required"},
        {"type": PreconditionType.toolbox_talk, "desc": "Confined space toolbox talk required"},
    ],
    "hot_works": [
        {"type": PreconditionType.certification, "desc": "Hot works certification required"},
        {"type": PreconditionType.risk_assessment, "desc": "Fire risk assessment required"},
        {"type": PreconditionType.ppe, "desc": "Fire-resistant PPE required"},
    ],
    "height_works": [
        {"type": PreconditionType.certification, "desc": "Working at height certification required"},
        {"type": PreconditionType.risk_assessment, "desc": "Height risk assessment required"},
        {"type": PreconditionType.ppe, "desc": "Harness and lanyard required"},
        {"type": PreconditionType.method_statement, "desc": "Working at height method statement required"},
    ],
    "street_works": [
        {"type": PreconditionType.ppe, "desc": "High-visibility clothing required"},
        {"type": PreconditionType.risk_assessment, "desc": "Street works traffic management risk assessment required"},
    ],
}

_EXCEPTION_KEYWORD_MAP: dict[str, ExceptionType] = {
    "rework": ExceptionType.rework,
    "redo": ExceptionType.rework,
    "failed inspection": ExceptionType.rework,
    "revisit": ExceptionType.revisit,
    "return visit": ExceptionType.revisit,
    "follow-up": ExceptionType.revisit,
    "no access": ExceptionType.no_access,
    "not in": ExceptionType.no_access,
    "locked": ExceptionType.no_access,
    "safety stop": ExceptionType.safety_stop,
    "unsafe": ExceptionType.safety_stop,
    "hazard": ExceptionType.safety_stop,
    "wrong part": ExceptionType.wrong_materials,
    "wrong material": ExceptionType.wrong_materials,
    "incorrect materials": ExceptionType.wrong_materials,
    "not qualified": ExceptionType.skill_gap,
    "skill gap": ExceptionType.skill_gap,
    "unable to complete": ExceptionType.skill_gap,
    "weather": ExceptionType.weather,
    "rain": ExceptionType.weather,
    "wind": ExceptionType.weather,
    "storm": ExceptionType.weather,
    "customer refused": ExceptionType.customer_refusal,
    "customer declined": ExceptionType.customer_refusal,
    "refused entry": ExceptionType.customer_refusal,
}


class WorkOrderParser:
    """Parse work order documents."""

    def parse_work_order(self, text_or_payload: str | dict) -> ParsedWorkOrder:
        if isinstance(text_or_payload, dict):
            return self._from_json(text_or_payload)
        return self._from_text(text_or_payload)

    # ----- structured payload --------------------------------------------------

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
            site_id=data.get("site_id", ""),
            scheduled_end=data.get("scheduled_end"),
            dependencies=data.get("dependencies", []),
            materials_required=data.get("materials_required", []),
            special_instructions=data.get("special_instructions", ""),
            linked_contract_id=data.get("linked_contract_id"),
            customer_confirmed=data.get("customer_confirmed", False),
            weather_conditions=data.get("weather_conditions"),
        )

    # ----- free-text payload ---------------------------------------------------

    def _from_text(self, text: str) -> ParsedWorkOrder:
        wo_id_match = re.search(r"WO[-_]?(\w+)", text)
        priority = "normal"
        if re.search(r"\b(urgent|emergency|critical)\b", text, re.IGNORECASE):
            priority = "emergency"
        elif re.search(r"\bhigh\b", text, re.IGNORECASE):
            priority = "high"

        location_match = re.search(r"(?:location|site|address)[:\s]+(.+?)(?:\n|$)", text, re.IGNORECASE)

        return ParsedWorkOrder(
            work_order_id=wo_id_match.group(0) if wo_id_match else "unknown",
            description=text[:500],
            priority=priority,
            location=location_match.group(1).strip() if location_match else "",
        )

    # ----- dependency extraction -----------------------------------------------

    def extract_dependencies(self, payload: dict) -> list[dict]:
        """Parse prerequisite work orders, permits, and approvals from payload."""
        dependencies: list[dict] = []

        for dep in payload.get("dependencies", []):
            dep_entry: dict[str, Any] = {
                "dependency_id": dep.get("id", dep.get("work_order_id", "")),
                "type": dep.get("type", "work_order"),
                "description": dep.get("description", ""),
                "status": dep.get("status", "pending"),
                "blocking": dep.get("blocking", True),
                "resolved": dep.get("status", "pending") in ("completed", "resolved", "approved"),
            }
            dependencies.append(dep_entry)

        for prereq in payload.get("prerequisites", []):
            dep_entry = {
                "dependency_id": prereq.get("id", ""),
                "type": prereq.get("type", "prerequisite"),
                "description": prereq.get("description", str(prereq)),
                "status": prereq.get("status", "pending"),
                "blocking": prereq.get("blocking", True),
                "resolved": prereq.get("status", "pending") in ("completed", "resolved"),
            }
            dependencies.append(dep_entry)

        for permit_data in payload.get("required_permits", []):
            if not permit_data.get("obtained", False):
                dependencies.append({
                    "dependency_id": permit_data.get("reference", ""),
                    "type": "permit",
                    "description": f"Permit required: {permit_data.get('permit_type', 'unknown')}",
                    "status": "pending",
                    "blocking": permit_data.get("required", True),
                    "resolved": False,
                })

        return dependencies

    # ----- material extraction -------------------------------------------------

    def extract_materials(self, payload: dict) -> list[MaterialRequirement]:
        """Parse material requirements with availability information."""
        materials: list[MaterialRequirement] = []
        for mat in payload.get("materials_required", []):
            materials.append(MaterialRequirement(
                material_id=mat.get("material_id", mat.get("id", "")),
                description=mat.get("description", mat.get("name", "")),
                quantity=float(mat.get("quantity", 1)),
                unit=mat.get("unit", "each"),
                available=mat.get("available", True),
                alternative=mat.get("alternative", ""),
            ))
        return materials

    # ----- safety requirement extraction ---------------------------------------

    def extract_safety_requirements(self, payload: dict) -> list[SafetyPreconditionObject]:
        """Parse safety preconditions from work order payload."""
        safety_items: list[SafetyPreconditionObject] = []

        # Explicit safety items from payload
        for item in payload.get("safety_requirements", []):
            ptype = item.get("precondition_type", item.get("type", "ppe"))
            try:
                precondition_type = PreconditionType(ptype)
            except ValueError:
                precondition_type = PreconditionType.ppe
            safety_items.append(SafetyPreconditionObject(
                precondition_type=precondition_type,
                description=item.get("description", ""),
                required=item.get("required", True),
                verified=item.get("verified", False),
                verified_by=item.get("verified_by", ""),
                verified_at=item.get("verified_at", ""),
            ))

        # Derive safety items from permit types
        for permit_data in payload.get("required_permits", []):
            pt = permit_data.get("permit_type", "")
            if pt in _SAFETY_MAP:
                for entry in _SAFETY_MAP[pt]:
                    safety_items.append(SafetyPreconditionObject(
                        precondition_type=entry["type"],
                        description=entry["desc"],
                        required=True,
                        verified=False,
                    ))

        # Always require basic PPE for any work order
        safety_items.append(SafetyPreconditionObject(
            precondition_type=PreconditionType.ppe,
            description="Standard PPE: hard hat, safety boots, hi-vis vest",
            required=True,
            verified=False,
        ))

        return safety_items

    # ----- time constraint extraction ------------------------------------------

    def extract_time_constraints(self, payload: dict) -> dict:
        """Parse time windows, blackout periods, and customer availability."""
        constraints: dict[str, Any] = {
            "scheduled_start": payload.get("scheduled_date") or payload.get("scheduled_start"),
            "scheduled_end": payload.get("scheduled_end"),
            "blackout_periods": payload.get("blackout_periods", []),
            "customer_availability": payload.get("customer_availability", {}),
            "time_window_valid": True,
            "issues": [],
        }

        start = constraints["scheduled_start"]
        end = constraints["scheduled_end"]

        if start and end:
            try:
                start_dt = datetime.fromisoformat(start)
                end_dt = datetime.fromisoformat(end)
                if end_dt <= start_dt:
                    constraints["time_window_valid"] = False
                    constraints["issues"].append("Scheduled end is before or equal to scheduled start")
                duration_hours = (end_dt - start_dt).total_seconds() / 3600
                estimated = payload.get("estimated_duration_hours", 0)
                if estimated and duration_hours < estimated:
                    constraints["issues"].append(
                        f"Time window ({duration_hours:.1f}h) shorter than estimated duration ({estimated}h)"
                    )
            except (ValueError, TypeError):
                constraints["issues"].append("Unable to parse scheduled dates")

        if start:
            try:
                start_dt = datetime.fromisoformat(start)
                if start_dt < datetime.now():
                    constraints["issues"].append("Scheduled start is in the past")
            except (ValueError, TypeError):
                pass

        for bp in constraints["blackout_periods"]:
            bp_start = bp.get("start")
            bp_end = bp.get("end")
            if bp_start and bp_end and start:
                try:
                    bp_s = datetime.fromisoformat(bp_start)
                    bp_e = datetime.fromisoformat(bp_end)
                    s = datetime.fromisoformat(start)
                    if bp_s <= s <= bp_e:
                        constraints["time_window_valid"] = False
                        constraints["issues"].append(
                            f"Scheduled start falls within blackout period: {bp.get('reason', 'N/A')}"
                        )
                except (ValueError, TypeError):
                    pass

        return constraints


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

    # ----- accreditation validity check ----------------------------------------

    def check_accreditation_validity(self, accreditations: list[Accreditation]) -> list[dict]:
        """Check expiry dates on accreditations; flag expired or expiring-soon items."""
        results: list[dict] = []
        now = datetime.now()

        for accred in accreditations:
            entry: dict[str, Any] = {
                "name": accred.name,
                "issuing_body": accred.issuing_body,
                "status": "valid",
                "days_remaining": None,
                "expired": False,
                "expiring_soon": False,
            }

            if accred.valid_to:
                try:
                    exp_date = datetime.fromisoformat(accred.valid_to)
                    days_left = (exp_date - now).days
                    entry["days_remaining"] = days_left
                    if days_left < 0:
                        entry["status"] = "expired"
                        entry["expired"] = True
                    elif days_left < 30:
                        entry["status"] = "expiring_soon"
                        entry["expiring_soon"] = True
                    else:
                        entry["status"] = "valid"
                except (ValueError, TypeError):
                    entry["status"] = "unparseable_date"

            if not accred.is_valid:
                entry["status"] = "revoked"
                entry["expired"] = True

            results.append(entry)

        return results

    # ----- skill-to-requirement matching ---------------------------------------

    def match_skills_to_requirements(
        self, engineer: EngineerProfile, requirements: list[SkillRecord]
    ) -> SkillFitAnalysis:
        """Detailed skill matching with gap analysis."""
        required_names = {s.skill_name.lower() for s in requirements}
        available_map = {s.skill_name.lower(): s for s in engineer.skills}

        matching: list[str] = []
        missing: list[str] = []

        for req in requirements:
            key = req.skill_name.lower()
            eng_skill = available_map.get(key)
            if eng_skill is None:
                missing.append(req.skill_name)
            else:
                # Level check: trainee cannot fulfil expert requirements
                level_order = {"trainee": 0, "qualified": 1, "expert": 2}
                req_level = level_order.get(req.level, 1)
                eng_level = level_order.get(eng_skill.level, 1)
                if eng_level < req_level:
                    missing.append(f"{req.skill_name} (requires {req.level}, has {eng_skill.level})")
                else:
                    matching.append(req.skill_name)

        # Expiring accreditations
        expiring: list[str] = []
        now = datetime.now()
        for accred in engineer.accreditations:
            if accred.valid_to:
                try:
                    exp_date = datetime.fromisoformat(accred.valid_to)
                    days_left = (exp_date - now).days
                    if 0 < days_left < 30:
                        expiring.append(f"{accred.name} (expires in {days_left} days)")
                except (ValueError, TypeError):
                    pass

        return SkillFitAnalysis(
            fit=len(missing) == 0,
            matching_skills=sorted(matching),
            missing_skills=sorted(missing),
            expiring_soon=expiring,
        )


class PermitParser:
    """Parse and validate permits for field operations."""

    def parse_permits(self, text_or_data: str | list | dict) -> list[PermitRequirement]:
        """Parse permit information from text or structured data."""
        if isinstance(text_or_data, list):
            return [self._parse_single_permit(p) for p in text_or_data]
        if isinstance(text_or_data, dict):
            return [self._parse_single_permit(text_or_data)]
        # Free text
        return self._parse_permits_from_text(text_or_data)

    def _parse_single_permit(self, data: dict) -> PermitRequirement:
        pt = data.get("permit_type", "building_access")
        try:
            permit_type = PermitType(pt)
        except ValueError:
            permit_type = PermitType.building_access
        return PermitRequirement(
            permit_type=permit_type,
            description=data.get("description", ""),
            required=data.get("required", True),
            obtained=data.get("obtained", False),
            reference=data.get("reference", ""),
        )

    def _parse_permits_from_text(self, text: str) -> list[PermitRequirement]:
        permits: list[PermitRequirement] = []
        permit_patterns: dict[str, PermitType] = {
            r"street\s*works?\s*permit": PermitType.street_works,
            r"building\s*access\s*permit": PermitType.building_access,
            r"confined\s*space\s*permit": PermitType.confined_space,
            r"hot\s*works?\s*permit": PermitType.hot_works,
            r"(?:height|working at height)\s*permit": PermitType.height_works,
        }
        for pattern, pt in permit_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                permits.append(PermitRequirement(
                    permit_type=pt,
                    description=f"Detected from text: {pt.value}",
                    required=True,
                    obtained=False,
                ))
        return permits

    def check_permit_validity(self, permits: list[PermitRequirement]) -> list[dict]:
        """Check each permit's validity status."""
        results: list[dict] = []
        for permit in permits:
            results.append({
                "permit_type": permit.permit_type.value,
                "required": permit.required,
                "obtained": permit.obtained,
                "valid": permit.obtained or not permit.required,
                "reference": permit.reference,
                "issue": "" if (permit.obtained or not permit.required) else f"Required permit {permit.permit_type.value} not obtained",
            })
        return results

    def detect_missing_permits(
        self, work_order: ParsedWorkOrder, available_permits: list[PermitRequirement]
    ) -> list[MissingPrerequisite]:
        """Detect permits required by the work order but not available."""
        available_types = {p.permit_type for p in available_permits if p.obtained}
        missing: list[MissingPrerequisite] = []

        for req in work_order.required_permits:
            if req.required and req.permit_type not in available_types:
                resolution_hours = {
                    PermitType.street_works: 48.0,
                    PermitType.building_access: 24.0,
                    PermitType.confined_space: 72.0,
                    PermitType.hot_works: 24.0,
                    PermitType.height_works: 24.0,
                }.get(req.permit_type, 24.0)

                missing.append(MissingPrerequisite(
                    prerequisite_type="permit",
                    description=f"Missing required permit: {req.permit_type.value}",
                    severity="error",
                    resolution_action=f"Obtain {req.permit_type.value} permit from issuing authority",
                    estimated_resolution_time_hours=resolution_hours,
                    blocking=True,
                ))

        return missing


class FieldLogParser:
    """Parse field engineer logs and notes."""

    def parse_field_notes(self, text: str) -> dict:
        """Extract structured outcomes, exceptions, and issues from field notes."""
        result: dict[str, Any] = {
            "raw_text": text,
            "outcome": "unknown",
            "exceptions": [],
            "issues": [],
            "materials_used": [],
            "time_on_site_hours": None,
            "follow_up_required": False,
        }

        # Determine outcome
        text_lower = text.lower()
        if re.search(r"\b(completed?|finished|done|resolved)\b", text_lower):
            result["outcome"] = "completed"
        elif re.search(r"\b(partial|partly|incomplete)\b", text_lower):
            result["outcome"] = "partial"
            result["follow_up_required"] = True
        elif re.search(r"\b(failed|unable|could not|couldn't|aborted)\b", text_lower):
            result["outcome"] = "failed"
            result["follow_up_required"] = True
        elif re.search(r"\b(no access|locked out|nobody home)\b", text_lower):
            result["outcome"] = "no_access"
            result["follow_up_required"] = True

        # Detect exceptions
        for keyword, exc_type in _EXCEPTION_KEYWORD_MAP.items():
            if keyword in text_lower:
                result["exceptions"].append({
                    "type": exc_type.value,
                    "keyword_match": keyword,
                })

        # Extract time on site
        time_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s*(?:on\s*site)?", text_lower)
        if time_match:
            result["time_on_site_hours"] = float(time_match.group(1))

        # Extract issues (lines starting with - or * that contain problem language)
        for line in text.split("\n"):
            stripped = line.strip().lstrip("-*").strip()
            if stripped and re.search(r"\b(issue|problem|fault|defect|broken|damaged|leak)\b", stripped, re.IGNORECASE):
                result["issues"].append(stripped)

        # Follow-up detection
        if re.search(r"\b(follow[\s-]?up|return|revisit|come back|reschedule)\b", text_lower):
            result["follow_up_required"] = True

        return result

    def classify_field_exception(self, notes: str) -> FieldExceptionClassification:
        """Classify a field exception from engineer notes."""
        notes_lower = notes.lower()

        # Find the best-matching exception type
        matched_type = ExceptionType.rework  # default
        for keyword, exc_type in _EXCEPTION_KEYWORD_MAP.items():
            if keyword in notes_lower:
                matched_type = exc_type
                break

        # Determine root cause heuristics
        root_cause = "unknown"
        preventable = False
        cost_impact = 0.0
        recommended_action = ""

        if matched_type == ExceptionType.rework:
            root_cause = "Initial work did not meet quality standards"
            preventable = True
            cost_impact = 150.0
            recommended_action = "Review quality checklist before sign-off"
        elif matched_type == ExceptionType.revisit:
            root_cause = "Work could not be completed in a single visit"
            preventable = True
            cost_impact = 120.0
            recommended_action = "Improve pre-visit scoping and material preparation"
        elif matched_type == ExceptionType.no_access:
            root_cause = "Customer not available or site inaccessible"
            preventable = True
            cost_impact = 80.0
            recommended_action = "Confirm customer availability 24h before dispatch"
        elif matched_type == ExceptionType.safety_stop:
            root_cause = "Safety hazard identified on site"
            preventable = False
            cost_impact = 200.0
            recommended_action = "Escalate to safety officer for assessment"
        elif matched_type == ExceptionType.wrong_materials:
            root_cause = "Incorrect or insufficient materials provisioned"
            preventable = True
            cost_impact = 100.0
            recommended_action = "Validate material requirements against work order spec"
        elif matched_type == ExceptionType.skill_gap:
            root_cause = "Engineer lacked required skill or qualification"
            preventable = True
            cost_impact = 150.0
            recommended_action = "Verify engineer skill fit before dispatch"
        elif matched_type == ExceptionType.weather:
            root_cause = "Adverse weather conditions prevented safe work"
            preventable = False
            cost_impact = 60.0
            recommended_action = "Check weather forecast before scheduling outdoor work"
        elif matched_type == ExceptionType.customer_refusal:
            root_cause = "Customer refused to allow work to proceed"
            preventable = False
            cost_impact = 80.0
            recommended_action = "Re-engage customer through account management"

        return FieldExceptionClassification(
            exception_type=matched_type,
            description=notes[:200],
            root_cause=root_cause,
            preventable=preventable,
            cost_impact=cost_impact,
            recommended_action=recommended_action,
        )

    def detect_repeat_visit_risk(self, history: list[dict]) -> RepeatVisitRisk:
        """Assess repeat-visit risk based on visit history."""
        if not history:
            return RepeatVisitRisk(
                risk_level=RiskLevel.low,
                contributing_factors=[],
                previous_visit_count=0,
                recommended_mitigations=[],
            )

        visit_count = len(history)
        factors: list[str] = []
        mitigations: list[str] = []

        # Count unsuccessful visits
        failed_count = sum(
            1 for h in history
            if h.get("outcome", "") in ("failed", "partial", "no_access", "aborted")
        )

        if failed_count > 0:
            factors.append(f"{failed_count} of {visit_count} previous visits were unsuccessful")
            mitigations.append("Review previous visit notes for root cause")

        # Check for recurring issues
        exception_types = [h.get("exception_type") for h in history if h.get("exception_type")]
        if len(exception_types) != len(set(exception_types)):
            factors.append("Same exception type recurring across visits")
            mitigations.append("Escalate to supervisor for root cause analysis")

        # Check for no-access pattern
        no_access_count = sum(1 for h in history if h.get("outcome") == "no_access")
        if no_access_count >= 2:
            factors.append(f"{no_access_count} no-access events")
            mitigations.append("Arrange confirmed appointment with customer")

        # Check for material issues
        material_issues = sum(
            1 for h in history
            if h.get("exception_type") in ("wrong_materials", "missing_materials")
        )
        if material_issues > 0:
            factors.append("Material supply issues on previous visits")
            mitigations.append("Pre-validate all material requirements with warehouse")

        # Determine risk level
        if visit_count >= 3 or failed_count >= 2:
            risk_level = RiskLevel.high
            mitigations.append("Assign senior engineer for next visit")
        elif visit_count >= 2 or failed_count >= 1:
            risk_level = RiskLevel.medium
        else:
            risk_level = RiskLevel.low

        return RepeatVisitRisk(
            risk_level=risk_level,
            contributing_factors=factors,
            previous_visit_count=visit_count,
            recommended_mitigations=mitigations,
        )
