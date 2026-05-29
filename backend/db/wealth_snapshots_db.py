"""CRUD for wealth_snapshots."""
from __future__ import annotations

from typing import Any

from db.supabase_client import get_supabase

_TABLE = "wealth_snapshots"


def get_latest_snapshot(sb, client_id: str) -> dict[str, Any] | None:
    """Return the most recent snapshot row for a client, or None."""
    if sb is None:
        sb = get_supabase()
    res = (
        sb.table(_TABLE)
        .select("*")
        .eq("client_id", str(client_id))
        .order("as_of", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def get_snapshots_range(
    sb, client_id: str, from_date, to_date
) -> list[dict[str, Any]]:
    """Return snapshots within a date range."""
    if sb is None:
        sb = get_supabase()
    res = (
        sb.table(_TABLE)
        .select("*")
        .eq("client_id", str(client_id))
        .gte("as_of", str(from_date))
        .lte("as_of", str(to_date))
        .order("as_of", desc=False)
        .execute()
    )
    return res.data or []


def insert_snapshot(sb, row: dict[str, Any]) -> str:
    """Insert a snapshot row and return its id."""
    if sb is None:
        sb = get_supabase()
    res = sb.table(_TABLE).insert(row).select("id").single().execute()
    return res.data["id"]
