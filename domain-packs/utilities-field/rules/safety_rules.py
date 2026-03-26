"""Safety rule engine for evaluating field engineer safety compliance.

Checks safety certifications required for specific hazardous work types
including confined spaces, height works, hot works, and gas work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..schemas.field_schemas import (
    ComplianceBlocker,
    EngineerProfile,
    ParsedWorkOrder,
)
from ..taxonomy.field_taxonomy import PermitType


@dataclass
class SafetyCheckResult:
    """Result of a single safety compliance check."""

    rule_name: str
    passed: bool
    message: str
    severity: str = "info"  # info, warning, blocking
    required_action: str = ""


class SafetyRuleEngine:
    """Evaluates safety compliance for field operations.

    Checks whether engineers hold the necessary safety certifications
    and whether work orders have appropriate safety provisions.
    """

    def evaluate(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> list[ComplianceBlocker]:
        """Run all safety rules and return any blockers.

        Args:
            work_order: The work order being evaluated.
            engineer: The engineer assigned to the work.

        Returns:
            List of ComplianceBlocker for any failed safety checks.
        """
        blockers: list[ComplianceBlocker] = []
        checks = [
            self._confined_space_certified(work_order, engineer),
            self._height_works_certified(work_order, engineer),
            self._hot_works_certified(work_order, engineer),
            self._gas_safe_registered(work_order, engineer),
        ]

        for check in checks:
            if not check.passed:
                blockers.append(
                    ComplianceBlocker(
                        category="safety",
                        description=check.message,
                        severity=check.severity,
                        resolution_action=check.required_action,
                    )
                )

        return blockers

    def evaluate_detailed(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> list[SafetyCheckResult]:
        """Run all safety rules and return detailed results including passes.

        Args:
            work_order: The work order being evaluated.
            engineer: The engineer assigned to the work.

        Returns:
            List of SafetyCheckResult for all checks.
        """
        return [
            self._confined_space_certified(work_order, engineer),
            self._height_works_certified(work_order, engineer),
            self._hot_works_certified(work_order, engineer),
            self._gas_safe_registered(work_order, engineer),
        ]

    def _confined_space_certified(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> SafetyCheckResult:
        """Check confined space certification if required."""
        requires_confined = self._work_requires_permit(work_order, PermitType.confined_space)
        requires_confined = requires_confined or self._jobs_mention_hazard(
            work_order, ["confined space", "manhole", "chamber"]
        )

        if not requires_confined:
            return SafetyCheckResult(
                rule_name="confined_space_certified",
                passed=True,
                message="Confined space certification not required for this work order.",
            )

        if self._engineer_has_accreditation(engineer, "Confined Space"):
            return SafetyCheckResult(
                rule_name="confined_space_certified",
                passed=True,
                message="Engineer holds valid confined space certification.",
            )

        return SafetyCheckResult(
            rule_name="confined_space_certified",
            passed=False,
            message="Work requires confined space entry but engineer lacks certification.",
            severity="blocking",
            required_action=(
                "Engineer must complete confined space training and obtain certification "
                "before undertaking this work. Alternative: assign a certified engineer."
            ),
        )

    def _height_works_certified(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> SafetyCheckResult:
        """Check height works certification (IPAF/PASMA) if required."""
        requires_height = self._work_requires_permit(work_order, PermitType.height_works)
        requires_height = requires_height or self._jobs_mention_hazard(
            work_order, ["height", "ladder", "scaffold", "aerial", "cherry picker"]
        )

        if not requires_height:
            return SafetyCheckResult(
                rule_name="height_works_certified",
                passed=True,
                message="Height works certification not required for this work order.",
            )

        has_ipaf = self._engineer_has_accreditation(engineer, "IPAF")
        has_pasma = self._engineer_has_accreditation(engineer, "PASMA")

        if has_ipaf or has_pasma:
            cert_name = "IPAF" if has_ipaf else "PASMA"
            return SafetyCheckResult(
                rule_name="height_works_certified",
                passed=True,
                message=f"Engineer holds valid {cert_name} certification for height works.",
            )

        return SafetyCheckResult(
            rule_name="height_works_certified",
            passed=False,
            message="Work requires working at height but engineer lacks IPAF/PASMA certification.",
            severity="blocking",
            required_action=(
                "Engineer must obtain IPAF licence (powered access) or PASMA certificate "
                "(mobile towers) before undertaking height works."
            ),
        )

    def _hot_works_certified(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> SafetyCheckResult:
        """Check hot works certification if required."""
        requires_hot = self._work_requires_permit(work_order, PermitType.hot_works)
        requires_hot = requires_hot or self._jobs_mention_hazard(
            work_order, ["welding", "soldering", "brazing", "grinding", "hot works"]
        )

        if not requires_hot:
            return SafetyCheckResult(
                rule_name="hot_works_certified",
                passed=True,
                message="Hot works certification not required for this work order.",
            )

        # Check for any relevant fire/hot works accreditation
        has_cert = any(
            "hot" in a.name.lower() or "welding" in a.name.lower() or "fire" in a.name.lower()
            for a in engineer.accreditations
            if not (a.expiry_date and a.expiry_date < date.today())
        )

        if has_cert:
            return SafetyCheckResult(
                rule_name="hot_works_certified",
                passed=True,
                message="Engineer holds valid hot works certification.",
            )

        return SafetyCheckResult(
            rule_name="hot_works_certified",
            passed=False,
            message="Work involves hot works but engineer lacks appropriate certification.",
            severity="blocking",
            required_action=(
                "Engineer must complete hot works safety training and obtain permit "
                "before undertaking welding, soldering, or grinding activities."
            ),
        )

    def _gas_safe_registered(
        self,
        work_order: ParsedWorkOrder,
        engineer: EngineerProfile,
    ) -> SafetyCheckResult:
        """Check Gas Safe Register status for gas-related work."""
        requires_gas = any(s.value == "gas" for s in work_order.required_skills)
        requires_gas = requires_gas or self._jobs_mention_hazard(
            work_order, ["gas", "boiler", "flue", "combustion"]
        )

        if not requires_gas:
            return SafetyCheckResult(
                rule_name="gas_safe_registered",
                passed=True,
                message="Gas Safe registration not required for this work order.",
            )

        has_gas_safe = self._engineer_has_accreditation(engineer, "Gas Safe")

        if has_gas_safe:
            return SafetyCheckResult(
                rule_name="gas_safe_registered",
                passed=True,
                message="Engineer is Gas Safe registered.",
            )

        return SafetyCheckResult(
            rule_name="gas_safe_registered",
            passed=False,
            message=(
                "Work involves gas appliances/pipework but engineer is not Gas Safe registered. "
                "It is ILLEGAL to carry out gas work without Gas Safe registration."
            ),
            severity="blocking",
            required_action=(
                "Only a Gas Safe registered engineer may work on gas installations. "
                "Assign a Gas Safe registered engineer immediately."
            ),
        )

    # ----- Helpers -----

    def _work_requires_permit(
        self,
        work_order: ParsedWorkOrder,
        permit_type: PermitType,
    ) -> bool:
        """Check if work order has a required permit of the given type."""
        return any(p.permit_type == permit_type for p in work_order.required_permits)

    def _jobs_mention_hazard(
        self,
        work_order: ParsedWorkOrder,
        keywords: list[str],
    ) -> bool:
        """Check if any job description or hazard list mentions the keywords."""
        for job in work_order.jobs:
            text = f"{job.description} {' '.join(job.hazards)}".lower()
            for kw in keywords:
                if kw.lower() in text:
                    return True
        return False

    def _engineer_has_accreditation(
        self,
        engineer: EngineerProfile,
        name_substring: str,
    ) -> bool:
        """Check if engineer has a valid (non-expired) accreditation matching the name."""
        today = date.today()
        for accred in engineer.accreditations:
            if name_substring.lower() in accred.name.lower():
                if accred.expiry_date and accred.expiry_date < today:
                    continue  # expired
                return True
        return False
