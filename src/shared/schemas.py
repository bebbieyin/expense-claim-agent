"""Structured data used by the expense claim review workflow."""

from datetime import date
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class HealthCheck(BaseModel):
    """Health-check response."""

    status: str


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
    merchant_address: str | None = None
    receipt_date: date | None
    total_amount: float | None
    currency: str | None
    confidence: float = Field(ge=0, le=1)


class OCRLine(BaseModel):
    """One OCR text line and its source location."""

    text: str
    page_number: int
    polygon: list[float] = Field(default_factory=list)


class OCRTable(BaseModel):
    """One table extracted from a document."""

    page_number: int | None = None
    rows: list[list[str]]


class OCRResult(BaseModel):
    """Provider-neutral OCR output used by production and experiments."""

    full_text: str
    pages: int
    lines: list[OCRLine] = Field(default_factory=list)
    tables: list[OCRTable] = Field(default_factory=list)
    provider: str
    model: str
    raw_response: dict[str, Any] = Field(default_factory=dict)


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
