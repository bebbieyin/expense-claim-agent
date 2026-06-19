"""Integration tests for the sequential mock review workflow."""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from src.workflow.agents import ClaimReviewError, run_review

EXPECTED_AGENT_COUNT = 6


class FakeObservation:
    """Capture updates made to a Langfuse observation."""

    def __init__(self) -> None:
        """Initialize captured updates."""
        self.updates: list[dict[str, object]] = []

    def update(self, **values: object) -> None:
        """Capture one observation update."""
        self.updates.append(values)


class FakeLangfuseClient:
    """Minimal Langfuse client used by workflow tests."""

    def __init__(self) -> None:
        """Initialize captured observations."""
        self.observations: list[tuple[dict[str, object], FakeObservation]] = []
        self.flushed = False

    def create_trace_id(self) -> str:
        """Return a deterministic test trace ID."""
        return "test-trace-id"

    @contextmanager
    def start_as_current_observation(
        self,
        **values: object,
    ) -> object:
        """Capture and yield an observation."""
        observation = FakeObservation()
        self.observations.append((values, observation))
        yield observation

    def flush(self) -> None:
        """Record that pending observations were flushed."""
        self.flushed = True


@pytest.fixture(autouse=True)
def mock_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep mock workflow tests independent from local provider settings."""
    monkeypatch.setenv("OCR_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")


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


def test_langfuse_traces_claim_ocr_and_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enabled tracing records a claim chain and extraction observations."""
    client = FakeLangfuseClient()
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setattr(
        "src.workflow.agents.get_langfuse_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "src.client.langfuse_client.get_langfuse_client",
        lambda: client,
    )
    session = MagicMock(spec=Session)
    session.scalars.return_value = []
    claim = {
        "claim_id": "CLM-0003",
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

    state = run_review(claim, "receipt.png", session, current_claim_id=3)

    assert state["langfuse_trace_id"] == "test-trace-id"
    assert [values["name"] for values, _ in client.observations] == [
        "claim-review",
        "receipt-ocr",
        "receipt-extraction",
    ]
    assert client.observations[0][0]["trace_context"] == {"trace_id": "test-trace-id"}
    assert client.observations[2][0]["as_type"] == "generation"
    assert client.flushed is True


def test_review_failure_preserves_langfuse_trace_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed traced review exposes its trace ID for persistence."""
    client = FakeLangfuseClient()
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setattr(
        "src.workflow.agents.get_langfuse_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "src.client.langfuse_client.get_langfuse_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "src.workflow.agents.extract_text_from_receipt",
        MagicMock(side_effect=RuntimeError("OCR failed")),
    )
    session = MagicMock(spec=Session)
    claim = {
        "claim_id": "CLM-0004",
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

    with pytest.raises(ClaimReviewError, match="OCR failed") as error:
        run_review(claim, "receipt.png", session, current_claim_id=4)

    assert error.value.langfuse_trace_id == "test-trace-id"
    assert client.flushed is True
