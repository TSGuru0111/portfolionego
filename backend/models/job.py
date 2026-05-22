"""Pydantic models for scheduled job responses."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class JobResponse(BaseModel):
    status: str = Field(..., description='"ok" or "error"')
    job: str
    records: int = 0
    duration_ms: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
