"""Tests for database helpers."""

from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from src.database import (
    create_database_engine,
    get_claim,
    list_claims,
    list_employees,
    run_migrations,
)
from src.models import Claim


def test_migration_creates_default_employees(tmp_path: Path) -> None:
    """The head migration creates employees for claim submission."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"

    run_migrations(database_url)

    engine = create_database_engine(database_url)
    with Session(engine) as session:
        employees = list_employees(session)

    assert [
        (employee.employee_id, employee.employee_name) for employee in employees
    ] == [
        ("EMP-1023", "Alicia Tan"),
        ("EMP-2044", "Daniel Lee"),
        ("EMP-3381", "Mei Wong"),
    ]


def test_employee_claim_access_is_scoped(tmp_path: Path) -> None:
    """Employees can list and retrieve only their own claims."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    run_migrations(database_url)
    engine = create_database_engine(database_url)

    with Session(engine) as session:
        session.add_all(
            [
                Claim(
                    claim_id="CLM-0001",
                    employee_id="EMP-1023",
                    employee_name="Alicia Tan",
                    department="Sales & Marketing",
                    claim_date=date(2026, 6, 18),
                    expense_category="Meals",
                    expense_purpose="Client lunch",
                    claimed_amount=45.90,
                    currency="MYR",
                    receipt_file_path="receipt-1.png",
                ),
                Claim(
                    claim_id="CLM-0002",
                    employee_id="EMP-2044",
                    employee_name="Daniel Lee",
                    department="IT",
                    claim_date=date(2026, 6, 18),
                    expense_category="Transport",
                    expense_purpose="Site visit",
                    claimed_amount=20.00,
                    currency="MYR",
                    receipt_file_path="receipt-2.png",
                ),
            ],
        )
        session.commit()

        claims = list_claims(session, "EMP-1023")

        assert [claim.claim_id for claim in claims] == ["CLM-0001"]
        assert get_claim(session, "CLM-0002", "EMP-1023") is None
        assert get_claim(session, "CLM-0002") is not None
