"""LangGraph workflow for expense claim review."""

import os
from dataclasses import dataclass
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from sqlalchemy.orm import Session

from src.client.langfuse_client import (
    get_langfuse_client,
    is_langfuse_enabled,
    observation,
)
from src.database.operations import find_duplicate_receipt
from src.shared.schemas import CheckResult, ClaimReviewState, ExtractedReceipt
from src.workflow.extraction import extract_receipt_fields
from src.workflow.ocr import extract_text_from_receipt
from src.workflow.policy import check_policy
from src.workflow.validation import validate_claim

MINIMUM_EXTRACTION_CONFIDENCE = 0.75


@dataclass
class ReviewContext:
    """Runtime dependencies for claim review nodes."""

    session: Session
    current_claim_id: int


class ClaimReviewError(RuntimeError):
    """A claim review failure with its optional Langfuse trace ID."""

    def __init__(self, message: str, langfuse_trace_id: str | None = None) -> None:
        """Initialize the review failure."""
        super().__init__(message)
        self.langfuse_trace_id = langfuse_trace_id


def _serialized(results: list[CheckResult]) -> list[dict[str, Any]]:
    return [result.model_dump(mode="json") for result in results]


def _trail(
    state: ClaimReviewState,
    agent: str,
    message: str,
) -> list[dict[str, Any]]:
    return [*state["agent_trail"], {"agent": agent, "message": message}]


def receipt_extraction_agent(state: ClaimReviewState) -> dict[str, Any]:
    """Populate OCR and structured receipt values."""
    with observation(
        name="receipt-ocr",
        input_data={"receipt_file_path": state["receipt_file_path"]},
        metadata={"provider": os.getenv("OCR_PROVIDER", "mock")},
    ) as ocr_span:
        raw_text = extract_text_from_receipt(state["receipt_file_path"])
        if ocr_span is not None:
            ocr_span.update(output={"raw_ocr_text": raw_text})

    with observation(
        name="receipt-extraction",
        as_type="generation",
        input_data={"raw_ocr_text": raw_text},
        metadata={
            "provider": os.getenv("LLM_PROVIDER", "mock"),
            "model": os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        },
    ) as extraction_generation:
        receipt = extract_receipt_fields(raw_text)
        if extraction_generation is not None:
            extraction_generation.update(output=receipt.model_dump(mode="json"))

    extracted_receipt = receipt.model_dump(mode="json")
    total_amount = (
        f"{receipt.total_amount:.2f}"
        if receipt.total_amount is not None
        else "unknown amount"
    )
    message = (
        f"Extracted {receipt.merchant_name}, {receipt.receipt_date}, "
        f"{receipt.currency or 'unknown currency'} {total_amount} "
        f"with {receipt.confidence:.0%} confidence."
    )
    return {
        "raw_ocr_text": raw_text,
        "extracted_receipt": extracted_receipt,
        "agent_trail": _trail(state, "Receipt Extraction Agent", message),
    }


def claim_validation_agent(state: ClaimReviewState) -> dict[str, Any]:
    """Run claim-to-receipt validation."""
    receipt = ExtractedReceipt.model_validate(state["extracted_receipt"])
    results = validate_claim(state["claim"], receipt)
    serialized_results = _serialized(results)
    failed = sum(result.status == "failed" for result in results)
    message = f"Completed {len(results)} checks; {failed} failed."
    return {
        "validation_results": serialized_results,
        "agent_trail": _trail(state, "Claim Validation Agent", message),
    }


def policy_compliance_agent(state: ClaimReviewState) -> dict[str, Any]:
    """Run hardcoded policy rules."""
    results = check_policy(
        state["claim"],
        receipt_provided=bool(state["receipt_file_path"]),
    )
    serialized_results = _serialized(results)
    failed = sum(result.status == "failed" for result in results)
    message = f"Completed {len(results)} checks; {failed} failed."
    return {
        "policy_results": serialized_results,
        "agent_trail": _trail(state, "Policy Compliance Agent", message),
    }


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
        "duplicate_results": _serialized([result]),
        "agent_trail": _trail(state, "Duplicate Check Agent", result.message),
    }


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
        "agent_trail": _trail(
            state,
            "Decision Agent",
            f"Decision: {decision}. {reason}",
        ),
    }


