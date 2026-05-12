"""exports

Revision ID: 0008_exports
Revises: 0007_events
Create Date: 2026-05-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_exports"
down_revision: str | None = "0007_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("export_type", sa.Text(), nullable=False),
        sa.Column("export_scope", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("sha256_hash", sa.Text(), nullable=True),
        sa.Column("generated_by_analysis_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("exported_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_filter", sa.Text(), nullable=True),
        sa.Column("export_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("export_type in ('json', 'markdown', 'html', 'pdf', 'docx')", name="ck_exports_export_type"),
        sa.CheckConstraint(
            "export_scope in ('review_report', 'case_summary', 'claims', 'timeline', 'contradictions', 'missing_items', 'custom_bundle')",
            name="ck_exports_export_scope",
        ),
        sa.CheckConstraint("sha256_hash is null or sha256_hash ~ '^[0-9a-f]{64}$'", name="ck_exports_sha256_hash_hex"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name="fk_exports_case_id_cases"),
        sa.ForeignKeyConstraint(["exported_by_user_id"], ["users.id"], name="fk_exports_exported_by_user_id_users"),
        sa.ForeignKeyConstraint(["generated_by_analysis_run_id"], ["analysis_runs.id"], name="fk_exports_generated_by_analysis_run_id_analysis_runs"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exports_case_created_at", "exports", ["case_id", sa.text("created_at DESC")])
    op.create_index("ix_exports_export_scope", "exports", ["export_scope"])
    op.create_index("ix_exports_export_type", "exports", ["export_type"])

    op.create_table(
        "export_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("export_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "object_type in ('entity', 'event', 'claim', 'contradiction_candidate', 'missing_item_candidate', 'summary_item')",
            name="ck_export_items_object_type",
        ),
        sa.CheckConstraint("display_order is null or display_order >= 0", name="ck_export_items_display_order_non_negative"),
        sa.ForeignKeyConstraint(["export_id"], ["exports.id"], name="fk_export_items_export_id_exports"),
        sa.ForeignKeyConstraint(["source_reference_id"], ["source_references.id"], name="fk_export_items_source_reference_id_source_references"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_items_export_id", "export_items", ["export_id"])
    op.create_index("ix_export_items_object", "export_items", ["object_type", "object_id"])
    op.create_index("ix_export_items_source_reference_id", "export_items", ["source_reference_id"])


def downgrade() -> None:
    op.drop_index("ix_export_items_source_reference_id", table_name="export_items")
    op.drop_index("ix_export_items_object", table_name="export_items")
    op.drop_index("ix_export_items_export_id", table_name="export_items")
    op.drop_table("export_items")
    op.drop_index("ix_exports_export_type", table_name="exports")
    op.drop_index("ix_exports_export_scope", table_name="exports")
    op.drop_index("ix_exports_case_created_at", table_name="exports")
    op.drop_table("exports")
