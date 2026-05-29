"""CRUD for share_tokens."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any
from db.supabase_client import get_supabase

_TABLE = "share_tokens"

def create_share_token(sb, *, client_id: str, expires_in_days: int, rm_id: str) -> dict[str, Any]:
    if sb is None:
        sb = get_supabase()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat()
    row = {"client_id": str(client_id), "expires_at": expires_at, "created_by_rm_id": str(rm_id)}
    res = sb.table(_TABLE).insert(row).execute()
    return res.data[0]

def get_latest_share_token(sb, client_id: str) -> dict[str, Any] | None:
    if sb is None:
        sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    res = (sb.table(_TABLE).select("*").eq("client_id", str(client_id))
           .gt("expires_at", now).order("created_at", desc=True).limit(1).execute())
    return res.data[0] if res.data else None

def resolve_token(sb, token: str) -> dict[str, Any] | None:
    if sb is None:
        sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    res = (sb.table(_TABLE).select("*").eq("token", str(token))
           .gt("expires_at", now).limit(1).execute())
    return res.data[0] if res.data else None
