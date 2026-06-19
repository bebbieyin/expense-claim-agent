"""Tests for database helpers."""

from unittest.mock import MagicMock, patch

from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.database.operations import (
    create_database_engine,
    get_claim,
    get_database_url,
    list_claims,
    run_migrations,
)

DATABASE_URL = "postgresql+psycopg://localhost:5432/expense_claims"


@patch("src.database.operations.create_engine")
def test_create_database_engine_uses_postgresql_url(
    create_engine: MagicMock,
) -> None:
    """The configured PostgreSQL URL is passed to SQLAlchemy."""
    expected_engine = MagicMock(spec=Engine)
    create_engine.return_value = expected_engine

    engine = create_database_engine(DATABASE_URL)

    create_engine.assert_called_once_with(DATABASE_URL)
    assert engine is expected_engine


@patch.dict(
    "os.environ",
    {
        "DATABASE_URL": "",
        "POSTGRES_USER": "",
        "POSTGRES_HOST": "db",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "test_db",
    },
    clear=True,
)
def test_database_url_is_built_from_environment() -> None:
    """PostgreSQL connection settings can be supplied separately."""
    assert get_database_url() == "postgresql+psycopg://db:5432/test_db"


@patch("src.database.operations.command.upgrade")
@patch("src.database.operations.Config")
def test_run_migrations_targets_alembic_head(
    config_class: MagicMock,
    upgrade: MagicMock,
) -> None:
    """Migrations use the configured PostgreSQL URL and upgrade to head."""
    config = MagicMock(spec=Config)
    config_class.return_value = config

    run_migrations(DATABASE_URL)

    config.set_main_option.assert_called_once_with("sqlalchemy.url", DATABASE_URL)
    upgrade.assert_called_once_with(config, "head")


def test_employee_claim_access_is_scoped() -> None:
    """Employee claim queries include an employee ID restriction."""
    session = MagicMock(spec=Session)
    session.scalars.return_value = []
    session.scalar.return_value = None

    list_claims(session, "EMP-1023")
    get_claim(session, "CLM-0002", "EMP-1023")

    list_statement = session.scalars.call_args.args[0]
    get_statement = session.scalar.call_args.args[0]
    assert "claims.employee_id" in str(list_statement)
    assert "claims.employee_id" in str(get_statement)
