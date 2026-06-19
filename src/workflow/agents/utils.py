"""Shared helpers for expense claim review agents."""

from typing import Any

from src.shared.schemas import CheckResult, ClaimReviewState


def serialize_results(results: list[CheckResult]) -> list[dict[str, Any]]:
    """Serialize check results for the shared workflow state."""
    return [result.model_dump(mode="json") for result in results]


def append_agent_trail(
    state: ClaimReviewState,
    agent: str,
    message: str,
) -> list[dict[str, Any]]:
    """Append an agent result to the review trail."""
    return [*state["agent_trail"], {"agent": agent, "message": message}]
