"""API response schemas."""

from pydantic import BaseModel


class HealthCheck(BaseModel):
    """Health-check response."""

    status: str
