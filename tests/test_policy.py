"""Tests for MVP expense policy checks."""

from src.workflow.agents.policy_compliance.policy import check_policy


def test_meal_within_limit_passes() -> None:
    """An allowed claim within its limit passes policy."""
    results = check_policy(
        {"expense_category": "Meals", "claimed_amount": 45.90},
        receipt_provided=True,
    )

    assert all(result.status == "passed" for result in results)


def test_meal_over_limit_fails_policy_limit() -> None:
    """A claim over the category limit fails."""
    results = check_policy(
        {"expense_category": "Meals", "claimed_amount": 101.00},
        receipt_provided=True,
    )

    limit_result = next(result for result in results if result.check == "policy_limit")
    assert limit_result.status == "failed"


def test_category_is_not_checked() -> None:
    """A category without configured policy does not fail review."""
    results = check_policy(
        {"expense_category": "Other", "claimed_amount": 45.90},
        receipt_provided=True,
    )

    assert results == []
