"""Tests for the FastAPI application."""

from fastapi import status
from fastapi.testclient import TestClient

from src.main import app


def test_health_returns_ok() -> None:
    """Health endpoint returns a successful status."""
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
