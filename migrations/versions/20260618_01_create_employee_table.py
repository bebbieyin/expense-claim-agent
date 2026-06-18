"""Create employee table and establish the schema baseline."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260618_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_EMPLOYEES = [
    {"employee_id": "EMP-1023", "employee_name": "Alicia Tan"},
    {"employee_id": "EMP-2044", "employee_name": "Daniel Lee"},
    {"employee_id": "EMP-3381", "employee_name": "Mei Wong"},
]


def upgrade() -> None:
    """Create missing tables and populate employees."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if "claims" not in inspector.get_table_names():
        op.create_table(
            "claims",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("claim_id", sa.String(length=32), nullable=False),
            sa.Column("employee_id", sa.String(length=64), nullable=False),
            sa.Column("employee_name", sa.String(length=120), nullable=False),
            sa.Column("department", sa.String(length=120), nullable=False),
            sa.Column("claim_date", sa.Date(), nullable=False),
            sa.Column("expense_category", sa.String(length=64), nullable=False),
            sa.Column("expense_purpose", sa.Text(), nullable=False),
            sa.Column("claimed_amount", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("receipt_file_path", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("decision", sa.String(length=32), nullable=True),
            sa.Column("review_summary", sa.Text(), nullable=True),
            sa.Column("raw_agent_state", sa.Text(), nullable=True),
            sa.Column("langfuse_trace_id", sa.String(length=120), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_claims_claim_id", "claims", ["claim_id"], unique=True)
        op.create_index("ix_claims_employee_id", "claims", ["employee_id"])

    if "employees" not in inspector.get_table_names():
        op.create_table(
            "employees",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("employee_id", sa.String(length=64), nullable=False),
            sa.Column("employee_name", sa.String(length=120), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_employees_employee_id",
            "employees",
            ["employee_id"],
            unique=True,
        )
        op.create_index(
            "ix_employees_employee_name",
            "employees",
            ["employee_name"],
        )

    employees = sa.table(
        "employees",
        sa.column("employee_id", sa.String()),
        sa.column("employee_name", sa.String()),
    )
    existing_ids = set(connection.scalars(sa.select(employees.c.employee_id)))
    claim_employees = connection.execute(
        sa.text(
            "SELECT DISTINCT employee_id, employee_name FROM claims "
            "WHERE employee_id IS NOT NULL AND employee_name IS NOT NULL",
        ),
    )
    employee_rows = [
        employee
        for employee in DEFAULT_EMPLOYEES
        if employee["employee_id"] not in existing_ids
    ]
    employee_rows.extend(
        {"employee_id": employee_id, "employee_name": employee_name}
        for employee_id, employee_name in claim_employees
        if employee_id not in existing_ids
        and employee_id not in {employee["employee_id"] for employee in employee_rows}
    )
    if employee_rows:
        op.bulk_insert(employees, employee_rows)


def downgrade() -> None:
    """Remove the employee table."""
    op.drop_index("ix_employees_employee_name", table_name="employees")
    op.drop_index("ix_employees_employee_id", table_name="employees")
    op.drop_table("employees")
