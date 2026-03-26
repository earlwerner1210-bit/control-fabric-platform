"""Initial schema – all core tables.

Revision ID: 001_initial
Revises: None
Create Date: 2024-06-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

from alembic import op

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── pgvector extension ────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── tenants ───────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("slug", sa.String(63), unique=True, nullable=False, index=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("settings", JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── roles ─────────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.String(63), unique=True, nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── users ─────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── user_roles ────────────────────────────────────────────────────────
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id",
            UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # ── documents ─────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(127), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("status", sa.String(31), nullable=False, server_default="uploaded"),
        sa.Column("document_type", sa.String(63), nullable=True),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("metadata", JSON, nullable=True),
        sa.Column("parsed_payload", JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── document_chunks ───────────────────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("metadata", JSON, nullable=True),
        sa.Column("embedding_model", sa.String(127), nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── canonical_entities ────────────────────────────────────────────────
    op.create_table(
        "canonical_entities",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("entity_type", sa.String(63), nullable=False),
        sa.Column("canonical_name", sa.String(500), nullable=False),
        sa.Column("aliases", JSON, nullable=False, server_default="[]"),
        sa.Column("metadata", JSON, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── workflow_cases ────────────────────────────────────────────────────
    op.create_table(
        "workflow_cases",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("workflow_type", sa.String(63), nullable=False, index=True),
        sa.Column("status", sa.String(31), nullable=False, server_default="pending"),
        sa.Column("verdict", sa.String(31), nullable=True),
        sa.Column("input_payload", JSON, nullable=True),
        sa.Column("output_payload", JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("temporal_workflow_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── control_objects ───────────────────────────────────────────────────
    op.create_table(
        "control_objects",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("domain_pack", sa.String(63), nullable=False),
        sa.Column("control_type", sa.String(63), nullable=False, index=True),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("payload", JSON, nullable=True),
        sa.Column(
            "source_document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_chunk_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_clause_ref", sa.String(127), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column(
            "workflow_case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workflow_cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── control_links ─────────────────────────────────────────────────────
    op.create_table(
        "control_links",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "source_object_id",
            UUID(as_uuid=True),
            sa.ForeignKey("control_objects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "target_object_id",
            UUID(as_uuid=True),
            sa.ForeignKey("control_objects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("link_type", sa.String(63), nullable=False),
        sa.Column("weight", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("metadata", JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── validation_results ────────────────────────────────────────────────
    op.create_table(
        "validation_results",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("target_type", sa.String(63), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("rule_name", sa.String(127), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("severity", sa.String(31), nullable=False),
        sa.Column("details", JSON, nullable=True),
        sa.Column(
            "workflow_case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workflow_cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── model_runs ────────────────────────────────────────────────────────
    op.create_table(
        "model_runs",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider", sa.String(63), nullable=False),
        sa.Column("model_name", sa.String(127), nullable=False),
        sa.Column("operation", sa.String(63), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("input_payload", JSON, nullable=True),
        sa.Column("output_payload", JSON, nullable=True),
        sa.Column("success", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "workflow_case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workflow_cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── audit_events ──────────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_type", sa.String(127), nullable=False, index=True),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("resource_type", sa.String(63), nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
        sa.Column("payload", JSON, nullable=True),
        sa.Column(
            "workflow_case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workflow_cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── prompt_templates ──────────────────────────────────────────────────
    op.create_table(
        "prompt_templates",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("domain_pack", sa.String(63), nullable=False),
        sa.Column("template_text", sa.Text, nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("metadata", JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── domain_pack_versions ──────────────────────────────────────────────
    op.create_table(
        "domain_pack_versions",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("pack_name", sa.String(63), nullable=False),
        sa.Column("version", sa.String(31), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("config", JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── eval_cases ────────────────────────────────────────────────────────
    op.create_table(
        "eval_cases",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("domain", sa.String(63), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("input_payload", JSON, nullable=True),
        sa.Column("expected_output", JSON, nullable=True),
        sa.Column("tags", JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── eval_runs ─────────────────────────────────────────────────────────
    op.create_table(
        "eval_runs",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("eval_suite", sa.String(127), nullable=False),
        sa.Column("total_cases", sa.Integer, nullable=False),
        sa.Column("passed", sa.Integer, nullable=False),
        sa.Column("failed", sa.Integer, nullable=False),
        sa.Column("results", JSON, nullable=True),
        sa.Column("triggered_by", sa.String(127), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── notification_events ───────────────────────────────────────────────
    op.create_table(
        "notification_events",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("channel", sa.String(31), nullable=False),
        sa.Column("recipient", sa.String(500), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("status", sa.String(31), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_events")
    op.drop_table("eval_runs")
    op.drop_table("eval_cases")
    op.drop_table("domain_pack_versions")
    op.drop_table("prompt_templates")
    op.drop_table("audit_events")
    op.drop_table("model_runs")
    op.drop_table("validation_results")
    op.drop_table("control_links")
    op.drop_table("control_objects")
    op.drop_table("workflow_cases")
    op.drop_table("canonical_entities")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("tenants")
    op.execute("DROP EXTENSION IF EXISTS vector")
