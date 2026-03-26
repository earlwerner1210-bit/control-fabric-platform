"""
Reconciliation Module - Cross-domain linkers that match contracts to
work orders and work orders to incidents using token-based similarity,
reference matching, and timeline overlap.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared link model
# ---------------------------------------------------------------------------

class CrossPlaneLink(BaseModel):
    """A link between two objects in different domain planes."""

    source_id: str = Field(..., description="Identifier of the source object")
    target_id: str = Field(..., description="Identifier of the target object")
    source_domain: str = Field(..., description="Domain the source belongs to (e.g. contract, field, telco)")
    target_domain: str = Field(..., description="Domain the target belongs to")
    link_type: str = Field(..., description="Nature of the link (activity_match, rate_card, ref_match, timeline_overlap, description_similarity)")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence score 0-1")
    evidence: str = Field("", description="Human-readable evidence for why the link was created")


# ---------------------------------------------------------------------------
# Token utilities
# ---------------------------------------------------------------------------

_SPLIT_PATTERN = re.compile(r"[_\-\s/,;:]+")
_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "at",
    "is", "it", "by", "with", "from", "as", "be", "was", "were", "been",
})


def _tokenize(text: str) -> set[str]:
    """Normalise and tokenize a string into a set of meaningful tokens."""
    if not text:
        return set()
    tokens = _SPLIT_PATTERN.split(text.lower().strip())
    return {t for t in tokens if t and t not in _STOP_WORDS and len(t) > 1}


def _token_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard-style similarity between two token sets."""
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Contract <-> Work Order Linker
# ---------------------------------------------------------------------------

class ContractWorkOrderLinker:
    """Links contract objects to work orders using activity names,
    rate card references, and obligation identifiers.
    """

    def link(
        self,
        contract_objects: list[dict[str, Any]],
        work_order: dict[str, Any],
    ) -> list[CrossPlaneLink]:
        """Find links between a set of contract objects and a single work order.

        Matching strategies:
        1. Direct reference match (contract_ref on work order matches contract id)
        2. Activity / description token similarity
        3. Rate card reference match
        4. Obligation reference match
        """
        links: list[CrossPlaneLink] = []
        wo_id = str(work_order.get("work_order_id", work_order.get("id", "")))
        wo_contract_ref = work_order.get("contract_ref", "")
        wo_description = work_order.get("description", "")
        wo_tokens = _tokenize(wo_description)
        wo_activities = self._extract_activities(wo_description)
        wo_rate_ref = work_order.get("rate_card_ref", work_order.get("rate_ref", ""))

        for co in contract_objects:
            co_id = str(co.get("contract_id", co.get("id", "")))

            # Strategy 1: direct contract_ref match
            if wo_contract_ref and wo_contract_ref == co_id:
                links.append(CrossPlaneLink(
                    source_id=co_id,
                    target_id=wo_id,
                    source_domain="contract",
                    target_domain="field",
                    link_type="ref_match",
                    confidence=1.0,
                    evidence=f"Work order contract_ref '{wo_contract_ref}' matches contract id",
                ))
                continue  # strong match, no need for fuzzy

            # Strategy 2: activity / description similarity
            co_description = co.get("description", co.get("scope", ""))
            co_activities = self._extract_activities(co_description)
            co_tokens = _tokenize(co_description)

            # Activity-level overlap
            activity_overlap = wo_activities & co_activities
            if activity_overlap:
                confidence = min(1.0, len(activity_overlap) / max(len(wo_activities), 1) * 0.8 + 0.2)
                links.append(CrossPlaneLink(
                    source_id=co_id,
                    target_id=wo_id,
                    source_domain="contract",
                    target_domain="field",
                    link_type="activity_match",
                    confidence=round(confidence, 3),
                    evidence=f"Matching activities: {', '.join(sorted(activity_overlap))}",
                ))
            else:
                # Fall back to general token similarity
                sim = _token_similarity(wo_tokens, co_tokens)
                if sim >= 0.25:
                    links.append(CrossPlaneLink(
                        source_id=co_id,
                        target_id=wo_id,
                        source_domain="contract",
                        target_domain="field",
                        link_type="description_similarity",
                        confidence=round(sim, 3),
                        evidence=f"Description token similarity: {sim:.2%}",
                    ))

            # Strategy 3: rate card reference
            co_rate_ref = co.get("rate_card_ref", co.get("rate_ref", ""))
            if wo_rate_ref and co_rate_ref and wo_rate_ref.lower() == co_rate_ref.lower():
                links.append(CrossPlaneLink(
                    source_id=co_id,
                    target_id=wo_id,
                    source_domain="contract",
                    target_domain="field",
                    link_type="rate_card",
                    confidence=0.9,
                    evidence=f"Matching rate card reference: {wo_rate_ref}",
                ))

            # Strategy 4: obligation reference match
            co_obligations = co.get("obligation_refs", co.get("obligations", []))
            wo_obligations = work_order.get("obligation_refs", [])
            if isinstance(co_obligations, list) and isinstance(wo_obligations, list):
                co_obl_set = {str(o).lower() for o in co_obligations}
                wo_obl_set = {str(o).lower() for o in wo_obligations}
                overlap = co_obl_set & wo_obl_set
                if overlap:
                    links.append(CrossPlaneLink(
                        source_id=co_id,
                        target_id=wo_id,
                        source_domain="contract",
                        target_domain="field",
                        link_type="obligation_match",
                        confidence=0.85,
                        evidence=f"Matching obligation refs: {', '.join(sorted(overlap))}",
                    ))

        return links

    @staticmethod
    def _extract_activities(description: str) -> set[str]:
        """Tokenize and normalize a description into a set of activity tokens.

        Splits on common delimiters, lowercases, strips stop words, and
        returns meaningful tokens that represent work activities.
        """
        return _tokenize(description)


