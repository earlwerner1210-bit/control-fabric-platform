"""CanonicalEntity model."""

from __future__ import annotations

from sqlalchemy import Column, Float, String
from sqlalchemy.dialects.postgresql import JSON

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CanonicalEntity(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "canonical_entities"

    entity_type = Column(String(63), nullable=False)
    canonical_name = Column(String(500), nullable=False)
    aliases = Column(JSON, nullable=False, default=list)
    metadata_ = Column("metadata", JSON, nullable=True)
    confidence = Column(Float, nullable=False, default=1.0)
