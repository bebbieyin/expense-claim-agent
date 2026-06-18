"""Receipt field extraction placeholder."""

from src.schemas import ExtractedReceipt


def extract_receipt_fields(raw_ocr_text: str) -> ExtractedReceipt:
    """Return deterministic mock receipt fields."""
    # TODO(phase-3): Add managed LLM extraction.  # noqa: FIX002, TD003
    return ExtractedReceipt(
        merchant_name="Restoran ABC",
        receipt_date="2026-06-16",
        total_amount=45.90,
        currency="MYR",
        confidence=0.91,
        source_text=raw_ocr_text,
    )
