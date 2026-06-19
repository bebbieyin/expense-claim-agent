"""Tests for deterministic SROIE experiment preparation."""

import json
from pathlib import Path

import pytest

from experiments.langfuse.evaluators import (
    evaluate_receipt,
    f1,
    ned,
)
from experiments.langfuse.run_experiment import ExperimentProgress
from experiments.langfuse.sroie import (
    expected_receipt,
    normalize_date,
    normalize_total,
    paired_sroie_items,
    sample_sroie_items,
)

SAMPLE_SIZE = 5
EXPECTED_DOLLAR_TOTAL = 6.60


def _create_sroie_fixture(root: Path, count: int = 12) -> Path:
    image_dir = root / "SROIE_test_images_task_3"
    label_dir = root / "SROIE_test_gt_task_3"
    image_dir.mkdir(parents=True)
    label_dir.mkdir(parents=True)
    dates = ("01/02/2018", "02-03-18", "03 APR 2018", "04.05.18")
    totals = ("10.00", "RM 20.00")

    for index in range(count):
        item_id = f"receipt-{index:02d}"
        (image_dir / f"{item_id}.jpg").write_bytes(b"image")
        label = {
            "company": f"Merchant {index}",
            "date": dates[index % len(dates)],
            "address": f"Address {index}",
            "total": totals[index % len(totals)],
        }
        (label_dir / f"{item_id}.txt").write_text(
            json.dumps(label),
            encoding="utf-8",
        )
    return root


def test_sample_is_reproducible(tmp_path: Path) -> None:
    """The same seed and size produce the same document IDs."""
    source = _create_sroie_fixture(tmp_path / "sroie")

    first = sample_sroie_items(
        source,
        sample_size=SAMPLE_SIZE,
        seed=42,
    )
    second = sample_sroie_items(
        source,
        sample_size=SAMPLE_SIZE,
        seed=42,
    )

    assert [item["id"] for item in first] == [item["id"] for item in second]
    assert len(first) == SAMPLE_SIZE


def test_sample_rejects_oversized_request(tmp_path: Path) -> None:
    """A sample cannot request more documents than the source contains."""
    source = _create_sroie_fixture(tmp_path / "sroie", count=3)

    with pytest.raises(ValueError, match="Requested 4 samples"):
        sample_sroie_items(source, sample_size=4, seed=42)


def test_paired_items_reject_missing_label(tmp_path: Path) -> None:
    """Every SROIE image must have a matching label."""
    source = _create_sroie_fixture(tmp_path / "sroie", count=1)
    (source / "SROIE_test_gt_task_3" / "receipt-00.txt").unlink()

    with pytest.raises(ValueError, match="Unpaired SROIE files"):
        paired_sroie_items(source)


def test_sroie_values_map_to_receipt_fields() -> None:
    """SROIE labels normalize to the production extraction names."""
    expected = expected_receipt(
        {
            "company": "Example Sdn Bhd",
            "date": "22 MAR 18",
            "address": "Kuala Lumpur",
            "total": "RM 34.40",
        }
    )

    assert expected == {
        "merchant_name": "Example Sdn Bhd",
        "merchant_address": "Kuala Lumpur",
        "receipt_date": "2018-03-22",
        "total_amount": 34.40,
    }
    assert normalize_date("23.03.18") == "2018-03-23"
    assert normalize_date("2018/03/27") == "2018-03-27"
    assert normalize_date("4/22/2018") == "2018-04-22"
    assert normalize_total("$6.60") == EXPECTED_DOLLAR_TOTAL


def test_receipt_evaluators_score_normalized_values() -> None:
    """Receipt fields use normalized F1 and NED scoring."""
    output = {
        "merchant_name": "EXAMPLE SDN. BHD.",
        "merchant_address": "NO. 1, JALAN EXAMPLE",
        "receipt_date": "2018-03-22",
        "total_amount": 34.40,
    }
    expected = {
        "merchant_name": "Example Sdn Bhd",
        "merchant_address": "No 1 Jalan Example",
        "receipt_date": "2018-03-22",
        "total_amount": 34.40,
    }

    assert f1(output, expected) == 1.0
    assert ned(output, expected) == 1.0


def test_receipt_evaluators_handle_missing_values() -> None:
    """Missing extraction values receive zero F1 and NED scores."""
    output = {
        "merchant_name": None,
        "merchant_address": None,
        "receipt_date": None,
        "total_amount": None,
    }
    expected = {
        "merchant_name": "Example",
        "merchant_address": "Kuala Lumpur",
        "receipt_date": "2018-03-22",
        "total_amount": 34.40,
    }

    assert f1(output, expected) == 0.0
    assert ned(output, expected) == 0.0


def test_receipt_evaluator_outputs_field_and_overall_scores() -> None:
    """Langfuse receives per-field and overall F1 and NED scores."""
    values = {"merchant_name": "Example"}

    evaluations = evaluate_receipt(output=values, expected_output=values)

    assert [(evaluation.name, evaluation.value) for evaluation in evaluations] == [
        ("merchant_name_f1", 1.0),
        ("merchant_name_ned", 1.0),
        ("overall_f1", 1.0),
        ("overall_ned", 1.0),
    ]


def test_experiment_progress_prints_completed_count(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Experiment progress includes completed count, total, status, and item ID."""
    progress = ExperimentProgress(total=2)

    progress.report("receipt-01", succeeded=True)
    progress.report("receipt-02", succeeded=False)

    assert capsys.readouterr().out.splitlines() == [
        "[1/2] completed: receipt-01",
        "[2/2] failed: receipt-02",
    ]
