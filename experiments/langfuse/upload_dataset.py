"""Build and upload OCR-backed Langfuse datasets."""

import os
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.langfuse_client import get_langfuse_client
from src.ocr import extract_document

DatasetItem = Mapping[str, Any]
DatasetRecord = dict[str, Any]
DatasetItemBuilder = Callable[[DatasetItem], DatasetRecord]


@dataclass(frozen=True)
class DatasetUploadOptions:
    """Control preparation or upload of one OCR dataset."""

    name: str
    description: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    dry_run: bool = True
    sleep_between: float = 0


def build_ocr_dataset_item(
    *,
    image_path: Path,
    expected_output: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> DatasetRecord:
    """Run OCR and build one frozen Langfuse dataset item."""
    ocr_result = extract_document(str(image_path))
    return {
        "input": {
            "ocr_text": ocr_result.full_text,
            "ocr_lines": [line.model_dump(mode="json") for line in ocr_result.lines],
            "tables": [table.model_dump(mode="json") for table in ocr_result.tables],
        },
        "expected_output": dict(expected_output),
        "metadata": {
            **metadata,
            "ocr_provider": ocr_result.provider,
            "ocr_model": ocr_result.model,
        },
    }


def upload_dataset(
    *,
    items: Iterable[DatasetItem],
    build_item: DatasetItemBuilder,
    options: DatasetUploadOptions,
) -> list[DatasetRecord]:
    """Prepare or upload dataset items and return the frozen records."""
    prepared_items = list(items)
    client = None if options.dry_run else get_langfuse_client()
    mode = "Uploading" if client is not None else "Preparing"
    print(  # noqa: T201
        f"{mode} {len(prepared_items)} items for dataset '{options.name}'",
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
            name=options.name,
            description=options.description,
            metadata=dict(options.metadata),
        )

    records = []
    for index, item in enumerate(prepared_items, start=1):
        item_id = str(item["id"])
        print(  # noqa: T201
            f"[{index}/{len(prepared_items)}] Processing OCR: {item_id}",
            flush=True,
        )
        record = build_item(item)
        records.append(record)
        if client is not None:
            client.create_dataset_item(dataset_name=options.name, **record)
        status = "Uploaded" if client is not None else "Prepared"
        print(  # noqa: T201
            f"[{index}/{len(prepared_items)}] {status}: {item_id}",
            flush=True,
        )
        if options.sleep_between:
            time.sleep(options.sleep_between)
    return records
