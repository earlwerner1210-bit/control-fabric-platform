"""initial schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-01-01 00:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── Enum types ────────────────────────────────────────────────────
    control_object_type = postgresql.ENUM(
        "obligation",
        "billable_event",
        "penalty_condition",
        "dispatch_precondition",
        "skill_requirement",
        "incident_state",
        "escalation_rule",
        "service_state",
        "readiness_check",
        "leakage_trigger",
        name="control_object_type",
        create_type=False,
    )
    workflow_status = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
        name="workflow_status",
        create_type=False,
    )
    case_verdict = postgresql.ENUM(
        "approved",
        "rejected",
        "needs_review",
        "escalated",
        name="case_verdict",
        create_type=False,
    )
    validation_status = postgresql.ENUM(
        "passed",
        "warned",
        "blocked",
        "escalated",
        name="validation_status",
        create_type=False,
    )

    # Create enum types explicitly
    control_object_type.create(op.get_bind(), checkfirst=True)
    workflow_status.create(op.get_bind(), checkfirst=True)
    case_verdict.create(op.get_bind(), checkfirst=True)
    validation_status.create(op.get_bind(), checkfirst=True)

    # ── tenants ───────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    # ── roles ─────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(63), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ── users ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # ── user_roles (composite PK join table) ──────────────────────────
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
    )

    # ── documents ─────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(127), nullable=True),
        sa.Column("document_type", sa.String(63), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("storage_path", sa.String(1024), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("parsed_payload", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.String(31),
            server_default="uploaded",
            nullable=False,
        ),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
    op.create_index("ix_documents_checksum_sha256", "documents", ["checksum_sha256"])

    # ── document_chunks ───────────────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_document_chunks_tenant_id", "document_chunks", ["tenant_id"])
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])

    # Add the pgvector embedding column (Vector type not directly supported by
    # Alembic's sa.Column, so we use raw SQL for the column + index).
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")

    # ── canonical_entities ────────────────────────────────────────────
    op.create_table(
        "canonical_entities",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("canonical_name", sa.String(512), nullable=False),
        sa.Column("entity_type", sa.String(63), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True, server_default="1.0"),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_canonical_entities_tenant_id", "canonical_entities", ["tenant_id"])
    op.create_index(
        "ix_canonical_entities_canonical_name", "canonical_entities", ["canonical_name"]
    )
    op.create_index("ix_canonical_entities_entity_type", "canonical_entities", ["entity_type"])

    # ── control_objects ───────────────────────────────────────────────
    op.create_table(
        "control_objects",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "control_type",
            control_object_type,
            nullable=False,
        ),
        sa.Column("domain", sa.String(63), nullable=False),
        sa.Column("label", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("source_chunk_id", sa.UUID(), nullable=True),
        sa.Column("source_clause_ref", sa.String(63), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True, server_default="1.0"),
        sa.Column("workflow_case_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_control_objects_tenant_id", "control_objects", ["tenant_id"])
    op.create_index("ix_control_objects_control_type", "control_objects", ["control_type"])
    op.create_index("ix_control_objects_domain", "control_objects", ["domain"])
    op.create_index(
        "ix_control_objects_source_document_id", "control_objects", ["source_document_id"]
    )
    op.create_index("ix_control_objects_workflow_case_id", "control_objects", ["workflow_case_id"])

    # ── control_links ─────────────────────────────────────────────────
    op.create_table(
        "control_links",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("source_object_id", sa.UUID(), nullable=False),
        sa.Column("target_object_id", sa.UUID(), nullable=False),
        sa.Column("link_type", sa.String(63), nullable=False),
        sa.Column("weight", sa.Float(), nullable=True, server_default="1.0"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_object_id"], ["control_objects.id"]),
        sa.ForeignKeyConstraint(["target_object_id"], ["control_objects.id"]),
    )
    op.create_index("ix_control_links_tenant_id", "control_links", ["tenant_id"])
    op.create_index("ix_control_links_source_object_id", "control_links", ["source_object_id"])
    op.create_index("ix_control_links_target_object_id", "control_links", ["target_object_id"])

    # ── workflow_cases ────────────────────────────────────────────────
    op.create_table(
        "workflow_cases",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("workflow_type", sa.String(63), nullable=False),
        sa.Column(
            "status",
            workflow_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("verdict", case_verdict, nullable=True),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("temporal_workflow_id", sa.String(255), nullable=True),
        sa.Column("temporal_run_id", sa.String(255), nullable=True),
        sa.Column("initiated_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_workflow_cases_tenant_id", "workflow_cases", ["tenant_id"])
    op.create_index("ix_workflow_cases_workflow_type", "workflow_cases", ["workflow_type"])

    # ── validation_results ────────────────────────────────────────────
    op.create_table(
        "validation_results",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("workflow_case_id", sa.UUID(), nullable=False),
        sa.Column("validator_name", sa.String(127), nullable=False),
        sa.Column("status", validation_status, nullable=False),
        sa.Column("domain", sa.String(63), nullable=False),
        sa.Column("rule_results", sa.JSON(), nullable=False),
        sa.Column("summary", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_case_id"], ["workflow_cases.id"]),
    )
    op.create_index("ix_validation_results_tenant_id", "validation_results", ["tenant_id"])
    op.create_index(
        "ix_validation_results_workflow_case_id", "validation_results", ["workflow_case_id"]
    )

    # ── prompt_templates ──────────────────────────────────────────────
    op.create_table(
        "prompt_templates",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(127), nullable=False),
        sa.Column("domain", sa.String(63), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_template", sa.Text(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_prompt_templates_tenant_id", "prompt_templates", ["tenant_id"])
    op.create_index("ix_prompt_templates_name", "prompt_templates", ["name"])
    op.create_index("ix_prompt_templates_domain", "prompt_templates", ["domain"])

    # ── model_runs ────────────────────────────────────────────────────
    op.create_table(
        "model_runs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("workflow_case_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(63), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("operation", sa.String(63), nullable=False),
        sa.Column("prompt_template_id", sa.UUID(), nullable=True),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_count_input", sa.Integer(), nullable=True),
        sa.Column("token_count_output", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("success", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("error_message", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_model_runs_tenant_id", "model_runs", ["tenant_id"])
    op.create_index("ix_model_runs_workflow_case_id", "model_runs", ["workflow_case_id"])

    # ── audit_events ──────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("workflow_case_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(63), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("actor_type", sa.String(31), nullable=False, server_default="system"),
        sa.Column("resource_type", sa.String(63), nullable=True),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("detail", sa.String(2048), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index("ix_audit_events_workflow_case_id", "audit_events", ["workflow_case_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])

    # ── domain_pack_versions ──────────────────────────────────────────
    op.create_table(
        "domain_pack_versions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("pack_name", sa.String(63), nullable=False),
        sa.Column("version", sa.String(31), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_domain_pack_versions_pack_name", "domain_pack_versions", ["pack_name"])

    # ── eval_cases ────────────────────────────────────────────────────
    op.create_table(
        "eval_cases",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(63), nullable=False),
        sa.Column("workflow_type", sa.String(63), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("expected_output", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_cases_domain", "eval_cases", ["domain"])

    # ── eval_runs ─────────────────────────────────────────────────────
    op.create_table(
        "eval_runs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("eval_case_id", sa.UUID(), nullable=False),
        sa.Column("workflow_case_id", sa.UUID(), nullable=True),
        sa.Column("actual_output", sa.JSON(), nullable=True),
        sa.Column("passed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["eval_case_id"], ["eval_cases.id"]),
    )
    op.create_index("ix_eval_runs_tenant_id", "eval_runs", ["tenant_id"])
    op.create_index("ix_eval_runs_eval_case_id", "eval_runs", ["eval_case_id"])

    # ── notification_events ───────────────────────────────────────────
    op.create_table(
        "notification_events",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("workflow_case_id", sa.UUID(), nullable=True),
        sa.Column("channel", sa.String(31), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(512), nullable=True),
        sa.Column("body", sa.String(4096), nullable=True),
        sa.Column("status", sa.String(31), server_default="pending", nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notification_events_tenant_id", "notification_events", ["tenant_id"])
    op.create_index(
        "ix_notification_events_workflow_case_id", "notification_events", ["workflow_case_id"]
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("notification_events")
    op.drop_table("eval_runs")
    op.drop_table("eval_cases")
    op.drop_table("domain_pack_versions")
    op.drop_table("audit_events")
    op.drop_table("model_runs")
    op.drop_table("prompt_templates")
    op.drop_table("validation_results")
    op.drop_table("workflow_cases")
    op.drop_table("control_links")
    op.drop_table("control_objects")
    op.drop_table("canonical_entities")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("tenants")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS validation_status")
    op.execute("DROP TYPE IF EXISTS case_verdict")
    op.execute("DROP TYPE IF EXISTS workflow_status")
    op.execute("DROP TYPE IF EXISTS control_object_type")

    # Drop extensions
    op.execute("DROP EXTENSION IF EXISTS vector")
