"""DomainPackVersion model."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.dialects.postgresql import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DomainPackVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "domain_pack_versions"

    pack_name = Column(String(63), nullable=False)
    version = Column(String(31), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    config = Column(JSON, nullable=True)
