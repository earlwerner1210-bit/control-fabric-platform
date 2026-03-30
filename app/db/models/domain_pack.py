"""DomainPackVersion model."""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DomainPackVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "domain_pack_versions"

    pack_name: Mapped[str] = mapped_column(String(63), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(31), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
