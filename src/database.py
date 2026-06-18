"""SQLite persistence helpers for expense claims."""

import json
import os
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.models import Base, Claim, Employee
from src.schemas import ClaimCreate, ClaimReviewState

DEFAULT_DATABASE_URL = "sqlite:///data/expense_claims.db"
AMOUNT_TOLERANCE = 0.01


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create an engine, ensuring the local SQLite directory exists."""
    url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    if url.startswith("sqlite:///") and url != "sqlite:///:memory:":
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, connect_args={"check_same_thread": False})


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_database(db_engine: Engine = engine) -> None:
    """Create application tables for isolated tests."""
    Base.metadata.create_all(db_engine)


def run_migrations(database_url: str | None = None) -> None:
    """Apply all pending Alembic migrations."""
    config = Config(Path(__file__).parent.parent / "alembic.ini")
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def list_employees(session: Session) -> list[Employee]:
    """Return employees ordered by name."""
    return list(session.scalars(select(Employee).order_by(Employee.employee_name)))


def create_claim(session: Session, claim_data: ClaimCreate) -> Claim:
    """Persist a new claim in processing state."""
    claim = Claim(**claim_data.model_dump(), status="processing")
    session.add(claim)
    session.commit()
    return claim


def update_claim_review(
    session: Session,
    claim: Claim,
    state: ClaimReviewState,
) -> None:
    """Store the completed review state on a claim."""
    claim.status = "reviewed"
    claim.decision = state["decision"]
    claim.review_summary = state["review_summary"]
    claim.raw_agent_state = json.dumps(state, default=str)
    claim.langfuse_trace_id = state["langfuse_trace_id"]
    session.commit()


def list_claims(session: Session, employee_id: str | None = None) -> list[Claim]:
    """Return newest claims, optionally scoped to one employee."""
    statement = select(Claim).order_by(Claim.created_at.desc(), Claim.id.desc())
    if employee_id:
        statement = statement.where(Claim.employee_id == employee_id)
    return list(session.scalars(statement))


def get_claim(
    session: Session,
    claim_id: str,
    employee_id: str | None = None,
) -> Claim | None:
    """Find a claim, optionally restricting access to one employee."""
    statement = select(Claim).where(Claim.claim_id == claim_id)
    if employee_id:
        statement = statement.where(Claim.employee_id == employee_id)
    return session.scalar(statement)


def find_duplicate_receipt(
    session: Session,
    *,
    current_claim_id: int,
    employee_id: str,
    receipt: dict[str, Any],
) -> Claim | None:
    """Find a prior reviewed claim with matching receipt attributes."""
    merchant_name = receipt.get("merchant_name")
    receipt_date = receipt.get("receipt_date")
    total_amount = receipt.get("total_amount")
    if merchant_name is None or receipt_date is None or total_amount is None:
        return None

    candidates = session.scalars(
        select(Claim).where(
            Claim.employee_id == employee_id,
            Claim.id != current_claim_id,
            Claim.raw_agent_state.is_not(None),
        ),
    )
    for candidate in candidates:
        try:
            state: dict[str, Any] = json.loads(candidate.raw_agent_state or "{}")
            receipt = state.get("extracted_receipt") or {}
        except json.JSONDecodeError:
            continue
        if (
            receipt.get("merchant_name") == merchant_name
            and receipt.get("receipt_date") == receipt_date
            and receipt.get("total_amount") is not None
            and abs(float(receipt["total_amount"]) - float(total_amount))
            <= AMOUNT_TOLERANCE
        ):
            return candidate
    return None
