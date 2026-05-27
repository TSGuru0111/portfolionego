"""Pydantic shapes for the wealth aggregator output.

Phase 1 only ships the four bucket models the aggregator builds. Per-asset
shapes (MutualFund, Bond, etc.) are deferred to Phase 3 when an API surface
needs them. The aggregator reads DB rows as dicts.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


AssetClass = Literal[
    "mutual_funds", "bonds", "gold", "cash", "fixed_deposits"
]


class AssetBucket(BaseModel):
    """One asset class for one client (MFs, bonds, gold, cash, FDs)."""
    asset_class: AssetClass
    holdings: list[dict[str, Any]] = Field(default_factory=list)
    current_value: float = 0.0
    invested_value: float = 0.0
    unrealised_gain: float = 0.0


class InsuranceBucket(BaseModel):
    """Insurance is special — cover and surrender are tracked separately."""
    policies: list[dict[str, Any]] = Field(default_factory=list)
    total_cover: float = 0.0
    total_surrender_value: float = 0.0


class LiabilityBucket(BaseModel):
    """All loans for one client."""
    loans: list[dict[str, Any]] = Field(default_factory=list)
    total_outstanding: float = 0.0


class WealthSnapshot(BaseModel):
    """Full multi-asset snapshot for one client at a point in time."""
    client_id: str
    as_of: str  # ISO date string
    mutual_funds: AssetBucket
    bonds: AssetBucket
    gold: AssetBucket
    cash: AssetBucket
    fixed_deposits: AssetBucket
    insurance: InsuranceBucket
    liabilities: LiabilityBucket
    net_worth: float
    asset_allocation: dict[str, float] = Field(default_factory=dict)
    has_stale_values: bool = False
    stale_sources: list[str] = Field(default_factory=list)
