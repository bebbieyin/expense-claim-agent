# Langfuse Experiments

The dataset used for this experiment is Scanned Receipt OCR and Information Extraction (SROIE).
This pipeline keeps production extraction in `src/` and uses Langfuse only for
frozen OCR inputs, prompt versions, experiment runs, and scores.

## Structure

- `upload_dataset.py`: shared OCR and Langfuse dataset upload flow.
- `sroie/dataset.py`: SROIE file discovery, sampling, and label normalization.
- `sroie/upload.py`: SROIE-specific dataset configuration and CLI.
- `run_experiment.py`: receipt extraction experiment runner.
- `evaluators.py`: receipt extraction evaluators.

Dataset-specific loaders should remain in their own folders and call the shared
functions in `upload_dataset.py`.

## Prepare the SROIE dataset

The current receipt extraction experiments use the Scanned Receipt OCR and
Information Extraction (SROIE) Task 3 dataset.

Preview OCR-backed records without uploading them:

```bash
uv run python -m experiments.langfuse.sroie.upload \
  --source "/path/to/SROIE/task 3" \
  --seed 21 \
  --sample-size 10 \
  --preview experiments/langfuse/sroie_preview.csv
```

The preview path can be anywhere and must use a `.csv` extension. Preview files
contain `input`, `expected_output`, and `metadata` columns, with each nested
value encoded as JSON.

Add `--live` to create the dataset and upload its items to Langfuse:

```bash
uv run python -m experiments.langfuse.sroie.upload \
  --source "/path/to/SROIE/task 3" \
  --seed 21 \
  --sample-size 10 \
  --live
```

Live uploads require a real OCR provider, such as
`OCR_PROVIDER=azure_ocr`. OCR runs during dataset preparation, and the resulting
text, lines, and tables are frozen in Langfuse. Prompt experiments therefore do
not rerun OCR.

The seed and sample size select a deterministic set of documents. The default
dataset name for the example above is `sroie/seed-21-n-10`. Use
`--dataset-name` to override it.

## Run an experiment

Run prompt experiments on the uploaded dataset:

```bash
uv run python -m experiments.langfuse.run_experiment \
  --seed 21 \
  --sample-size 10 \
  --prompt-version 1 \
  --run-name "receipt-v1"
```

Pass `--dataset-name` when the dataset was uploaded under a custom name. Select
the Langfuse prompt with either `--prompt-version` or `--prompt-label`.
