"""ControlObject and ControlLink models."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ControlObject(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "control_objects"

    domain_pack = Column(String(63), nullable=False)
    control_type = Column(String(63), nullable=False, index=True)
    label = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    payload = Column(JSON, nullable=True)
    source_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_chunk_id = Column(UUID(as_uuid=True), nullable=True)
    source_clause_ref = Column(String(127), nullable=True)
    confidence = Column(Float, nullable=False, default=1.0)
    workflow_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_cases.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)

    outgoing_links = relationship(
        "ControlLink",
        foreign_keys="ControlLink.source_object_id",
        back_populates="source_object",
        lazy="selectin",
    )
    incoming_links = relationship(
        "ControlLink",
        foreign_keys="ControlLink.target_object_id",
        back_populates="target_object",
        lazy="selectin",
    )


class ControlLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_links"

    source_object_id = Column(
        UUID(as_uuid=True),
        ForeignKey("control_objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_object_id = Column(
        UUID(as_uuid=True),
        ForeignKey("control_objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    link_type = Column(String(63), nullable=False)
    weight = Column(Float, nullable=False, default=1.0)
    metadata_ = Column("metadata", JSON, nullable=True)

    source_object = relationship(
        "ControlObject",
        foreign_keys=[source_object_id],
        back_populates="outgoing_links",
        lazy="selectin",
    )
    target_object = relationship(
        "ControlObject",
        foreign_keys=[target_object_id],
        back_populates="incoming_links",
        lazy="selectin",
    )
