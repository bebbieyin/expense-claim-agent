"""Duplicate check agent."""

from dataclasses import dataclass
from typing import Any

from langgraph.runtime import Runtime
from sqlalchemy.orm import Session

from src.database.operations import find_duplicate_receipt
from src.shared.schemas import CheckResult, ClaimReviewState
from src.workflow.agents.utils import append_agent_trail, serialize_results


@dataclass
class ReviewContext:
    """Runtime dependencies for claim review nodes."""

    session: Session
    current_claim_id: int


def duplicate_check_agent(
    state: ClaimReviewState,
    runtime: Runtime[ReviewContext],
) -> dict[str, Any]:
    """Search prior claims for the same extracted receipt."""
    receipt = state["extracted_receipt"] or {}
    duplicate = find_duplicate_receipt(
        runtime.context.session,
        current_claim_id=runtime.context.current_claim_id,
        employee_id=str(state["claim"]["employee_id"]),
        receipt=receipt,
    )
    result = CheckResult(
        check="duplicate_claim",
        status="warning" if duplicate else "passed",
        message=(
            f"Possible duplicate of {duplicate.claim_id} was found."
            if duplicate
            else "No duplicate claim was found."
        ),
    )
    return {
        "duplicate_results": serialize_results([result]),
        "agent_trail": append_agent_trail(
            state,
            "Duplicate Check Agent",
            result.message,
        ),
    }
