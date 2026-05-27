"""Pydantic models for rationale_events rows."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

EventType = Literal[
    "target_change", "rebalance", "cash_deployment", "tax_harvest",
    "liquidity_event", "external_change", "market_commentary", "onboarding",
]

EVENT_TYPES: tuple[str, ...] = (
    "target_change", "rebalance", "cash_deployment", "tax_harvest",
    "liquidity_event", "external_change", "market_commentary", "onboarding",
)


class RationaleEventWrite(BaseModel):
    """Request body for POST /clients/{id}/rationale-events."""

    event_date: datetime
    event_type: EventType
    title: str = Field(min_length=1, max_length=200)
    rationale_text: str = Field(min_length=1)
    link_transaction_ids: list[UUID] = Field(default_factory=list)


class RationaleEvent(BaseModel):
    """Row as stored in the rationale_events table."""

    id: UUID
    client_id: UUID
    event_date: datetime
    event_type: EventType
    title: str
    rationale_text: str
    snapshot_id: UUID | None = None
    linked_target_id: UUID | None = None
    created_by_rm_id: UUID
    created_at: datetime
