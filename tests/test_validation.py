"""Tests for claim-to-receipt validation."""

from src.shared.schemas import ExtractedReceipt
from src.workflow.validation import validate_claim


def test_matching_claim_passes_core_validation() -> None:
    """Matching amount, date, and currency pass."""
    claim = {
        "claimed_amount": 45.90,
        "currency": "MYR",
        "claim_date": "2026-06-18",
    }
    receipt = ExtractedReceipt(
        merchant_name="Restoran ABC",
        receipt_date="2026-06-16",
        total_amount=45.90,
        currency="MYR",
        confidence=0.91,
    )

    results = validate_claim(claim, receipt)

    assert all(result.status == "passed" for result in results)


def test_amount_mismatch_fails_validation() -> None:
    """A material amount difference is flagged."""
    claim = {
        "claimed_amount": 50.00,
        "currency": "MYR",
        "claim_date": "2026-06-18",
    }
    receipt = ExtractedReceipt(
        merchant_name="Restoran ABC",
        receipt_date="2026-06-16",
        total_amount=45.90,
        currency="MYR",
        confidence=0.91,
    )

    results = validate_claim(claim, receipt)

    amount_result = next(result for result in results if result.check == "amount_match")
    assert amount_result.status == "failed"
