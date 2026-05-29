"""Pydantic models for report endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GenerateReportRequest(BaseModel):
    client_id: str
    month: str = Field(..., description='Month identifier, e.g. "2026-04"')
    cadence: Literal["weekly", "monthly", "quarterly"] = "monthly"


class ReportResponse(BaseModel):
    id: str
    client_id: str
    month: str
    qa_score: int | None = None
    has_hindi: bool = False
    created_at: datetime


class ReportSummary(BaseModel):
    """Lightweight summary for listing past reports."""

    id: str
    month: str
    qa_score: int | None = None
    created_at: datetime
