"""CRUD for allocation_targets, with an atomic `change` via RPC."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from backend.db.supabase_client import get_supabase

_TABLE = "allocation_targets"


def get_active_target(sb, client_id) -> dict[str, Any] | None:
    """Return the currently active allocation target (effective_to IS NULL)."""
    if sb is None:
        sb = get_supabase()
    res = (
        sb.table(_TABLE)
        .select("*")
        .eq("client_id", str(client_id))
        .is_("effective_to", "null")
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def get_target_history(sb, client_id) -> list[dict[str, Any]]:
    """Return all allocation targets for a client, newest first."""
    if sb is None:
        sb = get_supabase()
    res = (
        sb.table(_TABLE)
        .select("*")
        .eq("client_id", str(client_id))
        .order("effective_from", desc=True)
        .execute()
    )
    return res.data or []


def change_allocation_target(
    sb,
    *,
    client_id,
    risk_profile: str,
    target_pct: dict[str, Decimal],
    band_pct: dict[str, Decimal],
    rationale_event_id,
    set_by,
) -> dict[str, Any]:
    """Atomically stamp prior active row and insert a new active row via RPC.

    Returns the new target row dict (with id).
    """
    if sb is None:
        sb = get_supabase()
    payload = {
        "p_client_id": str(client_id),
        "p_rationale_event_id": str(rationale_event_id),
        "p_rm_id": str(set_by),
        "p_equity_pct": str(target_pct["equity"]),
        "p_debt_pct": str(target_pct["debt"]),
        "p_gold_pct": str(target_pct["gold"]),
        "p_cash_pct": str(target_pct["cash"]),
        "p_alternatives_pct": str(target_pct["alternatives"]),
        "p_equity_band_pct": str(band_pct["equity"]),
        "p_debt_band_pct": str(band_pct["debt"]),
        "p_gold_band_pct": str(band_pct["gold"]),
        "p_cash_band_pct": str(band_pct["cash"]),
        "p_alternatives_band_pct": str(band_pct["alternatives"]),
    }
    res = sb.rpc("change_allocation_target", payload).execute()
    new_id = res.data
    return {"id": str(new_id), "client_id": str(client_id)}
