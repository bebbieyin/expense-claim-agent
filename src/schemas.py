"""Structured data used by the expense claim review workflow."""

from datetime import date
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class ClaimCreate(BaseModel):
    """User-submitted expense claim."""

    claim_id: str
    employee_id: str
    employee_name: str
    department: str
    claim_date: date
    expense_category: str
    expense_purpose: str
    claimed_amount: float = Field(gt=0)
    currency: str = "MYR"
    receipt_file_path: str


class ExtractedReceipt(BaseModel):
    """Structured values extracted from a receipt."""

    merchant_name: str | None
    receipt_date: date | None
    total_amount: float | None
    currency: str | None
    confidence: float = Field(ge=0, le=1)
    source_text: str


class CheckResult(BaseModel):
    """Result of one deterministic review check."""

    check: str
    status: Literal["passed", "failed", "warning", "skipped"]
    message: str


class ClaimReviewState(TypedDict):
    """Shared state passed through the mock review agents."""

    claim: dict[str, Any]
    receipt_file_path: str
    raw_ocr_text: str | None
    extracted_receipt: dict[str, Any] | None
    validation_results: list[dict[str, Any]]
    policy_results: list[dict[str, Any]]
    duplicate_results: list[dict[str, Any]]
    decision: str | None
    decision_reason: str | None
    review_summary: str | None
    langfuse_trace_id: str | None
    agent_trail: list[dict[str, Any]]
