"""Policy compliance agent."""

from typing import Any

from src.shared.schemas import ClaimReviewState
from src.workflow.agents.policy_compliance.policy import check_policy
from src.workflow.agents.utils import append_agent_trail, serialize_results


def policy_compliance_agent(state: ClaimReviewState) -> dict[str, Any]:
    """Run hardcoded policy rules."""
    results = check_policy(
        state["claim"],
        receipt_provided=bool(state["receipt_file_path"]),
    )
    serialized_results = serialize_results(results)
    failed = sum(result.status == "failed" for result in results)
    message = f"Completed {len(results)} checks; {failed} failed."
    return {
        "policy_results": serialized_results,
        "agent_trail": append_agent_trail(
            state,
            "Policy Compliance Agent",
            message,
        ),
    }
