"""PromptTemplate model."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PromptTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prompt_templates"

    name = Column(String(255), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    domain_pack = Column(String(63), nullable=False)
    template_text = Column(Text, nullable=False)
    system_prompt = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    metadata_ = Column("metadata", JSON, nullable=True)
