# Expense Claim Agent

Agentic AI system for automating employee expense claim review, extracting
receipt details, validating claims, and routing exceptions to the relevant team.

## Phase 1 features

- Streamlit claim submission, dashboard, and claim detail tabs
- PostgreSQL and SQLAlchemy persistence
- Local receipt uploads
- Mock OCR and structured receipt extraction
- Validation, policy, duplicate, decision, and explanation agents
- Deterministic decisions: `approved`, `needs_review`, or `rejected`
- Full persisted agent review trail
- FastAPI `/health` endpoint retained for service monitoring

## Setup

Install Python 3.12, [`uv`](https://docs.astral.sh/uv/), and
[`just`](https://just.systems/), then run:

```bash
cp .env.example .env
uv sync --all-groups
just db-up
just migrate
```

List available commands:

```bash
just
```

Run the API locally:

```bash
just run-local
```

Run the Streamlit app:

```bash
just run-ui
```

PostgreSQL runs on `localhost:5432` by default. Update the credentials in
`.env` before deploying outside local development.

The mock extractor always returns Restoran ABC, receipt date `2026-06-16`, and
total `MYR 45.90`. Use those values when testing the approval path.

Verify it from another terminal:

```bash
just health
```

Run the checks:

```bash
just check
```

Run with Docker:

```bash
just deploy-local
just logs
just stop
```

The Docker deployment starts PostgreSQL, FastAPI, and Streamlit. PostgreSQL
data and uploaded receipts are stored in named Docker volumes.

## Endpoint

```bash
curl http://127.0.0.1:8000/health
```

Response:

```json
{"status":"ok"}
```
