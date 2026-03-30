"""Skill matching engine for evaluating engineer-to-work-order fit.

Compares required skill categories against an engineer's skill records
to produce a quantified fit analysis.
"""

from __future__ import annotations

from ..schemas.field_schemas import EngineerProfile, SkillFitAnalysis
from ..taxonomy.field_taxonomy import SkillCategory

# Mapping of related skill categories for partial matching
_RELATED_SKILLS: dict[SkillCategory, set[SkillCategory]] = {
    SkillCategory.electrical: {SkillCategory.fiber, SkillCategory.general},
    SkillCategory.plumbing: {SkillCategory.general},
    SkillCategory.hvac: {SkillCategory.electrical, SkillCategory.plumbing, SkillCategory.general},
    SkillCategory.gas: {SkillCategory.plumbing, SkillCategory.hvac, SkillCategory.general},
    SkillCategory.fiber: {SkillCategory.electrical, SkillCategory.general},
    SkillCategory.general: set(),
}


class SkillMatchEngine:
    """Evaluates how well an engineer's skills match work order requirements."""

    def evaluate_fit(
        self,
        required_skills: list[SkillCategory],
        engineer: EngineerProfile,
    ) -> SkillFitAnalysis:
        """Assess skill fit between requirements and engineer capabilities.

        Args:
            required_skills: Skill categories required by the work order.
            engineer: The engineer whose skills are being evaluated.

        Returns:
            SkillFitAnalysis with match scores and categorised skill lists.
        """
        if not required_skills:
            return SkillFitAnalysis(
                overall_fit=1.0,
                matched_skills=[],
                missing_skills=[],
                partially_matched=[],
                overqualified_areas=[],
            )

        engineer_categories = {s.category for s in engineer.skills}
        required_set = set(required_skills)

        matched: list[str] = []
        missing: list[str] = []
        partial: list[str] = []

        for req in required_set:
            if req in engineer_categories:
                matched.append(req.value)
            else:
                # Check for partial match via related skills
                related = _RELATED_SKILLS.get(req, set())
                if related & engineer_categories:
                    partial.append(req.value)
                else:
                    missing.append(req.value)

        # Overqualified: engineer has skills beyond what's required
        overqualified = [
            s.category.value
            for s in engineer.skills
            if s.category not in required_set and s.proficiency_level == "expert"
        ]

        # Calculate overall fit
        total_required = len(required_set)
        full_match_score = len(matched) / total_required if total_required > 0 else 1.0
        partial_match_score = (len(partial) * 0.5) / total_required if total_required > 0 else 0.0

        # Bonus for proficiency level on matched skills
        proficiency_bonus = 0.0
        for skill in engineer.skills:
            if skill.category in required_set:
                if skill.proficiency_level == "expert":
                    proficiency_bonus += 0.05
                elif skill.proficiency_level == "trainee":
                    proficiency_bonus -= 0.05

        overall_fit = min(1.0, max(0.0, full_match_score + partial_match_score + proficiency_bonus))

        return SkillFitAnalysis(
            overall_fit=round(overall_fit, 2),
            matched_skills=sorted(matched),
            missing_skills=sorted(missing),
            partially_matched=sorted(partial),
            overqualified_areas=sorted(set(overqualified)),
        )

    def rank_engineers(
        self,
        required_skills: list[SkillCategory],
        engineers: list[EngineerProfile],
    ) -> list[tuple[EngineerProfile, SkillFitAnalysis]]:
        """Rank multiple engineers by skill fit for a work order.

        Args:
            required_skills: Required skill categories.
            engineers: List of candidate engineers.

        Returns:
            List of (engineer, fit_analysis) tuples sorted by overall_fit descending.
        """
        results: list[tuple[EngineerProfile, SkillFitAnalysis]] = []
        for eng in engineers:
            if not eng.available:
                continue
            fit = self.evaluate_fit(required_skills, eng)
            results.append((eng, fit))

        results.sort(key=lambda x: x[1].overall_fit, reverse=True)
        return results
