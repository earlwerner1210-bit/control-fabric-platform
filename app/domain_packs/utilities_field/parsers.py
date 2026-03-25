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
# Work Order Parser
# ---------------------------------------------------------------------------


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
                level=s.get("level", "qualified") if isinstance(s, dict) else "qualified",
                expiry_date=s.get("expiry_date") if isinstance(s, dict) else None,
            )
            for s in data.get("required_skills", [])
        ]
        permits = [
            PermitRequirement(
                permit_type=PermitType(p.get("permit_type", "building_access")),
                description=p.get("description", ""),
                required=p.get("required", True),
                obtained=p.get("obtained", False),
                reference=p.get("reference", ""),
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

    def _from_text(self, text: str) -> ParsedWorkOrder:
        wo_id_match = re.search(r"WO[-_]?(\w+)", text)
        priority = "normal"
        if re.search(r"\b(urgent|emergency|critical)\b", text, re.IGNORECASE):
            priority = "emergency"
        elif re.search(r"\b(high)\b", text, re.IGNORECASE):
            priority = "high"

        location_match = re.search(r"(?:location|site|address)[:\s]+(.+?)(?:\n|$)", text, re.IGNORECASE)
        customer_match = re.search(r"(?:customer|client)[:\s]+(.+?)(?:\n|$)", text, re.IGNORECASE)

        return ParsedWorkOrder(
            work_order_id=wo_id_match.group(0) if wo_id_match else "unknown",
            description=text[:500],
            priority=priority,
            location=location_match.group(1).strip() if location_match else "",
            customer=customer_match.group(1).strip() if customer_match else "",
        )

    # -----------------------------------------------------------------------
    # Extended extraction methods
    # -----------------------------------------------------------------------

    def extract_dependencies(self, payload: dict) -> list[dict]:
        """Parse prerequisite work orders, permits, and approvals from payload."""
        dependencies: list[dict] = []
        for dep in payload.get("dependencies", []):
            if isinstance(dep, str):
                dependencies.append({
                    "dependency_id": dep,
                    "type": "work_order",
                    "status": "unknown",
                    "blocking": True,
                })
            elif isinstance(dep, dict):
                dependencies.append({
                    "dependency_id": dep.get("id", dep.get("dependency_id", "")),
                    "type": dep.get("type", "work_order"),
                    "status": dep.get("status", "unknown"),
                    "blocking": dep.get("blocking", True),
                    "description": dep.get("description", ""),
                })

        # Also check prerequisites list
        for prereq in payload.get("prerequisites", []):
            if isinstance(prereq, dict) and prereq.get("type") in ("approval", "permit", "inspection"):
                dependencies.append({
                    "dependency_id": prereq.get("id", ""),
                    "type": prereq.get("type", "approval"),
                    "status": prereq.get("status", "pending"),
                    "blocking": prereq.get("blocking", True),
                    "description": prereq.get("description", ""),
                })

        return dependencies

    def extract_materials(self, payload: dict) -> list[MaterialRequirement]:
        """Parse material requirements with availability status."""
        materials: list[MaterialRequirement] = []
        for mat in payload.get("materials_required", payload.get("materials", [])):
            if isinstance(mat, str):
                materials.append(MaterialRequirement(description=mat))
            elif isinstance(mat, dict):
                materials.append(MaterialRequirement(
                    material_id=mat.get("material_id", mat.get("id", "")),
                    description=mat.get("description", mat.get("name", "")),
                    quantity=float(mat.get("quantity", 1)),
                    unit=mat.get("unit", "each"),
                    available=mat.get("available", True),
                    alternative=mat.get("alternative", ""),
                ))
        return materials

    def extract_safety_requirements(self, payload: dict) -> list[SafetyPreconditionObject]:
        """Parse safety preconditions from work order payload."""
        safety_items: list[SafetyPreconditionObject] = []

        for item in payload.get("safety_requirements", payload.get("safety", [])):
            if isinstance(item, dict):
                ptype_raw = item.get("precondition_type", item.get("type", "ppe"))
                try:
                    ptype = PreconditionType(ptype_raw)
                except ValueError:
                    ptype = PreconditionType.ppe
                safety_items.append(SafetyPreconditionObject(
                    precondition_type=ptype,
                    description=item.get("description", ""),
                    required=item.get("required", True),
                    verified=item.get("verified", False),
                    verified_by=item.get("verified_by", ""),
                    verified_at=item.get("verified_at", ""),
                ))

        # Auto-infer safety requirements from work order type
        wo_type = payload.get("work_order_type", "maintenance")
        description = payload.get("description", "").lower()

        if wo_type in ("installation", "repair", "emergency"):
            if not any(s.precondition_type == PreconditionType.risk_assessment for s in safety_items):
                safety_items.append(SafetyPreconditionObject(
                    precondition_type=PreconditionType.risk_assessment,
                    description=f"Risk assessment required for {wo_type} work",
                    required=True,
                ))

        if "confined" in description or any(
            p.get("permit_type") == "confined_space" for p in payload.get("required_permits", [])
        ):
            if not any(s.precondition_type == PreconditionType.method_statement for s in safety_items):
                safety_items.append(SafetyPreconditionObject(
                    precondition_type=PreconditionType.method_statement,
                    description="Method statement required for confined space entry",
                    required=True,
                ))

        if wo_type == "emergency" or "hot work" in description:
            if not any(s.precondition_type == PreconditionType.toolbox_talk for s in safety_items):
                safety_items.append(SafetyPreconditionObject(
                    precondition_type=PreconditionType.toolbox_talk,
                    description="Toolbox talk required before high-risk work",
                    required=True,
                ))

        return safety_items

    def extract_time_constraints(self, payload: dict) -> dict:
        """Parse time windows, blackout periods, and customer availability."""
        constraints: dict[str, Any] = {
            "scheduled_start": payload.get("scheduled_date") or payload.get("scheduled_start"),
            "scheduled_end": payload.get("scheduled_end"),
            "blackout_periods": [],
            "customer_availability_windows": [],
            "max_duration_hours": payload.get("estimated_duration_hours", 0),
            "time_of_day_restriction": None,
        }

        for bp in payload.get("blackout_periods", []):
            if isinstance(bp, dict):
                constraints["blackout_periods"].append({
                    "start": bp.get("start", ""),
                    "end": bp.get("end", ""),
                    "reason": bp.get("reason", ""),
                })

        for window in payload.get("customer_availability", []):
            if isinstance(window, dict):
                constraints["customer_availability_windows"].append({
                    "day": window.get("day", ""),
                    "start_time": window.get("start_time", "08:00"),
                    "end_time": window.get("end_time", "18:00"),
                })
            elif isinstance(window, str):
                constraints["customer_availability_windows"].append({"raw": window})

        restriction = payload.get("time_of_day_restriction")
        if restriction:
            constraints["time_of_day_restriction"] = restriction

        return constraints


# ---------------------------------------------------------------------------
# Engineer Profile Parser
# ---------------------------------------------------------------------------


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

    # -----------------------------------------------------------------------
    # Extended analysis methods
    # -----------------------------------------------------------------------

    def check_accreditation_validity(self, accreditations: list[Accreditation]) -> list[dict]:
        """Check expiry dates and flag expired or expiring-soon accreditations."""
        results: list[dict] = []
        now = datetime.now()

        for accred in accreditations:
            entry: dict[str, Any] = {
                "name": accred.name,
                "issuing_body": accred.issuing_body,
                "status": "valid",
                "days_remaining": None,
                "action_required": None,
            }
            if accred.valid_to:
                try:
                    exp_date = datetime.fromisoformat(accred.valid_to)
                    days_left = (exp_date - now).days
                    entry["days_remaining"] = days_left

                    if days_left < 0:
                        entry["status"] = "expired"
                        entry["action_required"] = f"Renew {accred.name} immediately -- expired {abs(days_left)} days ago"
                    elif days_left < 14:
                        entry["status"] = "expiring_critical"
                        entry["action_required"] = f"Renew {accred.name} urgently -- expires in {days_left} days"
                    elif days_left < 30:
                        entry["status"] = "expiring_soon"
                        entry["action_required"] = f"Schedule renewal for {accred.name} -- expires in {days_left} days"
                    else:
                        entry["status"] = "valid"
                except ValueError:
                    entry["status"] = "unknown"
                    entry["action_required"] = f"Cannot parse expiry date for {accred.name}"

            if not accred.is_valid:
                entry["status"] = "revoked"
                entry["action_required"] = f"{accred.name} has been marked as invalid/revoked"

            results.append(entry)

        return results

    def match_skills_to_requirements(
        self, engineer: EngineerProfile, requirements: list[SkillRecord]
    ) -> SkillFitAnalysis:
        """Detailed skill matching with gap analysis including level comparison."""
        level_rank = {"trainee": 1, "qualified": 2, "expert": 3}

        matching: list[str] = []
        missing: list[str] = []
        expiring: list[str] = []

        engineer_skills = {s.skill_name.lower(): s for s in engineer.skills}

        for req in requirements:
            req_key = req.skill_name.lower()
            eng_skill = engineer_skills.get(req_key)

            if eng_skill is None:
                missing.append(req.skill_name)
                continue

            req_level = level_rank.get(req.level, 2)
            eng_level = level_rank.get(eng_skill.level, 2)

            if eng_level < req_level:
                missing.append(
                    f"{req.skill_name} (has {eng_skill.level}, needs {req.level})"
                )
            else:
                matching.append(req.skill_name)

            if eng_skill.expiry_date:
                try:
                    exp_date = datetime.fromisoformat(eng_skill.expiry_date)
                    days_left = (exp_date - datetime.now()).days
                    if 0 < days_left < 30:
                        expiring.append(f"{eng_skill.skill_name} (expires in {days_left} days)")
                    elif days_left <= 0:
                        missing.append(f"{eng_skill.skill_name} (skill certification expired)")
                except ValueError:
                    pass

        # Also check accreditation expiry
        for accred in engineer.accreditations:
            if accred.valid_to:
                try:
                    exp_date = datetime.fromisoformat(accred.valid_to)
                    days_left = (exp_date - datetime.now()).days
                    if 0 < days_left < 30:
                        expiring.append(f"{accred.name} (expires in {days_left} days)")
                except ValueError:
                    pass

        return SkillFitAnalysis(
            fit=len(missing) == 0,
            matching_skills=sorted(matching),
            missing_skills=sorted(missing),
            expiring_soon=expiring,
        )


# ---------------------------------------------------------------------------
# Permit Parser
# ---------------------------------------------------------------------------


class PermitParser:
    """Parse and validate permit data."""

    _PERMIT_KEYWORDS: dict[str, PermitType] = {
        "street": PermitType.street_works,
        "road": PermitType.street_works,
        "highway": PermitType.street_works,
        "building": PermitType.building_access,
        "access": PermitType.building_access,
        "confined": PermitType.confined_space,
        "hot work": PermitType.hot_works,
        "welding": PermitType.hot_works,
        "height": PermitType.height_works,
        "scaffold": PermitType.height_works,
        "roof": PermitType.height_works,
    }

    def parse_permits(self, text_or_data: str | list | dict) -> list[PermitRequirement]:
        """Parse permit information from text or structured data."""
        if isinstance(text_or_data, list):
            return [self._parse_single_permit(p) for p in text_or_data]
        if isinstance(text_or_data, dict):
            return [self._parse_single_permit(text_or_data)]
        return self._parse_permits_from_text(text_or_data)

    def _parse_single_permit(self, data: dict) -> PermitRequirement:
        ptype_raw = data.get("permit_type", data.get("type", "building_access"))
        try:
            ptype = PermitType(ptype_raw)
        except ValueError:
            ptype = PermitType.building_access
        return PermitRequirement(
            permit_type=ptype,
            description=data.get("description", ""),
            required=data.get("required", True),
            obtained=data.get("obtained", False),
            reference=data.get("reference", ""),
        )

    def _parse_permits_from_text(self, text: str) -> list[PermitRequirement]:
        permits: list[PermitRequirement] = []
        text_lower = text.lower()
        seen_types: set[PermitType] = set()
        for keyword, ptype in self._PERMIT_KEYWORDS.items():
            if keyword in text_lower and ptype not in seen_types:
                seen_types.add(ptype)
                permits.append(PermitRequirement(
                    permit_type=ptype,
                    description=f"Permit inferred from text keyword: '{keyword}'",
                    required=True,
                    obtained=False,
                ))
        return permits

    def check_permit_validity(self, permits: list[PermitRequirement]) -> list[dict]:
        """Check validity status of each permit."""
        results: list[dict] = []
        for permit in permits:
            status = "valid" if permit.obtained else "missing"
            results.append({
                "permit_type": permit.permit_type.value,
                "description": permit.description,
                "required": permit.required,
                "obtained": permit.obtained,
                "reference": permit.reference,
                "status": status,
                "action_required": (
                    None if permit.obtained or not permit.required
                    else f"Obtain {permit.permit_type.value} permit before dispatch"
                ),
            })
        return results

    def detect_missing_permits(
        self,
        work_order: ParsedWorkOrder,
        available_permits: list[PermitRequirement],
    ) -> list[MissingPrerequisite]:
        """Detect permits required by the work order but not available."""
        available_types = {p.permit_type for p in available_permits if p.obtained}
        missing: list[MissingPrerequisite] = []

        for req in work_order.required_permits:
            if req.required and req.permit_type not in available_types:
                hours = self._estimate_permit_lead_time(req.permit_type)
                missing.append(MissingPrerequisite(
                    prerequisite_type="permit",
                    description=f"Missing required permit: {req.permit_type.value}",
                    severity="error",
                    resolution_action=f"Apply for {req.permit_type.value} permit",
                    estimated_resolution_time_hours=hours,
                    blocking=True,
                ))

        return missing

    @staticmethod
    def _estimate_permit_lead_time(permit_type: PermitType) -> float:
        lead_times: dict[PermitType, float] = {
            PermitType.street_works: 120.0,
            PermitType.building_access: 24.0,
            PermitType.confined_space: 48.0,
            PermitType.hot_works: 24.0,
            PermitType.height_works: 48.0,
        }
        return lead_times.get(permit_type, 24.0)


# ---------------------------------------------------------------------------
# Field Log Parser
# ---------------------------------------------------------------------------


class FieldLogParser:
    """Parse and classify field engineer notes and logs."""

    _EXCEPTION_PATTERNS: dict[str, ExceptionType] = {
        r"\bno\s*access\b": ExceptionType.no_access,
        r"\bcustomer\s*(refused|not\s*available|absent)\b": ExceptionType.customer_refusal,
        r"\brework\b": ExceptionType.rework,
        r"\bre[-\s]?visit\b": ExceptionType.revisit,
        r"\bsafety\s*(stop|concern|issue)\b": ExceptionType.safety_stop,
        r"\bwrong\s*material": ExceptionType.wrong_materials,
        r"\bweather\b": ExceptionType.weather,
        r"\b(skill|competency)\s*(gap|lack|missing)\b": ExceptionType.skill_gap,
    }

    def parse_field_notes(self, text: str) -> dict:
        """Extract structured outcomes, exceptions, and issues from free-text field notes."""
        text_lower = text.lower()

        completed = bool(re.search(r"\b(completed|finished|done|resolved)\b", text_lower))
        partial = bool(re.search(r"\b(partial|incomplete|outstanding)\b", text_lower))
        failed = bool(re.search(r"\b(failed|aborted|cancelled|abandoned)\b", text_lower))

        if completed and not failed:
            outcome = "completed"
        elif partial:
            outcome = "partial"
        elif failed:
            outcome = "failed"
        else:
            outcome = "unknown"

        exceptions_found: list[str] = []
        for pattern, exc_type in self._EXCEPTION_PATTERNS.items():
            if re.search(pattern, text_lower):
                exceptions_found.append(exc_type.value)

        follow_up_match = re.search(
            r"(?:follow[- ]?up|next\s*step|action\s*required)[:\s]+(.+?)(?:\n|$)",
            text,
            re.IGNORECASE,
        )

        return {
            "outcome": outcome,
            "exceptions": exceptions_found,
            "follow_up": follow_up_match.group(1).strip() if follow_up_match else None,
            "raw_text": text[:1000],
        }

    def classify_field_exception(self, notes: str) -> FieldExceptionClassification:
        """Classify a field note string into a structured exception."""
        text_lower = notes.lower()

        detected_type = ExceptionType.rework  # default
        for pattern, exc_type in self._EXCEPTION_PATTERNS.items():
            if re.search(pattern, text_lower):
                detected_type = exc_type
                break

        root_cause = self._infer_root_cause(detected_type, text_lower)
        preventable = detected_type in (
            ExceptionType.wrong_materials,
            ExceptionType.skill_gap,
            ExceptionType.rework,
        )
        cost_impact = self._estimate_cost_impact(detected_type)

        return FieldExceptionClassification(
            exception_type=detected_type,
            description=notes[:300],
            root_cause=root_cause,
            preventable=preventable,
            cost_impact=cost_impact,
            recommended_action=self._recommend_action(detected_type),
        )

    def detect_repeat_visit_risk(
        self, history: list[dict], current_work_order: ParsedWorkOrder | None = None
    ) -> RepeatVisitRisk:
        """Analyse visit history and determine repeat-visit risk."""
        if not history:
            return RepeatVisitRisk(risk_level=RiskLevel.low, previous_visit_count=0)

        visit_count = len(history)
        factors: list[str] = []
        mitigations: list[str] = []

        # Count incomplete / failed visits
        failed_count = sum(
            1 for h in history
            if h.get("outcome") in ("failed", "partial", "no_access")
        )
        rework_count = sum(1 for h in history if h.get("outcome") == "rework")

        if failed_count > 0:
            factors.append(f"{failed_count} previous failed/partial visits")
        if rework_count > 0:
            factors.append(f"{rework_count} rework instances")

        # Same site, same issue?
        if current_work_order:
            same_site = sum(
                1 for h in history
                if h.get("site_id") == current_work_order.site_id and current_work_order.site_id
            )
            if same_site >= 2:
                factors.append(f"Site visited {same_site} times previously")

        # Determine risk level
        if visit_count >= 3 or failed_count >= 2:
            risk_level = RiskLevel.high
            mitigations.append("Assign senior engineer for next visit")
            mitigations.append("Conduct root cause analysis before re-dispatch")
            mitigations.append("Review materials and access arrangements")
        elif visit_count >= 2 or failed_count >= 1:
            risk_level = RiskLevel.medium
            mitigations.append("Review previous visit notes before dispatch")
            mitigations.append("Confirm customer access and availability")
        else:
            risk_level = RiskLevel.low

        return RepeatVisitRisk(
            risk_level=risk_level,
            contributing_factors=factors,
            previous_visit_count=visit_count,
            recommended_mitigations=mitigations,
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _infer_root_cause(exc_type: ExceptionType, text: str) -> str:
        causes: dict[ExceptionType, str] = {
            ExceptionType.no_access: "Customer not present or access denied at site",
            ExceptionType.customer_refusal: "Customer refused work or was not available",
            ExceptionType.rework: "Previous work did not meet quality standards or specification",
            ExceptionType.revisit: "Original issue not fully resolved on prior visit",
            ExceptionType.safety_stop: "Safety hazard identified requiring work stoppage",
            ExceptionType.wrong_materials: "Incorrect or insufficient materials provided for the job",
            ExceptionType.weather: "Adverse weather conditions prevented safe working",
            ExceptionType.skill_gap: "Engineer lacked required competency for the task",
        }
        return causes.get(exc_type, "Root cause undetermined -- manual review required")

    @staticmethod
    def _estimate_cost_impact(exc_type: ExceptionType) -> float:
        costs: dict[ExceptionType, float] = {
            ExceptionType.no_access: 150.0,
            ExceptionType.customer_refusal: 150.0,
            ExceptionType.rework: 400.0,
            ExceptionType.revisit: 300.0,
            ExceptionType.safety_stop: 500.0,
            ExceptionType.wrong_materials: 350.0,
            ExceptionType.weather: 200.0,
            ExceptionType.skill_gap: 450.0,
        }
        return costs.get(exc_type, 200.0)

    @staticmethod
    def _recommend_action(exc_type: ExceptionType) -> str:
        actions: dict[ExceptionType, str] = {
            ExceptionType.no_access: "Confirm customer availability and access before next dispatch",
            ExceptionType.customer_refusal: "Contact customer to understand refusal and reschedule",
            ExceptionType.rework: "Assign senior engineer and review original work specification",
            ExceptionType.revisit: "Conduct root-cause analysis and ensure full resolution plan",
            ExceptionType.safety_stop: "Complete updated risk assessment before resuming work",
            ExceptionType.wrong_materials: "Verify bill of materials against work order before dispatch",
            ExceptionType.weather: "Monitor weather forecast and reschedule when conditions improve",
            ExceptionType.skill_gap: "Reassign to engineer with appropriate skill level",
        }
        return actions.get(exc_type, "Review field log and determine corrective action")
