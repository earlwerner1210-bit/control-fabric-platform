"""
Data Governance Layer

Provides classification, sensitivity labelling, legal hold,
and redaction controls for all evidence and audit data.

Critical when evidence includes sensitive enterprise data:
  - Financial records (IFRS, Basel III)
  - Health information (HIPAA, MDR)
  - Legal matter data (SRA privilege)
  - Export-controlled technical data (ITAR/EAR)

Classification levels:
  PUBLIC       — can be shared externally
  INTERNAL     — internal use only
  CONFIDENTIAL — restricted distribution, need-to-know
  RESTRICTED   — highest sensitivity, legal/regulatory protected

Legal hold:
  Prevents deletion of evidence that may be needed for
  litigation, regulatory investigation, or audit.
  Overrides all retention policies while active.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ClassificationLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class DataCategory(str, Enum):
    EVIDENCE = "evidence"
    AUDIT_LOG = "audit_log"
    GOVERNANCE_OBJECT = "governance_object"
    EXCEPTION_RECORD = "exception_record"
    USER_DATA = "user_data"
    CONFIGURATION = "configuration"


@dataclass
class ClassificationRecord:
    record_id: str
    entity_type: str
    entity_id: str
    classification: ClassificationLevel
    data_category: DataCategory
    sensitivity_reason: str
    classified_by: str
    tenant_id: str
    classified_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    review_due: str | None = None
    record_hash: str = ""

    def __post_init__(self) -> None:
        if not self.record_hash:
            payload = f"{self.entity_id}{self.classification}{self.classified_at}"
            self.record_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass
class LegalHold:
    hold_id: str
    hold_name: str
    description: str
    entity_ids: list[str]
    entity_types: list[str]
    placed_by: str
    legal_contact: str
    tenant_id: str
    placed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    released_at: str | None = None
    released_by: str | None = None
    is_active: bool = True
    hold_hash: str = ""

    def __post_init__(self) -> None:
        if not self.hold_hash:
            payload = f"{self.hold_id}{self.placed_by}{self.placed_at}"
            self.hold_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]


# Default classification rules per data category
DEFAULT_CLASSIFICATIONS: dict[DataCategory, ClassificationLevel] = {
    DataCategory.EVIDENCE: ClassificationLevel.CONFIDENTIAL,
    DataCategory.AUDIT_LOG: ClassificationLevel.INTERNAL,
    DataCategory.GOVERNANCE_OBJECT: ClassificationLevel.INTERNAL,
    DataCategory.EXCEPTION_RECORD: ClassificationLevel.CONFIDENTIAL,
    DataCategory.USER_DATA: ClassificationLevel.RESTRICTED,
    DataCategory.CONFIGURATION: ClassificationLevel.INTERNAL,
}

# Fields to redact per classification level on export
REDACTION_RULES: dict[ClassificationLevel, list[str]] = {
    ClassificationLevel.RESTRICTED: [
        "email",
        "phone",
        "address",
        "passport",
        "ssn",
        "health_data",
        "legal_matter_id",
        "salary",
        "itar_controlled",
        "ear_controlled",
    ],
    ClassificationLevel.CONFIDENTIAL: [
        "email",
        "personal_identifier",
        "client_name",
    ],
    ClassificationLevel.INTERNAL: [],
    ClassificationLevel.PUBLIC: [],
}
