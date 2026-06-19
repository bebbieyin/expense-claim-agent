"""LangGraph workflow for expense claim review."""

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from src.client.langfuse_client import (
    get_langfuse_client,
    is_langfuse_enabled,
    observation,
)
from src.shared.schemas import ClaimReviewState
from src.workflow.agents.claim_validation import claim_validation_agent
from src.workflow.agents.decision import decision_agent
from src.workflow.agents.duplicate_check import ReviewContext, duplicate_check_agent
from src.workflow.agents.explanation import explanation_agent
from src.workflow.agents.policy_compliance import policy_compliance_agent
from src.workflow.agents.receipt_extraction import receipt_extraction_agent


class ClaimReviewError(RuntimeError):
    """A claim review failure with its optional Langfuse trace ID."""

    def __init__(self, message: str, langfuse_trace_id: str | None = None) -> None:
        """Initialize the review failure."""
        super().__init__(message)
        self.langfuse_trace_id = langfuse_trace_id


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
