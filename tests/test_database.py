"""Tests for database helpers."""

from pathlib import Path

from sqlalchemy.orm import Session

from src.database import create_database_engine, list_employees, run_migrations


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
