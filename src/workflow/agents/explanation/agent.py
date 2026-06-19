"""Review explanation agent."""

from typing import Any

from src.shared.schemas import ClaimReviewState
from src.workflow.agents.utils import append_agent_trail


def explanation_agent(state: ClaimReviewState) -> dict[str, Any]:
    """Generate a concise deterministic review summary."""
    claim = state["claim"]
    decision = str(state["decision"]).replace("_", " ")
    decision_summary = (
        "The claim needs review"
        if state["decision"] == "needs_review"
        else f"The claim is {decision}"
    )
    review_summary = (
        f"{decision_summary}. {state['decision_reason']} "
        f"Claimed amount: {claim['currency']} {float(claim['claimed_amount']):.2f}."
    )
    return {
        "review_summary": review_summary,
        "agent_trail": append_agent_trail(
            state,
            "Explanation Agent",
            review_summary,
        ),
    }
