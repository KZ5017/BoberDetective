"""allow corrected contradiction candidates with partial pairs

Revision ID: 0049_contradiction_partial_pair
Revises: 0048_review_status_cleanup
Create Date: 2026-06-19
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0049_contradiction_partial_pair"
down_revision: str | None = "0048_review_status_cleanup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_contradiction_candidates_has_pair", "contradiction_candidates", type_="check")
    op.create_check_constraint(
        "ck_contradiction_candidates_has_pair",
        "contradiction_candidates",
        "(claim_id_a is not null and claim_id_b is not null) or "
        "(event_id_a is not null and event_id_b is not null) or "
        "review_status = 'corrected'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_contradiction_candidates_has_pair", "contradiction_candidates", type_="check")
    op.create_check_constraint(
        "ck_contradiction_candidates_has_pair",
        "contradiction_candidates",
        "(claim_id_a is not null and claim_id_b is not null) or "
        "(event_id_a is not null and event_id_b is not null)",
    )
