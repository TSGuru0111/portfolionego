"""CRUD for rationale_events."""
from __future__ import annotations

from typing import Any

from db.supabase_client import get_supabase

_TABLE = "rationale_events"


def insert_rationale_event(
    sb,
    *,
    client_id,
    event_type: str,
    event_date,
    title: str,
    body: str,
    author_rm_id,
) -> dict[str, Any]:
    """Insert a rationale event row and return it (with id)."""
    if sb is None:
        sb = get_supabase()
    row = {
        "client_id": str(client_id),
        "event_type": event_type,
        "event_date": str(event_date),
        "title": title,
        "rationale_text": body,
        "created_by_rm_id": str(author_rm_id),
    }
    res = sb.table(_TABLE).insert(row).execute()
    return res.data[0]


def update_snapshot_id(sb, event_id: str, snapshot_id: str) -> None:
    if sb is None:
        sb = get_supabase()
    sb.table(_TABLE).update({"snapshot_id": snapshot_id}).eq("id", event_id).execute()


def update_linked_target_id(sb, event_id: str, target_id: str) -> None:
    if sb is None:
        sb = get_supabase()
    sb.table(_TABLE).update({"linked_target_id": target_id}).eq("id", event_id).execute()


def link_transactions_to_event(sb, *, event_id, transaction_ids: list) -> None:
    """Stamp rationale_event_id on a list of transaction rows."""
    if sb is None:
        sb = get_supabase()
    ids = [str(t) for t in transaction_ids]
    sb.table("transactions").update({"rationale_event_id": str(event_id)}).in_("id", ids).execute()


def list_rationale_events(
    sb,
    client_id,
    from_date,
    to_date,
    types: list[str] | None = None,
) -> list[dict[str, Any]]:
    if sb is None:
        sb = get_supabase()
    q = (
        sb.table(_TABLE)
        .select("*")
        .eq("client_id", str(client_id))
        .gte("event_date", str(from_date))
        .lte("event_date", str(to_date))
    )
    if types:
        q = q.in_("event_type", types)
    res = q.order("event_date", desc=False).execute()
    return res.data or []
