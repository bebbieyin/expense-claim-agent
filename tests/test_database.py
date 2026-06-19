"""Tests for database helpers."""

from unittest.mock import MagicMock, patch

import pytest
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.database.operations import (
    create_database_engine,
    get_claim,
    get_database_url,
    list_claims,
    list_claims_needing_review,
    resolve_claim_review,
    run_migrations,
    update_claim_review,
    update_receipt_correction,
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


def test_review_queue_only_contains_pending_claims() -> None:
    """Human review queue filters to pending claims."""
    session = MagicMock(spec=Session)
    session.scalars.return_value = []

    list_claims_needing_review(session)

    statement = session.scalars.call_args.args[0]
    assert "claims.status" in str(statement)
    assert "pending_review" in str(statement.compile().params.values())


def test_human_review_resolves_pending_claim() -> None:
    """An approver decision resolves and audits an escalated claim."""
    session = MagicMock(spec=Session)
    claim = MagicMock()
    claim.status = "pending_review"

    resolve_claim_review(
        session,
        claim,
        "approved",
        "Receipt verified.",
        "Reviewer Team",
    )

    assert claim.status == "reviewed"
    assert claim.decision == "approved"
    assert claim.human_review_decision == "approved"
    assert claim.human_review_notes == "Receipt verified."
    assert claim.human_reviewed_by == "Reviewer Team"
    assert claim.human_reviewed_at is not None
    session.commit.assert_called_once()


def test_human_review_rejects_non_pending_claim() -> None:
    """Claims outside the review queue cannot be resolved again."""
    session = MagicMock(spec=Session)
    claim = MagicMock()
    claim.status = "reviewed"

    with pytest.raises(ValueError, match="pending human review"):
        resolve_claim_review(session, claim, "rejected", "", "Reviewer Team")

    session.commit.assert_not_called()


def test_receipt_correction_preserves_extracted_receipt() -> None:
    """Human corrections are stored separately from AI extraction."""
    session = MagicMock(spec=Session)
    claim = MagicMock()
    claim.extracted_receipt = {"total_amount": 55.0}
    corrected = {
        "merchant_name": "Example Store",
        "merchant_address": None,
        "receipt_date": "2026-06-19",
        "total_amount": 56.0,
        "currency": "MYR",
    }
    validation_results = [
        {
            "check": "amount_match",
            "status": "passed",
            "message": "Claimed amount matches receipt total.",
        },
    ]

    update_receipt_correction(
        session,
        claim,
        corrected,
        validation_results,
        "EMP-1023",
    )

    assert claim.extracted_receipt == {"total_amount": 55.0}
    assert claim.corrected_receipt == corrected
    assert claim.corrected_validation_results == validation_results
    assert claim.corrected_by == "EMP-1023"
    assert claim.corrected_at is not None
    session.commit.assert_called_once()


def test_claim_review_stores_extracted_receipt_for_evaluation() -> None:
    """Completed reviews persist a queryable extraction snapshot."""
    session = MagicMock(spec=Session)
    claim = MagicMock()
    extracted = {"merchant_name": "Example Store", "total_amount": 56.0}
    state = {
        "decision": "approved",
        "review_summary": "Approved.",
        "extracted_receipt": extracted,
        "langfuse_trace_id": "trace-id",
    }

    update_claim_review(session, claim, state)  # type: ignore[arg-type]

    assert claim.extracted_receipt == extracted
    assert claim.status == "reviewed"
    session.commit.assert_called_once()


def test_needs_review_is_escalated_to_pending_status() -> None:
    """Automated needs-review decisions enter the human review queue."""
    session = MagicMock(spec=Session)
    claim = MagicMock()
    state = {
        "decision": "needs_review",
        "review_summary": "Manual review required.",
        "extracted_receipt": {},
        "langfuse_trace_id": None,
    }

    update_claim_review(session, claim, state)  # type: ignore[arg-type]

    assert claim.status == "pending_review"
    assert claim.decision == "needs_review"
