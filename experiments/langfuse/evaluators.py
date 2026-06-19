"""Deterministic receipt extraction evaluators."""

import re
from collections import Counter

from langfuse import Evaluation


def normalize_text(value: object) -> str:
    """Normalize text for case- and punctuation-insensitive comparison."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", str(value).casefold())).strip()


def _field_f1(output_value: object, expected_value: object) -> float:
    """Calculate token-overlap F1 for one field."""
    output_tokens = normalize_text(output_value).split()
    expected_tokens = normalize_text(expected_value).split()
    if not output_tokens and not expected_tokens:
        return 1.0
    if not output_tokens or not expected_tokens:
        return 0.0

    matches = sum((Counter(output_tokens) & Counter(expected_tokens)).values())
    precision = matches / len(output_tokens)
    recall = matches / len(expected_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _edit_distance(first: str, second: str) -> int:
    """Calculate the Levenshtein edit distance between two strings."""
    previous = list(range(len(second) + 1))
    for first_index, first_character in enumerate(first, start=1):
        current = [first_index]
        for second_index, second_character in enumerate(second, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[second_index] + 1,
                    previous[second_index - 1] + (first_character != second_character),
                )
            )
        previous = current
    return previous[-1]


def _field_ned(output_value: object, expected_value: object) -> float:
    """Calculate normalized edit-distance similarity for one field."""
    output_text = normalize_text(output_value)
    expected_text = normalize_text(expected_value)
    if not output_text and not expected_text:
        return 1.0
    if not output_text or not expected_text:
        return 0.0

    distance = _edit_distance(output_text, expected_text)
    return 1 - distance / max(len(output_text), len(expected_text))


def f1(output: dict[str, object], expected: dict[str, object]) -> float:
    """Calculate mean token-overlap F1 across expected fields."""
    if not expected:
        return 1.0
    return sum(
        _field_f1(output.get(field), expected_value)
        for field, expected_value in expected.items()
    ) / len(expected)


def ned(output: dict[str, object], expected: dict[str, object]) -> float:
    """Calculate mean normalized edit-distance similarity across expected fields."""
    if not expected:
        return 1.0
    return sum(
        _field_ned(output.get(field), expected_value)
        for field, expected_value in expected.items()
    ) / len(expected)


def evaluate_receipt(
    *,
    output: dict[str, object],
    expected_output: dict[str, object],
    **_: object,
) -> list[Evaluation]:
    """Return per-field and overall F1 and NED evaluations."""
    evaluations = []
    f1_scores = []
    ned_scores = []

    for field, expected_value in expected_output.items():
        output_value = output.get(field)
        f1_score = _field_f1(output_value, expected_value)
        ned_score = _field_ned(output_value, expected_value)
        f1_scores.append(f1_score)
        ned_scores.append(ned_score)
        evaluations.extend(
            [
                Evaluation(name=f"{field}_f1", value=f1_score),
                Evaluation(name=f"{field}_ned", value=ned_score),
            ]
        )

    overall_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 1.0
    overall_ned = sum(ned_scores) / len(ned_scores) if ned_scores else 1.0
    evaluations.extend(
        [
            Evaluation(name="overall_f1", value=overall_f1),
            Evaluation(name="overall_ned", value=overall_ned),
        ]
    )
    return evaluations
