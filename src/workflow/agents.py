"""Sequential mock agents for the Phase 1 claim review workflow."""

from typing import Any

from sqlalchemy.orm import Session

from src.database.operations import find_duplicate_receipt
from src.shared.schemas import CheckResult, ClaimReviewState, ExtractedReceipt
from src.workflow.extraction import extract_receipt_fields
from src.workflow.ocr import extract_text_from_receipt
from src.workflow.policy import check_policy
from src.workflow.validation import validate_claim

MINIMUM_EXTRACTION_CONFIDENCE = 0.75


def _serialized(results: list[CheckResult]) -> list[dict[str, Any]]:
    return [result.model_dump(mode="json") for result in results]


def _add_trail(state: ClaimReviewState, agent: str, message: str) -> None:
    state["agent_trail"].append({"agent": agent, "message": message})


def receipt_extraction_agent(state: ClaimReviewState) -> None:
    """Populate mock OCR and structured receipt values."""
    raw_text = extract_text_from_receipt(state["receipt_file_path"])
    receipt = extract_receipt_fields(raw_text)
    state["raw_ocr_text"] = raw_text
    state["extracted_receipt"] = receipt.model_dump(mode="json")
    _add_trail(
        state,
        "Receipt Extraction Agent",
        (
            f"Extracted {receipt.merchant_name}, {receipt.receipt_date}, "
            f"{receipt.currency} {receipt.total_amount:.2f} "
            f"with {receipt.confidence:.0%} confidence."
        ),
    )


def claim_validation_agent(state: ClaimReviewState) -> None:
    """Run claim-to-receipt validation."""
    receipt = ExtractedReceipt.model_validate(state["extracted_receipt"])
    results = validate_claim(state["claim"], receipt)
    state["validation_results"] = _serialized(results)
    failed = sum(result.status == "failed" for result in results)
    _add_trail(
        state,
        "Claim Validation Agent",
        f"Completed {len(results)} checks; {failed} failed.",
    )


def policy_compliance_agent(state: ClaimReviewState) -> None:
    """Run hardcoded policy rules."""
    results = check_policy(
        state["claim"],
        receipt_provided=bool(state["receipt_file_path"]),
    )
    state["policy_results"] = _serialized(results)
    failed = sum(result.status == "failed" for result in results)
    _add_trail(
        state,
        "Policy Compliance Agent",
        f"Completed {len(results)} checks; {failed} failed.",
    )


def duplicate_check_agent(
    state: ClaimReviewState,
    session: Session,
    current_claim_id: int,
) -> None:
    """Search prior claims for the same extracted receipt."""
    receipt = state["extracted_receipt"] or {}
    duplicate = find_duplicate_receipt(
        session,
        current_claim_id=current_claim_id,
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
    state["duplicate_results"] = _serialized([result])
    _add_trail(state, "Duplicate Check Agent", result.message)


def decision_agent(state: ClaimReviewState) -> None:
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

    state["decision"] = decision
    state["decision_reason"] = reason
    _add_trail(state, "Decision Agent", f"Decision: {decision}. {reason}")


def explanation_agent(state: ClaimReviewState) -> None:
    """Generate a concise deterministic review summary."""
    claim = state["claim"]
    decision = str(state["decision"]).replace("_", " ")
    state["review_summary"] = (
        f"The claim is {decision}. {state['decision_reason']} "
        f"Claimed amount: {claim['currency']} {float(claim['claimed_amount']):.2f}."
    )
    _add_trail(state, "Explanation Agent", state["review_summary"])


def run_review(
    claim: dict[str, Any],
    receipt_file_path: str,
    session: Session,
    current_claim_id: int,
) -> ClaimReviewState:
    """Run the Phase 1 agents in a controlled sequence."""
    state: ClaimReviewState = {
        "claim": claim,
        "receipt_file_path": receipt_file_path,
        "raw_ocr_text": None,
        "extracted_receipt": None,
        "validation_results": [],
        "policy_results": [],
        "duplicate_results": [],
        "decision": None,
        "decision_reason": None,
        "review_summary": None,
        "langfuse_trace_id": None,
        "agent_trail": [],
    }

    # TODO(phase-5): Use a LangGraph workflow.  # noqa: FIX002, TD003
    receipt_extraction_agent(state)
    claim_validation_agent(state)
    policy_compliance_agent(state)
    duplicate_check_agent(state, session, current_claim_id)
    decision_agent(state)
    explanation_agent(state)
    return state
