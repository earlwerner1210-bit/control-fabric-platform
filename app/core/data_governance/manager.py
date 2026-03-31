"""
Data Governance Manager

Manages classification records, legal holds, and redaction.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.core.data_governance.classification import (
    DEFAULT_CLASSIFICATIONS,
    REDACTION_RULES,
    ClassificationLevel,
    ClassificationRecord,
    DataCategory,
    LegalHold,
)

logger = logging.getLogger(__name__)


class DataGovernanceManager:
    """
    Manages all data governance operations for a platform deployment.
    """

    def __init__(self) -> None:
        self._classifications: dict[str, ClassificationRecord] = {}
        self._holds: dict[str, LegalHold] = {}
        self._held_entities: set[str] = set()

    # ── Classification ─────────────────────────────────────────────────────────

    def classify(
        self,
        entity_type: str,
        entity_id: str,
        classification: ClassificationLevel,
        data_category: DataCategory,
        classified_by: str,
        tenant_id: str,
        sensitivity_reason: str = "",
        review_due: str | None = None,
    ) -> ClassificationRecord:
        record = ClassificationRecord(
            record_id=str(uuid.uuid4()),
            entity_type=entity_type,
            entity_id=entity_id,
            classification=classification,
            data_category=data_category,
            sensitivity_reason=sensitivity_reason or f"Classified as {classification.value}",
            classified_by=classified_by,
            tenant_id=tenant_id,
            review_due=review_due,
        )
        key = f"{entity_type}:{entity_id}"
        self._classifications[key] = record
        logger.info(
            "Classified: %s=%s as %s by %s",
            entity_type,
            entity_id[:12],
            classification.value,
            classified_by,
        )
        return record

    def get_classification(self, entity_type: str, entity_id: str) -> ClassificationRecord | None:
        return self._classifications.get(f"{entity_type}:{entity_id}")

    def get_default_classification(self, data_category: DataCategory) -> ClassificationLevel:
        return DEFAULT_CLASSIFICATIONS.get(data_category, ClassificationLevel.INTERNAL)

    def bulk_classify(
        self,
        entity_ids: list[str],
        entity_type: str,
        classification: ClassificationLevel,
        data_category: DataCategory,
        classified_by: str,
        tenant_id: str,
    ) -> list[ClassificationRecord]:
        return [
            self.classify(
                entity_type,
                eid,
                classification,
                data_category,
                classified_by,
                tenant_id,
            )
            for eid in entity_ids
        ]

    def get_all_classifications(self, tenant_id: str | None = None) -> list[ClassificationRecord]:
        records = list(self._classifications.values())
        if tenant_id:
            records = [r for r in records if r.tenant_id == tenant_id]
        return records

    # ── Legal Hold ─────────────────────────────────────────────────────────────

    def place_hold(
        self,
        hold_name: str,
        description: str,
        entity_ids: list[str],
        entity_types: list[str],
        placed_by: str,
        legal_contact: str,
        tenant_id: str,
    ) -> LegalHold:
        hold = LegalHold(
            hold_id=str(uuid.uuid4()),
            hold_name=hold_name,
            description=description,
            entity_ids=entity_ids,
            entity_types=entity_types,
            placed_by=placed_by,
            legal_contact=legal_contact,
            tenant_id=tenant_id,
        )
        self._holds[hold.hold_id] = hold
        for eid in entity_ids:
            self._held_entities.add(eid)
        logger.warning(
            "Legal hold placed: %s on %d entities by %s",
            hold_name,
            len(entity_ids),
            placed_by,
        )
        return hold

    def release_hold(self, hold_id: str, released_by: str) -> LegalHold:
        hold = self._holds.get(hold_id)
        if not hold:
            raise ValueError(f"Legal hold {hold_id} not found")
        if not hold.is_active:
            raise ValueError(f"Hold {hold_id} is already released")
        hold.is_active = False
        hold.released_at = datetime.now(UTC).isoformat()
        hold.released_by = released_by
        # Remove from held entities if no other active holds cover them
        active_held = set()
        for h in self._holds.values():
            if h.is_active:
                active_held.update(h.entity_ids)
        self._held_entities = active_held
        logger.warning("Legal hold released: %s by %s", hold.hold_name, released_by)
        return hold

    def is_on_hold(self, entity_id: str) -> bool:
        return entity_id in self._held_entities

    def can_delete(self, entity_id: str) -> tuple[bool, str]:
        if self.is_on_hold(entity_id):
            active_holds = [
                h.hold_name
                for h in self._holds.values()
                if h.is_active and entity_id in h.entity_ids
            ]
            return (
                False,
                f"Entity is under legal hold: {', '.join(active_holds)}",
            )
        return True, "No legal hold — deletion permitted by retention policy"

    def get_active_holds(self, tenant_id: str | None = None) -> list[LegalHold]:
        holds = [h for h in self._holds.values() if h.is_active]
        if tenant_id:
            holds = [h for h in holds if h.tenant_id == tenant_id]
        return holds

    # ── Redaction ──────────────────────────────────────────────────────────────

    def redact_for_export(
        self,
        data: dict,
        classification: ClassificationLevel,
        requesting_role: str = "auditor",
    ) -> dict:
        """
        Redact sensitive fields based on classification level and requester role.
        Platform admins see everything. Auditors see RESTRICTED data redacted.
        """
        if requesting_role == "platform_admin":
            return data  # Platform admins see everything
        fields_to_redact = REDACTION_RULES.get(classification, [])
        if not fields_to_redact:
            return data
        redacted = dict(data)
        for fld in fields_to_redact:
            if fld in redacted:
                redacted[fld] = f"[REDACTED — {classification.value.upper()}]"
                logger.debug(
                    "Redacted field %s for %s requester",
                    fld,
                    requesting_role,
                )
        return redacted

    def redact_audit_export(
        self,
        records: list[dict],
        requesting_role: str = "auditor",
        tenant_id: str = "default",
    ) -> list[dict]:
        """Redact a batch of audit records for export."""
        result = []
        for record in records:
            entity_id = record.get("entity_id", "")
            classification_record = self.get_classification("audit_log", entity_id)
            if classification_record:
                classification = classification_record.classification
            else:
                classification = ClassificationLevel.INTERNAL
            result.append(self.redact_for_export(record, classification, requesting_role))
        return result

    def get_summary(self, tenant_id: str) -> dict:
        all_records = self.get_all_classifications(tenant_id)
        by_level: dict[str, int] = {}
        for r in all_records:
            by_level[r.classification.value] = by_level.get(r.classification.value, 0) + 1
        active_holds = self.get_active_holds(tenant_id)
        return {
            "tenant_id": tenant_id,
            "total_classified": len(all_records),
            "by_classification": by_level,
            "active_legal_holds": len(active_holds),
            "entities_on_hold": len(self._held_entities),
        }


# Singleton
data_governance_manager = DataGovernanceManager()
