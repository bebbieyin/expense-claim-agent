"""Run OCR once and upload frozen SROIE inputs to Langfuse."""

import argparse
import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from experiments.langfuse.sroie.dataset import (
    expected_receipt,
    sample_sroie_items,
)
from experiments.langfuse.upload_dataset import (
    DatasetItem,
    DatasetUploadOptions,
    build_ocr_dataset_item,
    upload_dataset,
)

load_dotenv()

DEFAULT_SOURCE = Path("/Users/yin/Documents/projects/SROIE/task 3")
DEFAULT_SEED = 21
DEFAULT_SAMPLE_SIZE = 10
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadOptions:
    """Control one deterministic SROIE dataset upload."""

    source: Path = DEFAULT_SOURCE
    seed: int = DEFAULT_SEED
    sample_size: int = DEFAULT_SAMPLE_SIZE
    dataset_name: str | None = None
    dry_run: bool = True
    sleep_between: float = 0


def default_dataset_name(seed: int, sample_size: int) -> str:
    """Return a dataset name that identifies its deterministic sample."""
    return f"sroie/seed-{seed}-n-{sample_size}"


def build_dataset_item(item: DatasetItem) -> dict[str, Any]:
    """Map one SROIE item to a frozen OCR dataset record."""
    image_path = Path(item["image_path"])
    return build_ocr_dataset_item(
        image_path=image_path,
        expected_output=expected_receipt(item["label"]),
        metadata={
            "document_id": item["id"],
            "document_type": "receipt",
            "dataset_source": str(image_path.parents[1]),
        },
    )


def upload_sample(*, options: UploadOptions) -> list[dict[str, Any]]:
    """Upload one deterministic sample and return the prepared records."""
    items = sample_sroie_items(
        options.source,
        sample_size=options.sample_size,
        seed=options.seed,
    )
    name = options.dataset_name or default_dataset_name(
        options.seed,
        options.sample_size,
    )
    return upload_dataset(
        items=items,
        build_item=build_dataset_item,
        options=DatasetUploadOptions(
            name=name,
            description="Frozen Azure OCR inputs from a deterministic SROIE sample.",
            metadata={
                "seed": options.seed,
                "sample_size": options.sample_size,
                "source": str(options.source),
            },
            dry_run=options.dry_run,
            sleep_between=options.sleep_between,
        ),
    )


def write_preview(path: Path, records: list[dict[str, Any]]) -> None:
    """Write prepared records as CSV."""
    if path.suffix.lower() != ".csv":
        msg = "Preview path must use a .csv extension."
        raise ValueError(msg)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as preview:
        writer = csv.DictWriter(
            preview,
            fieldnames=("input", "expected_output", "metadata"),
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {key: json.dumps(record.get(key)) for key in writer.fieldnames}
            )


def main() -> None:
    """Upload a reproducible SROIE sample to Langfuse."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--dataset-name")
    parser.add_argument("--sleep-between", type=float, default=0)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--preview",
        type=Path,
        help="Write prepared records to a .csv file.",
    )
    args = parser.parse_args()

    records = upload_sample(
        options=UploadOptions(
            source=args.source,
            seed=args.seed,
            sample_size=args.sample_size,
            dataset_name=args.dataset_name,
            dry_run=not args.live,
            sleep_between=args.sleep_between,
        ),
    )
    if args.preview:
        write_preview(args.preview, records)
    mode = "uploaded" if args.live else "prepared"
    logger.info(
        "%s %d records using seed %d.",
        mode.capitalize(),
        len(records),
        args.seed,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
