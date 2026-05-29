"""Share token CRUD (protected) + public mirror endpoints."""
from __future__ import annotations
import os
from datetime import date, datetime, timezone, timedelta
from typing import Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator
from db.share_tokens_db import create_share_token, get_latest_share_token, resolve_token
from db.supabase_client import get_supabase
from db.allocation_targets_db import get_active_target
from db.wealth_snapshots_db import get_latest_snapshot, get_snapshots_range
from db.rationale_events_db import list_rationale_events
from routes.clients import get_client_portfolio
from services.drift_service import compute_drift

_FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
_CLASSES = ("equity", "debt", "gold", "cash", "alternatives")

protected_router = APIRouter()
public_router = APIRouter()


def _current_rm_id(request: Request) -> UUID:
    _DEMO_RM = UUID("00000000-0000-0000-0000-000000000001")
    return _DEMO_RM


def _require_token(token: str) -> dict[str, Any]:
    sb = get_supabase()
    row = resolve_token(sb, token)
    if row is None:
        raise HTTPException(status_code=403, detail="link expired or invalid")
    return row


class ShareTokenBody(BaseModel):
    expires_in_days: int

    @field_validator("expires_in_days")
    @classmethod
    def valid_days(cls, v):
        if v not in (7, 30, 90):
            raise ValueError("expires_in_days must be 7, 30, or 90")
        return v


@protected_router.post("/{client_id}/share-token")
async def create_token(client_id: UUID, body: ShareTokenBody, request: Request) -> dict[str, Any]:
    rm_id = _current_rm_id(request)
    sb = get_supabase()
    row = create_share_token(sb, client_id=str(client_id), expires_in_days=body.expires_in_days, rm_id=str(rm_id))
    token_val = row["token"]
    return {
        "token": token_val,
        "expires_at": row["expires_at"],
        "share_url": f"{_FRONTEND_BASE_URL}/share/{token_val}",
    }


@protected_router.get("/{client_id}/share-token")
def get_token(client_id: UUID, request: Request) -> dict[str, Any]:
    rm_id = _current_rm_id(request)
    sb = get_supabase()
    row = get_latest_share_token(sb, str(client_id))
    if row is None:
        raise HTTPException(status_code=404, detail="no active share token")
    token_val = row["token"]
    return {
        "token": token_val,
        "expires_at": row["expires_at"],
        "share_url": f"{_FRONTEND_BASE_URL}/share/{token_val}",
    }


@public_router.get("/{token}/portfolio")
async def share_portfolio(token: str) -> dict[str, Any]:
    row = _require_token(token)
    return await get_client_portfolio(row["client_id"])


@public_router.get("/{token}/drift")
def share_drift(token: str) -> list[dict[str, Any]]:
    row = _require_token(token)
    client_id = row["client_id"]
    sb = get_supabase()
    target = get_active_target(sb, client_id)
    if target is None:
        raise HTTPException(status_code=404, detail="no active allocation target")
    snap = get_latest_snapshot(sb, client_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="no snapshot")
    result = compute_drift(
        sb, client_id,
        target_pct={cls: str(target.get(f"{cls}_pct", 0)) for cls in _CLASSES},
        band_pct={cls: str(target.get(f"{cls}_band_pct", 5)) for cls in _CLASSES},
        actual_pct=snap.get("allocation_pct", {}),
    )
    return result or []


@public_router.get("/{token}/snapshots")
def share_snapshots(token: str) -> list[dict[str, Any]]:
    row = _require_token(token)
    sb = get_supabase()
    to_date = datetime.now(timezone.utc).date()
    from_date = (datetime.now(timezone.utc) - timedelta(days=365)).date()
    return get_snapshots_range(sb, row["client_id"], from_date, to_date)


@public_router.get("/{token}/rationale-events")
def share_events(token: str) -> list[dict[str, Any]]:
    row = _require_token(token)
    sb = get_supabase()
    return list_rationale_events(sb, row["client_id"], date(2020, 1, 1), date(2099, 1, 1))
