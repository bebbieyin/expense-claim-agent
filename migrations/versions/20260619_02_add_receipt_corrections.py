"""Add extracted and corrected receipt fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260619_02"
down_revision: str | None = "20260618_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add queryable extraction and correction data to claims."""
    op.add_column("claims", sa.Column("extracted_receipt", sa.JSON(), nullable=True))
    op.add_column("claims", sa.Column("corrected_receipt", sa.JSON(), nullable=True))
    op.add_column(
        "claims",
        sa.Column("corrected_by", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "claims",
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE claims
        SET extracted_receipt = CAST(raw_agent_state AS JSON) -> 'extracted_receipt'
        WHERE raw_agent_state IS NOT NULL
          AND raw_agent_state <> ''
        """,
    )


def downgrade() -> None:
    """Remove receipt correction fields."""
    op.drop_column("claims", "corrected_at")
    op.drop_column("claims", "corrected_by")
    op.drop_column("claims", "corrected_receipt")
    op.drop_column("claims", "extracted_receipt")
