"""Hardcoded MVP expense policy checks."""

from typing import Any

from src.shared.schemas import CheckResult

POLICIES: dict[str, dict[str, float | bool]] = {
    "Meals": {"max_amount": 100.0, "receipt_required": True},
    "Transport": {"max_amount": 200.0, "receipt_required": True},
    "Office Supplies": {"max_amount": 300.0, "receipt_required": True},
    "Medical": {"max_amount": 500.0, "receipt_required": True},
}


def check_policy(
    claim: dict[str, Any],
    *,
    receipt_provided: bool,
) -> list[CheckResult]:
    """Check a claim against the allowed categories and limits."""
    category = str(claim["expense_category"])
    policy = POLICIES.get(category)
    if policy is None:
        return [
            CheckResult(
                check="allowed_category",
                status="failed",
                message=f"{category} is not an allowed expense category.",
            ),
        ]

    amount = float(claim["claimed_amount"])
    limit = float(policy["max_amount"])
    within_limit = amount <= limit
    receipt_ok = receipt_provided or not bool(policy["receipt_required"])
    return [
        CheckResult(
            check="allowed_category",
            status="passed",
            message=f"{category} is an allowed expense category.",
        ),
        CheckResult(
            check="policy_limit",
            status="passed" if within_limit else "failed",
            message=(
                f"{category} claim is within the MYR {limit:.2f} policy limit."
                if within_limit
                else f"{category} claim exceeds the MYR {limit:.2f} policy limit."
            ),
        ),
        CheckResult(
            check="receipt_required",
            status="passed" if receipt_ok else "warning",
            message=(
                "Required receipt was provided."
                if receipt_ok
                else "A receipt is required but was not provided."
            ),
        ),
    ]
