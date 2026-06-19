"""Add human review audit fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260619_04"
down_revision: str | None = "20260619_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add human review decision and audit fields to claims."""
    op.add_column(
        "claims",
        sa.Column("human_review_decision", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("human_review_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("human_reviewed_by", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("human_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE claims
        SET status = 'pending_review'
        WHERE decision = 'needs_review'
          AND status = 'reviewed'
        """,
    )


def downgrade() -> None:
    """Remove human review audit fields."""
    op.drop_column("claims", "human_reviewed_at")
    op.drop_column("claims", "human_reviewed_by")
    op.drop_column("claims", "human_review_notes")
    op.drop_column("claims", "human_review_decision")
