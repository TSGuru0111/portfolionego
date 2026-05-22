"""Client + portfolio routes.

GET /clients              → roster (any logged-in RM sees all for the demo)
GET /clients/{id}/portfolio → client profile + holdings with live prices
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from db import clients_db
from services.market_data import (
    compute_portfolio_return,
    enrich_holdings_with_prices,
    fetch_nifty_return,
)

router = APIRouter()


@router.get("")
async def list_clients() -> list[dict[str, Any]]:
    """All clients ordered by name. Backend RLS will narrow by RM in prod."""
    try:
        return await clients_db.get_all_clients()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{client_id}/portfolio")
async def get_client_portfolio(client_id: str) -> dict[str, Any]:
    """Client profile + holdings enriched with live yfinance prices.

    Response shape (subset):
        client:              { id, name, aum_cr, risk_profile, ... }
        holdings:            [ { ticker, qty, buy_price, current_price,
                                 change_pct, source, ... } ]
        portfolio_return:    float | None    # weighted % vs buy_price
        nifty_return:        float | None    # 1-month Nifty return %
        has_stale_prices:    bool
        stale_tickers:       list[str]
    """
    try:
        client = await clients_db.get_client(client_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    portfolio = await clients_db.get_portfolio(client_id)
    holdings = (portfolio or {}).get("holdings") or []

    enriched, stale = await enrich_holdings_with_prices(holdings)
    portfolio_return = compute_portfolio_return(enriched)
    nifty_return = await fetch_nifty_return("1mo")

    return {
        "client": client,
        "portfolio": {
            **(portfolio or {}),
            "holdings": enriched,
        },
        "holdings": enriched,
        "portfolio_return": portfolio_return,
        "nifty_return": nifty_return,
        "has_stale_prices": bool(stale),
        "stale_tickers": stale,
    }
