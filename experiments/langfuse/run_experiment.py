"""Run a pinned receipt extraction experiment in Langfuse."""

import argparse
import functools
import os
from dataclasses import dataclass
from threading import Lock
from typing import cast

from langfuse.api import DatasetItem
from langfuse.model import BasePromptClient

from experiments.langfuse.evaluators import evaluate_receipt
from experiments.langfuse.sroie.upload import (
    DEFAULT_SAMPLE_SIZE,
    DEFAULT_SEED,
    default_dataset_name,
)
from src.extraction import extract_receipt_fields
from src.langfuse_client import compile_prompt, get_langfuse_client, get_prompt


@dataclass(frozen=True)
class ExperimentOptions:
    """Controls one Langfuse experiment run."""

    dataset_name: str
    prompt_name: str
    run_name: str
    prompt_label: str | None
    prompt_version: int | None
    description: str = ""
    max_concurrency: int = 2


class ExperimentProgress:
    """Print thread-safe experiment progress."""

    def __init__(self, total: int) -> None:
        """Initialize progress for the total number of dataset items."""
        self.total = total
        self.completed = 0
        self._lock = Lock()

    def report(self, item_id: str, *, succeeded: bool) -> None:
        """Print the completion status for one dataset item."""
        with self._lock:
            self.completed += 1
            status = "completed" if succeeded else "failed"
            print(  # noqa: T201
                f"[{self.completed}/{self.total}] {status}: {item_id}",
                flush=True,
            )


def extraction_task(
    *,
    item: DatasetItem,
    prompt: BasePromptClient,
    progress: ExperimentProgress | None = None,
    **_: object,
) -> dict[str, object]:
    """Run the production receipt extractor for one Langfuse dataset item."""
    try:
        item_input = cast("dict[str, object]", item.input)
        raw_ocr_text = str(item_input["ocr_text"])
        messages = compile_prompt(prompt, OCR_TEXT=raw_ocr_text)
        result = extract_receipt_fields(raw_ocr_text, messages=messages)
    except Exception:
        if progress is not None:
            progress.report(item.id, succeeded=False)
        raise

    if progress is not None:
        progress.report(item.id, succeeded=True)
    return result.model_dump(mode="json")


def run_experiment(
    *,
    options: ExperimentOptions,
) -> None:
    """Fetch a fixed dataset and prompt, then run the experiment."""
    client = get_langfuse_client()
    dataset = client.get_dataset(options.dataset_name)
    prompt = get_prompt(
        options.prompt_name,
        label=options.prompt_label,
        version=options.prompt_version,
    )
    progress = ExperimentProgress(len(dataset.items))
    print(  # noqa: T201
        f"Starting experiment '{options.run_name}' with "
        f"{progress.total} items (concurrency={options.max_concurrency})",
        flush=True,
    )
    task = functools.partial(extraction_task, prompt=prompt, progress=progress)
    dataset.run_experiment(
        name=options.run_name,
        description=options.description,
        task=task,
        evaluators=[evaluate_receipt],
        max_concurrency=options.max_concurrency,
        metadata={
            "prompt_name": prompt.name,
            "prompt_version": prompt.version,
            "prompt_label": options.prompt_label,
            "model_deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        },
    )


def main() -> None:
    """Run a Langfuse experiment from the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--dataset-name")
    parser.add_argument("--prompt-name", default="receipt-extraction")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt-version", type=int)
    prompt_group.add_argument("--prompt-label")
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--max-concurrency", type=int, default=2)
    args = parser.parse_args()

    run_experiment(
        options=ExperimentOptions(
            dataset_name=args.dataset_name
            or default_dataset_name(args.seed, args.sample_size),
            prompt_name=args.prompt_name,
            run_name=args.run_name,
            prompt_label=args.prompt_label,
            prompt_version=args.prompt_version,
            description=args.description,
            max_concurrency=args.max_concurrency,
        )
    )


if __name__ == "__main__":
    main()
