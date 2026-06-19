"""Shared SROIE dataset parsing and normalization."""

import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any

DATE_FORMATS = (
    "%Y/%m/%d",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%d %b %Y",
    "%d %b %y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d/%b/%Y",
    "%d/%b/%y",
    "%d.%m.%Y",
    "%d.%m.%y",
    "%m/%d/%Y",
    "%m/%d/%y",
)


def load_sroie_label(path: Path) -> dict[str, str]:
    """Load one SROIE Task 3 ground-truth file."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    required = {"company", "date", "address", "total"}
    missing = required - data.keys()
    if missing:
        msg = f"{path.name} is missing fields: {sorted(missing)}"
        raise ValueError(msg)
    return {key: str(data[key]).strip() for key in required}


def normalize_date(value: str) -> str:
    """Normalize a SROIE date to ISO format."""
    cleaned = re.sub(r"\s+", " ", value.strip()).upper()
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, date_format).date().isoformat()  # noqa: DTZ007
        except ValueError:
            continue
    msg = f"Unsupported SROIE date format: {value}"
    raise ValueError(msg)


def normalize_total(value: str) -> float:
    """Normalize a SROIE total to a decimal number."""
    cleaned = re.sub(r"[^0-9.\-]", "", value)
    try:
        return float(cleaned)
    except ValueError as exc:
        msg = f"Unsupported SROIE total: {value}"
        raise ValueError(msg) from exc


def expected_receipt(label: dict[str, str]) -> dict[str, Any]:
    """Map SROIE labels to the production receipt field names."""
    return {
        "merchant_name": label["company"],
        "merchant_address": label["address"],
        "receipt_date": normalize_date(label["date"]),
        "total_amount": normalize_total(label["total"]),
    }


def paired_sroie_items(source: Path) -> list[dict[str, Any]]:
    """Return validated image/label pairs from a SROIE Task 3 directory."""
    image_dir = source / "SROIE_test_images_task_3"
    label_dir = source / "SROIE_test_gt_task_3"
    image_paths = {path.stem: path for path in image_dir.glob("*.jpg")}
    label_paths = {path.stem: path for path in label_dir.glob("*.txt")}

    missing_images = sorted(label_paths.keys() - image_paths.keys())
    missing_labels = sorted(image_paths.keys() - label_paths.keys())
    if missing_images or missing_labels:
        msg = (
            f"Unpaired SROIE files; missing images={missing_images}, "
            f"missing labels={missing_labels}"
        )
        raise ValueError(msg)

    return [
        {
            "id": item_id,
            "image_path": image_paths[item_id],
            "label_path": label_paths[item_id],
            "label": load_sroie_label(label_paths[item_id]),
        }
        for item_id in sorted(image_paths)
    ]


def sample_sroie_items(
    source: Path,
    *,
    sample_size: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Select a reproducible number of SROIE documents."""
    items = paired_sroie_items(source)
    if sample_size < 1:
        msg = "Sample size must be positive."
        raise ValueError(msg)
    if sample_size > len(items):
        msg = f"Requested {sample_size} samples from a pool of {len(items)}."
        raise ValueError(msg)

    randomizer = random.Random(seed)  # noqa: S311 - reproducible evaluation sample
    randomizer.shuffle(items)
    return items[:sample_size]
