"""Canonical entity model for entity resolution."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CanonicalEntity(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "canonical_entities"

    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(63), nullable=False, index=True)
    aliases: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # list of alias strings
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