# ---------------------------------------------------------------------------
# Work Order <-> Incident Linker
# ---------------------------------------------------------------------------

class WorkOrderIncidentLinker:
    """Links work orders to incidents using reference matching,
    description similarity, and timeline overlap.
    """

    def link(
        self,
        work_order: dict[str, Any],
        incidents: list[dict[str, Any]],
    ) -> list[CrossPlaneLink]:
        """Find links between a work order and a set of incidents.

        Matching strategies:
        1. Direct work_order_ref match
        2. Description token similarity
        3. Timeline overlap (incident reported within work order window)
        """
        links: list[CrossPlaneLink] = []
        wo_id = str(work_order.get("work_order_id", work_order.get("id", "")))
        wo_tokens = _tokenize(work_order.get("description", ""))
        wo_scheduled = _parse_dt(work_order.get("scheduled_date"))
        wo_completed = _parse_dt(work_order.get("completed_date", work_order.get("completed_at")))

        for inc in incidents:
            inc_id = str(inc.get("incident_id", inc.get("id", "")))

            # Strategy 1: direct reference match
            wo_refs = inc.get("work_order_refs", [])
            if isinstance(wo_refs, list) and wo_id in [str(r) for r in wo_refs]:
                links.append(CrossPlaneLink(
                    source_id=wo_id,
                    target_id=inc_id,
                    source_domain="field",
                    target_domain="telco",
                    link_type="ref_match",
                    confidence=1.0,
                    evidence=f"Incident references work order '{wo_id}' directly",
                ))
                continue

            scored_links: list[CrossPlaneLink] = []

            # Strategy 2: description similarity
            inc_tokens = _tokenize(inc.get("description", "") + " " + inc.get("title", ""))
            sim = _token_similarity(wo_tokens, inc_tokens)
            if sim >= 0.2:
                scored_links.append(CrossPlaneLink(
                    source_id=wo_id,
                    target_id=inc_id,
                    source_domain="field",
                    target_domain="telco",
                    link_type="description_similarity",
                    confidence=round(sim, 3),
                    evidence=f"Description token similarity: {sim:.2%}",
                ))

            # Strategy 3: timeline overlap
            inc_reported = _parse_dt(inc.get("reported_at"))
            inc_resolved = _parse_dt(inc.get("resolved_at"))

            if wo_scheduled and inc_reported:
                overlap_conf = self._timeline_overlap_confidence(
                    wo_scheduled, wo_completed, inc_reported, inc_resolved,
                )
                if overlap_conf > 0.0:
                    scored_links.append(CrossPlaneLink(
                        source_id=wo_id,
                        target_id=inc_id,
                        source_domain="field",
                        target_domain="telco",
                        link_type="timeline_overlap",
                        confidence=round(overlap_conf, 3),
                        evidence="Work order and incident timelines overlap",
                    ))

            # Only keep the best scoring link per incident
            if scored_links:
                best = max(scored_links, key=lambda l: l.confidence)
                links.append(best)

        return links

    @staticmethod
    def _timeline_overlap_confidence(
        wo_start: datetime,
        wo_end: Optional[datetime],
        inc_start: datetime,
        inc_end: Optional[datetime],
    ) -> float:
        """Calculate a 0-1 confidence score based on timeline overlap.

        A 7-day window around the work order is used if no completion date
        is available.
        """
        from datetime import timedelta

        wo_end_effective = wo_end or (wo_start + timedelta(days=7))
        inc_end_effective = inc_end or (inc_start + timedelta(days=1))

        # Check overlap
        latest_start = max(wo_start, inc_start)
        earliest_end = min(wo_end_effective, inc_end_effective)

        if latest_start <= earliest_end:
            overlap_hours = (earliest_end - latest_start).total_seconds() / 3600.0
            # Confidence scales with overlap duration (cap at 0.7)
            return min(0.7, overlap_hours / 168.0 + 0.2)
        return 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(value: Any) -> Optional[datetime]:
    """Best-effort datetime parsing."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
