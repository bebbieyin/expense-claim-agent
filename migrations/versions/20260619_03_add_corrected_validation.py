"""Add corrected receipt validation results."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260619_03"
down_revision: str | None = "20260619_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add validation results generated from corrected receipt fields."""
    op.add_column(
        "claims",
        sa.Column("corrected_validation_results", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove corrected receipt validation results."""
    op.drop_column("claims", "corrected_validation_results")
