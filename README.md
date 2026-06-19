# Expense Claim Agent

## Setup

Install Python 3.12, [`uv`](https://docs.astral.sh/uv/),
[`just`](https://just.systems/), Node.js 20+, and
[`pnpm`](https://pnpm.io/), then run:

```bash
cp .env.example .env
just setup
just db-up
just migrate
```

Update `.env` with the required database and provider configuration before
starting the application.

## Prompt configuration

Langfuse prompt management is optional. Set `LANGFUSE_ENABLED=true` to use the
`receipt-key-info-extraction` prompt managed in Langfuse.

If you do not want to set up Langfuse, leave `LANGFUSE_ENABLED=false`. Receipt
extraction will use the local fallback prompt in
`prompts/receipt_extraction.py`.

## Run locally

Start the API:

```bash
just run-local
```

In another terminal, start the Streamlit UI:

```bash
just run-ui
```

## Run with Docker

```bash
just deploy-local
```

Stop the Docker services:

```bash
just stop
```
