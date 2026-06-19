"""Claim decision agent."""

from typing import Any

from src.shared.schemas import ClaimReviewState
from src.workflow.agents.utils import append_agent_trail

MINIMUM_EXTRACTION_CONFIDENCE = 0.75


def decision_agent(state: ClaimReviewState) -> dict[str, Any]:
    """Apply deterministic decision precedence."""
    receipt = state["extracted_receipt"] or {}
    validation = state["validation_results"]
    policy = state["policy_results"]
    duplicates = state["duplicate_results"]

    policy_failed = [item for item in policy if item["status"] == "failed"]
    validation_failed = [item for item in validation if item["status"] == "failed"]
    duplicate_warning = any(item["status"] == "warning" for item in duplicates)
    receipt_warning = any(item["status"] == "warning" for item in policy)

    if policy_failed:
        decision = "rejected"
        reason = policy_failed[0]["message"]
    elif float(receipt.get("confidence", 0)) < MINIMUM_EXTRACTION_CONFIDENCE:
        decision = "needs_review"
        reason = "Receipt extraction confidence is below 75%."
    elif validation_failed:
        decision = "needs_review"
        reason = validation_failed[0]["message"]
    elif duplicate_warning:
        decision = "needs_review"
        reason = duplicates[0]["message"]
    elif receipt_warning:
        decision = "needs_review"
        reason = "A required receipt was not provided."
    else:
        decision = "approved"
        reason = "All validation, policy, and duplicate checks passed."

    return {
        "decision": decision,
        "decision_reason": reason,
        "agent_trail": append_agent_trail(
            state,
            "Decision Agent",
            f"Decision: {decision}. {reason}",
        ),
    }
