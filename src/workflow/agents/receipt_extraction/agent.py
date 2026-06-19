"""Receipt extraction agent."""

import os
from typing import Any

from src.client.langfuse_client import observation
from src.shared.schemas import ClaimReviewState
from src.workflow.agents.receipt_extraction.extraction import extract_receipt_fields
from src.workflow.agents.receipt_extraction.ocr import extract_text_from_receipt
from src.workflow.agents.utils import append_agent_trail


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
        "agent_trail": append_agent_trail(
            state,
            "Receipt Extraction Agent",
            message,
        ),
    }
