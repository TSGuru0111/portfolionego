"""Pydantic models for wealth_snapshots rows."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Trigger = Literal["report", "rationale", "monthly"]


class WealthSnapshotRow(BaseModel):
    id: UUID
    client_id: UUID
    as_of: datetime
    trigger: Trigger
    rationale_event_id: UUID | None = None
    report_id: UUID | None = None

    net_worth: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    total_unrealised_gain: Decimal
    allocation_pct: dict[str, Decimal]

    snapshot_json: dict

    has_stale_values: bool = False
    stale_sources: list[str] = Field(default_factory=list)

    created_at: datetime
