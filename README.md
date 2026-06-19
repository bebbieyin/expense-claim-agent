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
