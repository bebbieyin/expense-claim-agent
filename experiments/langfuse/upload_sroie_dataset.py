"""Run OCR once and upload frozen SROIE inputs to Langfuse."""

import argparse
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from experiments.langfuse.sroie import expected_receipt, sample_sroie_items
from src.langfuse_client import get_langfuse_client
from src.ocr import extract_document

load_dotenv()

DEFAULT_SOURCE = Path("/Users/yin/Documents/projects/SROIE/task 3")
DEFAULT_SEED = 42
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


def build_dataset_item(item: dict[str, Any]) -> dict[str, Any]:
    """Run OCR and build one frozen Langfuse dataset item."""
    ocr_result = extract_document(str(item["image_path"]))
    return {
        "input": {
            "ocr_text": ocr_result.full_text,
            "ocr_lines": [line.model_dump(mode="json") for line in ocr_result.lines],
            "tables": [table.model_dump(mode="json") for table in ocr_result.tables],
        },
        "expected_output": expected_receipt(item["label"]),
        "metadata": {
            "document_id": item["id"],
            "document_type": "receipt",
            "dataset_source": "SROIE Task 3",
            "ocr_provider": ocr_result.provider,
            "ocr_model": ocr_result.model,
        },
    }


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
    client = None if options.dry_run else get_langfuse_client()
    mode = "Uploading" if client is not None else "Preparing"
    print(  # noqa: T201
        f"{mode} {len(items)} items for dataset '{name}'",
        flush=True,
    )
    if client is not None and os.getenv("OCR_PROVIDER", "mock") == "mock":
        msg = (
            "Live dataset upload requires a real OCR provider. "
            "Set OCR_PROVIDER=azure_ocr."
        )
        raise ValueError(msg)
    if client is not None:
        client.create_dataset(
            name=name,
            description="Frozen Azure OCR inputs from a deterministic SROIE sample.",
            metadata={
                "seed": options.seed,
                "sample_size": options.sample_size,
                "source": "SROIE Task 3",
            },
        )

    records = []
    for index, item in enumerate(items, start=1):
        print(  # noqa: T201
            f"[{index}/{len(items)}] Processing OCR: {item['id']}",
            flush=True,
        )
        record = build_dataset_item(item)
        records.append(record)
        if client is not None:
            client.create_dataset_item(dataset_name=name, **record)
        status = "Uploaded" if client is not None else "Prepared"
        print(  # noqa: T201
            f"[{index}/{len(items)}] {status}: {item['id']}",
            flush=True,
        )
        if options.sleep_between:
            time.sleep(options.sleep_between)
    return records


def main() -> None:
    """Upload a reproducible SROIE sample to Langfuse."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--dataset-name")
    parser.add_argument("--sleep-between", type=float, default=0)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--preview", type=Path)
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
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        with args.preview.open("w", encoding="utf-8") as preview:
            for record in records:
                preview.write(f"{json.dumps(record)}\n")
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
