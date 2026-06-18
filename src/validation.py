"""Deterministic validation rules for submitted claims."""

from datetime import date
from typing import Any

from src.schemas import CheckResult, ExtractedReceipt

AMOUNT_TOLERANCE = 0.01


def validate_claim(
    claim: dict[str, Any],
    receipt: ExtractedReceipt,
) -> list[CheckResult]:
    """Compare claim fields with extracted receipt values."""
    results: list[CheckResult] = []

    amount_matches = (
        receipt.total_amount is not None
        and abs(float(claim["claimed_amount"]) - receipt.total_amount)
        <= AMOUNT_TOLERANCE
    )
    results.append(
        CheckResult(
            check="amount_match",
            status="passed" if amount_matches else "failed",
            message=(
                "Claimed amount matches receipt total."
                if amount_matches
                else "Claimed amount does not match receipt total."
            ),
        ),
    )

    claim_date = claim["claim_date"]
    if isinstance(claim_date, str):
        claim_date = date.fromisoformat(claim_date)
    valid_date = receipt.receipt_date is not None and receipt.receipt_date <= claim_date
    results.append(
        CheckResult(
            check="date_validity",
            status="passed" if valid_date else "failed",
            message=(
                "Receipt date is on or before the claim date."
                if valid_date
                else "Receipt date is missing or after the claim date."
            ),
        ),
    )

    required_values = {
        "required_merchant": (receipt.merchant_name, "merchant name"),
        "required_date": (receipt.receipt_date, "receipt date"),
        "required_total": (receipt.total_amount, "receipt total"),
    }
    for check, (value, label) in required_values.items():
        present = value is not None and value != ""
        results.append(
            CheckResult(
                check=check,
                status="passed" if present else "failed",
                message=f"Required {label} is {'present' if present else 'missing'}.",
            ),
        )

    currency_matches = receipt.currency == claim["currency"]
    results.append(
        CheckResult(
            check="currency_match",
            status="passed" if currency_matches else "failed",
            message=(
                "Claim and receipt currencies match."
                if currency_matches
                else "Claim and receipt currencies do not match."
            ),
        ),
    )

    positive_amount = float(claim["claimed_amount"]) > 0
    results.append(
        CheckResult(
            check="positive_amount",
            status="passed" if positive_amount else "failed",
            message=(
                "Claimed amount is greater than zero."
                if positive_amount
                else "Claimed amount must be greater than zero."
            ),
        ),
    )
    return results
