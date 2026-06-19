"""Integration tests for the sequential mock review workflow."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from src.agents import run_review

EXPECTED_AGENT_COUNT = 6


@pytest.fixture(autouse=True)
def mock_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep mock workflow tests independent from local provider settings."""
    monkeypatch.setenv("OCR_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")


def test_mock_review_approves_matching_claim() -> None:
    """The documented mock claim reaches an approved decision."""
    session = MagicMock(spec=Session)
    session.scalars.return_value = []
    claim = {
        "claim_id": "CLM-0001",
        "employee_id": "EMP-1023",
        "employee_name": "Alicia Tan",
        "department": "Sales",
        "claim_date": "2026-06-18",
        "expense_category": "Meals",
        "expense_purpose": "Client lunch",
        "claimed_amount": 45.90,
        "currency": "MYR",
        "receipt_file_path": "receipt.png",
    }

    state = run_review(claim, "receipt.png", session, current_claim_id=1)

    assert state["decision"] == "approved"
    assert len(state["agent_trail"]) == EXPECTED_AGENT_COUNT


def test_policy_violation_is_rejected() -> None:
    """A clear policy limit violation takes rejection precedence."""
    session = MagicMock(spec=Session)
    session.scalars.return_value = []
    claim = {
        "claim_id": "CLM-0002",
        "employee_id": "EMP-1023",
        "employee_name": "Alicia Tan",
        "department": "Sales",
        "claim_date": "2026-06-18",
        "expense_category": "Meals",
        "expense_purpose": "Large team meal",
        "claimed_amount": 150.00,
        "currency": "MYR",
        "receipt_file_path": "receipt.png",
    }

    state = run_review(claim, "receipt.png", session, current_claim_id=2)

    assert state["decision"] == "rejected"
