"""Parser for operational runbook documents.

Extracts structured runbook steps, prerequisites, and metadata from
semi-structured text.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..schemas.telco_schemas import ParsedRunbook, RunbookStep
from ..taxonomy.telco_taxonomy import IncidentSeverity

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_STEP_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:step\s+)?(\d+)[.):\s]+(.+?)(?=\n\s*(?:step\s+)?\d+[.):\s]|\Z)",
    re.IGNORECASE | re.DOTALL,
)

_NUMBERED_LIST_PATTERN = re.compile(
    r"(?:^|\n)\s*(\d+)\.\s+(.+?)(?=\n\s*\d+\.|\Z)",
    re.DOTALL,
)

_SEVERITY_KEYWORDS: dict[IncidentSeverity, re.Pattern[str]] = {
    IncidentSeverity.p1: re.compile(r"\b(P1|priority\s*1|critical|sev[- ]?1)\b", re.I),
    IncidentSeverity.p2: re.compile(r"\b(P2|priority\s*2|high|sev[- ]?2)\b", re.I),
    IncidentSeverity.p3: re.compile(r"\b(P3|priority\s*3|medium|sev[- ]?3)\b", re.I),
    IncidentSeverity.p4: re.compile(r"\b(P4|priority\s*4|low|sev[- ]?4)\b", re.I),
}

_DATETIME_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)"
)

_FIELD_PATTERNS = {
    "runbook_id": re.compile(
        r"(?:runbook|document|id|ref)\s*[:=]?\s*(RB[- ]?[\w\-]+|\w+-\d+)", re.I
    ),
    "title": re.compile(r"(?:title|name|runbook)\s*[:=]\s*(.+?)(?:\n|$)", re.I),
    "owner": re.compile(r"(?:owner|author|maintainer)\s*[:=]\s*(.+?)(?:\n|$)", re.I),
    "description": re.compile(
        r"(?:description|purpose|overview)\s*[:=]\s*(.+?)(?:\n\n|\Z)", re.I | re.DOTALL
    ),
}

_PREREQUISITE_PATTERN = re.compile(
    r"(?:prerequisites?|requirements?|before\s+you\s+start)\s*[:=]?\s*\n((?:\s*[-*]\s*.+\n?)+)",
    re.I,
)

_ROLLBACK_PATTERN = re.compile(
    r"(?:rollback|undo|revert)\s*[:=]?\s*(.+?)(?:\n|$)",
    re.I,
)

_APPROVAL_KEYWORDS = re.compile(
    r"\b(requires?\s+approval|get\s+approval|seek\s+authoris|change\s+board|CAB)\b",
    re.I,
)

_DURATION_PATTERN = re.compile(r"(\d+)\s*(?:minutes?|mins?|min)\b", re.I)

_TAG_PATTERN = re.compile(r"(?:tags?|labels?|categories?)\s*[:=]\s*(.+?)(?:\n|$)", re.I)

_SERVICE_PATTERN = re.compile(r"(?:applies?\s+to|services?|systems?)\s*[:=]\s*(.+?)(?:\n|$)", re.I)


class RunbookParser:
    """Parser for extracting structured runbook data from text."""

    def parse_runbook(self, text: str) -> ParsedRunbook:
        """Parse runbook text into a structured ParsedRunbook.

        Args:
            text: Raw runbook document text.

        Returns:
            ParsedRunbook with steps, prerequisites, and metadata.
        """
        runbook_id = self._extract_field(text, "runbook_id")
        title = self._extract_field(text, "title") or text.split("\n")[0].strip()[:200]
        owner = self._extract_field(text, "owner") or ""
        description = self._extract_field(text, "description") or ""

        steps = self._extract_steps(text)
        prerequisites = self._extract_prerequisites(text)
        applicable_severity = self._detect_severity_scope(text)
        applicable_services = self._extract_services(text)

        # Calculate total estimated time
        total_minutes = sum(s.estimated_minutes for s in steps)

        # Extract last updated date
        last_updated = None
        date_match = re.search(r"(?:last\s+updated|modified|revised)\s*[:=]?\s*", text, re.I)
        if date_match:
            dt_match = _DATETIME_PATTERN.search(text[date_match.end() : date_match.end() + 50])
            if dt_match:
                try:
                    last_updated = datetime.fromisoformat(dt_match.group(1).replace("Z", "+00:00"))
                except ValueError:
                    pass

        # Tags
        tags: list[str] = []
        tag_match = _TAG_PATTERN.search(text)
        if tag_match:
            tags = [t.strip() for t in tag_match.group(1).split(",") if t.strip()]

        return ParsedRunbook(
            runbook_id=runbook_id or ParsedRunbook.model_fields["runbook_id"].default_factory(),
            title=title,
            description=description.strip(),
            applicable_severity=applicable_severity,
            applicable_services=applicable_services,
            steps=steps,
            prerequisites=prerequisites,
            estimated_total_minutes=total_minutes,
            last_updated=last_updated,
            owner=owner,
            tags=tags,
        )

    def _extract_steps(self, text: str) -> list[RunbookStep]:
        """Extract ordered steps from the runbook text."""
        steps: list[RunbookStep] = []

        # Try structured step pattern first
        matches = list(_STEP_PATTERN.finditer(text))
        if not matches:
            matches = list(_NUMBERED_LIST_PATTERN.finditer(text))

        for match in matches:
            step_num = int(match.group(1))
            step_text = match.group(2).strip()

            # Extract expected outcome
            expected = ""
            outcome_match = re.search(
                r"(?:expected|outcome|result|verify)\s*[:=]\s*(.+?)(?:\n|$)", step_text, re.I
            )
            if outcome_match:
                expected = outcome_match.group(1).strip()
                step_text = step_text[: outcome_match.start()].strip()

            # Extract rollback
            rollback = ""
            rollback_match = _ROLLBACK_PATTERN.search(step_text)
            if rollback_match:
                rollback = rollback_match.group(1).strip()

            # Check for approval requirement
            requires_approval = bool(_APPROVAL_KEYWORDS.search(step_text))

            # Estimate duration
            duration_match = _DURATION_PATTERN.search(step_text)
            duration = float(duration_match.group(1)) if duration_match else 5.0

            steps.append(
                RunbookStep(
                    step_number=step_num,
                    instruction=step_text,
                    expected_outcome=expected,
                    rollback_instruction=rollback,
                    requires_approval=requires_approval,
                    estimated_minutes=duration,
                )
            )

        return steps

    def _extract_prerequisites(self, text: str) -> list[str]:
        """Extract prerequisites from the runbook."""
        prereqs: list[str] = []
        match = _PREREQUISITE_PATTERN.search(text)
        if match:
            for line in match.group(1).strip().split("\n"):
                line = line.strip().lstrip("-*# ")
                if line:
                    prereqs.append(line)
        return prereqs

    def _detect_severity_scope(self, text: str) -> list[IncidentSeverity]:
        """Detect which severity levels this runbook applies to."""
        severities: list[IncidentSeverity] = []
        for sev, pattern in _SEVERITY_KEYWORDS.items():
            if pattern.search(text):
                severities.append(sev)
        return severities

    def _extract_services(self, text: str) -> list[str]:
        """Extract applicable service names."""
        match = _SERVICE_PATTERN.search(text)
        if match:
            return [s.strip() for s in match.group(1).split(",") if s.strip()]
        return []

    def _extract_field(self, text: str, field_name: str) -> str | None:
        """Extract a named field value from text."""
        pattern = _FIELD_PATTERNS.get(field_name)
        if pattern:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        return None
