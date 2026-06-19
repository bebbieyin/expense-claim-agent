"""Claim validation agent."""

from typing import Any

from src.shared.schemas import ClaimReviewState, ExtractedReceipt
from src.workflow.agents.claim_validation.validation import validate_claim
from src.workflow.agents.utils import append_agent_trail, serialize_results


def claim_validation_agent(state: ClaimReviewState) -> dict[str, Any]:
    """Run claim-to-receipt validation."""
    receipt = ExtractedReceipt.model_validate(state["extracted_receipt"])
    results = validate_claim(state["claim"], receipt)
    serialized_results = serialize_results(results)
    failed = sum(result.status == "failed" for result in results)
    message = f"Completed {len(results)} checks; {failed} failed."
    return {
        "validation_results": serialized_results,
        "agent_trail": append_agent_trail(
            state,
            "Claim Validation Agent",
            message,
        ),
    }