def explanation_agent(state: ClaimReviewState) -> dict[str, Any]:
    """Generate a concise deterministic review summary."""
    claim = state["claim"]
    decision = str(state["decision"]).replace("_", " ")
    review_summary = (
        f"The claim is {decision}. {state['decision_reason']} "
        f"Claimed amount: {claim['currency']} {float(claim['claimed_amount']):.2f}."
    )
    return {
        "review_summary": review_summary,
        "agent_trail": _trail(state, "Explanation Agent", review_summary),
    }


def route_after_extraction(
    state: ClaimReviewState,
) -> Literal["claim_validation", "decision"]:
    """Skip receipt-dependent checks when extraction produced no receipt."""
    if state["extracted_receipt"] is None:
        return "decision"
    return "claim_validation"


def route_after_decision(
    state: ClaimReviewState,
) -> Literal["approved", "needs_review", "rejected"]:
    """Route each supported decision to final explanation."""
    decision = state["decision"]
    if decision not in {"approved", "needs_review", "rejected"}:
        msg = f"Unsupported review decision: {decision}"
        raise ValueError(msg)
    return decision


def build_review_graph() -> CompiledStateGraph[
    ClaimReviewState,
    ReviewContext,
    ClaimReviewState,
    ClaimReviewState,
]:
    """Build and compile the claim review workflow."""
    workflow = StateGraph(ClaimReviewState, context_schema=ReviewContext)
    workflow.add_node("receipt_extraction", receipt_extraction_agent)
    workflow.add_node("claim_validation", claim_validation_agent)
    workflow.add_node("policy_compliance", policy_compliance_agent)
    workflow.add_node("duplicate_check", duplicate_check_agent)
    workflow.add_node("decision", decision_agent)
    workflow.add_node("explanation", explanation_agent)

    workflow.add_edge(START, "receipt_extraction")
    workflow.add_conditional_edges(
        "receipt_extraction",
        route_after_extraction,
        {
            "claim_validation": "claim_validation",
            "decision": "decision",
        },
    )
    workflow.add_edge("claim_validation", "policy_compliance")
    workflow.add_edge("policy_compliance", "duplicate_check")
    workflow.add_edge("duplicate_check", "decision")
    workflow.add_conditional_edges(
        "decision",
        route_after_decision,
        {
            "approved": "explanation",
            "needs_review": "explanation",
            "rejected": "explanation",
        },
    )
    workflow.add_edge("explanation", END)
    return workflow.compile()


CLAIM_REVIEW_GRAPH = build_review_graph()


def run_review(
    claim: dict[str, Any],
    receipt_file_path: str,
    session: Session,
    current_claim_id: int,
) -> ClaimReviewState:
    """Run the claim review graph."""
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

    client = get_langfuse_client() if is_langfuse_enabled() else None
    if client is not None:
        state["langfuse_trace_id"] = client.create_trace_id()

    try:
        with observation(
            name="claim-review",
            as_type="chain",
            input_data=claim,
            metadata={"claim_id": claim["claim_id"]},
            trace_id=state["langfuse_trace_id"],
        ) as claim_trace:
            state = CLAIM_REVIEW_GRAPH.invoke(
                state,
                context=ReviewContext(
                    session=session,
                    current_claim_id=current_claim_id,
                ),
            )
            if claim_trace is not None:
                claim_trace.update(
                    output={
                        "decision": state["decision"],
                        "review_summary": state["review_summary"],
                    },
                )
    except Exception as exc:
        raise ClaimReviewError(str(exc), state["langfuse_trace_id"]) from exc
    finally:
        if client is not None:
            client.flush()

    return state
