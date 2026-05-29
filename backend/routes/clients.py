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


# ─── Phase 2: rationale-events endpoints ─────────────────────────────────────

import logging
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import BaseModel, Field

from db.rationale_events_db import (
    insert_rationale_event,
    link_transactions_to_event,
    list_rationale_events,
)
from services.snapshot_service import persist_snapshot

_logger = logging.getLogger(__name__)

_MANUAL_EVENT_TYPES = {
    "rebalance",
    "cash_deployment",
    "tax_harvest",
    "liquidity_event",
    "external_change",
    "market_commentary",
}


def _current_rm_id(request: Request = None) -> UUID:
    """Demo: return fixed RM UUID (production would decode JWT)."""
    return UUID("00000000-0000-0000-0000-000000000001")


class _ManualEventBody(BaseModel):
    event_type: Literal[
        "rebalance", "cash_deployment", "tax_harvest",
        "liquidity_event", "external_change", "market_commentary",
        "target_change", "onboarding",
    ]
    event_date: date
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)
    transaction_ids: list[UUID] = Field(default_factory=list)


@router.post("/{client_id}/rationale-events")
async def post_manual_event(
    client_id: str,
    body: _ManualEventBody,
    request: Request,
):
    if body.event_type not in _MANUAL_EVENT_TYPES:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=422,
            detail=f"event_type '{body.event_type}' cannot be created manually",
        )
    rm_id = _current_rm_id(request)
    from db.supabase_client import get_supabase
    sb = get_supabase()

    event_row = insert_rationale_event(
        sb,
        client_id=client_id,
        event_type=body.event_type,
        event_date=body.event_date,
        title=body.title,
        body=body.body,
        author_rm_id=str(rm_id),
    )
    event_id = UUID(event_row["id"])

    if body.transaction_ids:
        link_transactions_to_event(
            sb=sb, event_id=event_id, transaction_ids=body.transaction_ids,
        )

    snapshot_id: UUID | None = None
    try:
        snap_row = persist_snapshot(
            sb,
            client_id=client_id,
            trigger="rationale",
            rationale_event_id=str(event_id),
        )
        snapshot_id = UUID(snap_row["id"])
    except Exception as exc:
        _logger.warning("snapshot after manual event failed for client %s: %s", client_id, exc)

    return {"event_id": str(event_id), "snapshot_id": str(snapshot_id) if snapshot_id else None}


@router.get("/{client_id}/rationale-events")
async def get_events(
    client_id: str,
    request: Request,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
):
    from fastapi import HTTPException
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to must be >= from")
    from db.supabase_client import get_supabase
    sb = get_supabase()
    return list_rationale_events(sb, client_id, from_date, to_date)
