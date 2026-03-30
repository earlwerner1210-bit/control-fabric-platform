"""Document and DocumentChunk models."""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Document(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "documents"

    title = Column(String(500), nullable=False)
    filename = Column(String(500), nullable=False)
    content_type = Column(String(127), nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    checksum_sha256 = Column(String(64), nullable=True)
    status = Column(String(31), nullable=False, default="uploaded")
    document_type = Column(String(63), nullable=True)
    source_url = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    parsed_payload = Column(JSON, nullable=True)

    chunks = relationship("DocumentChunk", back_populates="document", lazy="selectin")


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"

    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)
    embedding_model = Column(String(127), nullable=True)
    token_count = Column(Integer, nullable=True)
    # NOTE: embedding vector column is added via raw SQL in a migration:
    #   ALTER TABLE document_chunks ADD COLUMN embedding vector(<dim>);

    document = relationship("Document", back_populates="chunks", lazy="selectin")
