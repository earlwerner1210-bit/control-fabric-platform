"""EvalCase and EvalRun models."""

from __future__ import annotations

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EvalCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "eval_cases"

    name = Column(String(255), unique=True, nullable=False)
    domain = Column(String(63), nullable=False)
    description = Column(Text, nullable=True)
    input_payload = Column(JSON, nullable=True)
    expected_output = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)


class EvalRun(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "eval_runs"

    eval_suite = Column(String(127), nullable=False)
    total_cases = Column(Integer, nullable=False)
    passed = Column(Integer, nullable=False)
    failed = Column(Integer, nullable=False)
    results = Column(JSON, nullable=True)
    triggered_by = Column(String(127), nullable=True)
