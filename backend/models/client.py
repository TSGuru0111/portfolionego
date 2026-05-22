"""Pydantic models for client + portfolio responses."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

PriceSource = Literal["live", "cached", "unavailable"]


class HoldingItem(BaseModel):
    ticker: str
    company_name: str
    isin: str | None = None
    qty: float
    buy_price: float
    sector: str
    asset_class: str = "equity"
    buy_date: date | None = None

    # Filled at runtime by services/market_data.py
    current_price: float | None = None
    change_pct: float | None = None
    source: PriceSource = "live"


class ClientResponse(BaseModel):
    id: str
    name: str
    aum_cr: float
    risk_profile: str
    language_pref: str = "english"
    tone_pref: str = "warm"
    investment_horizon: str | None = None
    client_since: date | None = None
    next_review_date: date | None = None
    last_meeting_notes: str | None = None
    rm_name: str
    rm_email: str | None = None
    rm_phone: str | None = None


class PortfolioResponse(BaseModel):
    client_id: str
    benchmark: str = "NIFTY50"
    holdings: list[HoldingItem] = Field(default_factory=list)
    portfolio_return: float | None = None
    benchmark_return: float | None = None
    alpha: float | None = None
    total_value: float | None = None
    has_stale_prices: bool = False
    stale_tickers: list[str] = Field(default_factory=list)
