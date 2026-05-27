"""Pydantic models for allocation_targets rows."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

_HUNDRED = Decimal("100")
_TWO_PLACES = Decimal("0.01")


class _RationaleSubBody(BaseModel):
    event_date: datetime
    title: str = Field(min_length=1, max_length=200)
    rationale_text: str = Field(min_length=1)


class AllocationTargetWrite(BaseModel):
    equity_pct: Decimal = Field(ge=0, le=100)
    debt_pct: Decimal = Field(ge=0, le=100)
    gold_pct: Decimal = Field(ge=0, le=100)
    cash_pct: Decimal = Field(ge=0, le=100)
    alternatives_pct: Decimal = Field(ge=0, le=100)

    equity_band_pct: Decimal = Field(default=Decimal("5"), ge=0, le=100)
    debt_band_pct: Decimal = Field(default=Decimal("5"), ge=0, le=100)
    gold_band_pct: Decimal = Field(default=Decimal("2"), ge=0, le=100)
    cash_band_pct: Decimal = Field(default=Decimal("3"), ge=0, le=100)
    alternatives_band_pct: Decimal = Field(default=Decimal("3"), ge=0, le=100)

    rationale: _RationaleSubBody

    @model_validator(mode="after")
    def _pcts_sum_to_100(self) -> "AllocationTargetWrite":
        total = (
            self.equity_pct + self.debt_pct + self.gold_pct
            + self.cash_pct + self.alternatives_pct
        )
        if total.quantize(_TWO_PLACES) != _HUNDRED:
            raise ValueError(f"Allocation pcts must sum to 100, got {total}")
        return self


class AllocationTarget(BaseModel):
    id: UUID
    client_id: UUID
    effective_from: datetime
    effective_to: datetime | None = None

    equity_pct: Decimal
    debt_pct: Decimal
    gold_pct: Decimal
    cash_pct: Decimal
    alternatives_pct: Decimal

    equity_band_pct: Decimal
    debt_band_pct: Decimal
    gold_band_pct: Decimal
    cash_band_pct: Decimal
    alternatives_band_pct: Decimal

    rationale_event_id: UUID
    created_by_rm_id: UUID
    created_at: datetime
