# SROIE Langfuse Experiments

This pipeline keeps production extraction in `src/` and uses Langfuse only for
frozen datasets, prompt versions, experiment runs, and scores.

Preview OCR-backed dataset records before uploading:

```bash
uv run python -m experiments.langfuse.upload_sroie_dataset \
  --seed 42 \
  --sample-size 10 \
  --preview /tmp/sroie-preview.jsonl
```

Add `--live` to upload. OCR is performed during upload and the resulting text,
lines, and raw response are frozen in Langfuse. Prompt experiments therefore
do not pay for or rerun OCR. The same seed and sample size always select the
same documents. The default dataset name is
`sroie/receipt-extraction/seed-42-n-10`.

Run prompt experiments on the uploaded dataset:

```bash
uv run python -m experiments.langfuse.run_experiment \
  --seed 42 \
  --sample-size 10 \
  --prompt-version 1 \
  --run-name "receipt-v1"
```
