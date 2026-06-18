# Expense Claim Agent

Agentic AI system for automating employee expense claim review, extracting
receipt details, validating claims, and routing exceptions to the relevant team.

## Project baseline

The repository currently provides the application and engineering scaffold:

- FastAPI service with a `/health` endpoint
- `uv` dependency management
- Pytest, Ruff, and Bandit checks
- Docker and Docker Compose support
- `just` commands for common development tasks
- Commitlint and semantic-release configuration
- GitHub Actions for pull-request and release automation

Expense extraction, policy validation, and exception-routing features will be
added on top of this baseline.

## Setup

Install Python 3.12, [`uv`](https://docs.astral.sh/uv/), and
[`just`](https://just.systems/), then run:

```bash
cp .env.example .env
uv sync --all-groups
```

List available commands:

```bash
just
```

Run the API locally:

```bash
just run-local
```

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

## Endpoint

```bash
curl http://127.0.0.1:8000/health
```

Response:

```json
{"status":"ok"}
```
