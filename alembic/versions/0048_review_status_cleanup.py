"""clean up review status values

Revision ID: 0048_review_status_cleanup
Revises: 0047_knowledge_index_metadata
Create Date: 2026-06-13
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0048_review_status_cleanup"
down_revision: str | None = "0047_knowledge_index_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OBJECT_REVIEW_CONSTRAINTS = (
    ("claims", "ck_claims_review_status"),
    ("entities", "ck_entities_review_status"),
    ("events", "ck_events_review_status"),
    ("missing_item_candidates", "ck_missing_item_candidates_review_status"),
    ("contradiction_candidates", "ck_contradiction_candidates_review_status"),
)


def upgrade() -> None:
    for table_name, constraint_name in OBJECT_REVIEW_CONSTRAINTS:
        op.drop_constraint(constraint_name, table_name, type_="check")

    op.drop_constraint("ck_human_reviews_previous_review_status", "human_reviews", type_="check")
    op.drop_constraint("ck_human_reviews_new_review_status", "human_reviews", type_="check")

    for table_name, _constraint_name in OBJECT_REVIEW_CONSTRAINTS:
        op.execute(f"UPDATE {table_name} SET review_status = 'needs_review' WHERE review_status = 'new'")
    op.execute("UPDATE human_reviews SET previous_review_status = 'needs_review' WHERE previous_review_status = 'new'")
    op.execute("UPDATE human_reviews SET new_review_status = 'needs_review' WHERE new_review_status = 'new'")

    allowed_statuses = "('needs_review', 'verified', 'rejected', 'corrected')"
    for table_name, constraint_name in OBJECT_REVIEW_CONSTRAINTS:
        op.create_check_constraint(constraint_name, table_name, f"review_status in {allowed_statuses}")

    op.create_check_constraint(
        "ck_human_reviews_previous_review_status",
        "human_reviews",
        f"previous_review_status is null or previous_review_status in {allowed_statuses}",
    )
    op.create_check_constraint(
        "ck_human_reviews_new_review_status",
        "human_reviews",
        f"new_review_status is null or new_review_status in {allowed_statuses}",
    )


def downgrade() -> None:
    for table_name, constraint_name in OBJECT_REVIEW_CONSTRAINTS:
        op.drop_constraint(constraint_name, table_name, type_="check")

    op.drop_constraint("ck_human_reviews_previous_review_status", "human_reviews", type_="check")
    op.drop_constraint("ck_human_reviews_new_review_status", "human_reviews", type_="check")

    allowed_statuses = "('new', 'needs_review', 'verified', 'rejected', 'corrected')"
    for table_name, constraint_name in OBJECT_REVIEW_CONSTRAINTS:
        op.create_check_constraint(constraint_name, table_name, f"review_status in {allowed_statuses}")

    op.create_check_constraint(
        "ck_human_reviews_previous_review_status",
        "human_reviews",
        f"previous_review_status is null or previous_review_status in {allowed_statuses}",
    )
    op.create_check_constraint(
        "ck_human_reviews_new_review_status",
        "human_reviews",
        f"new_review_status is null or new_review_status in {allowed_statuses}",
    )
