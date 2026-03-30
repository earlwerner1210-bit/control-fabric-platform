"""Tenant model."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, String
from sqlalchemy.dialects.postgresql import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name = Column(String(255), unique=True, nullable=False)
    slug = Column(String(63), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    settings = Column(JSON, nullable=True)
