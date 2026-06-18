"""FastAPI application for the expense claim agent."""

from fastapi import FastAPI

from src.schema import HealthCheck

app = FastAPI(title="Expense Claim Agent API", version="0.1.0")


@app.get("/health")
def health() -> HealthCheck:
    """Return the API health status."""
    return HealthCheck(status="ok")
