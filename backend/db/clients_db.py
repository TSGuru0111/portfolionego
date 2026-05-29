"""Client + portfolio + transaction CRUD against Supabase.

Tables: ``rms``, ``clients``, ``portfolios``, ``transactions``.
"""
from __future__ import annotations

from typing import Any

from db.supabase_client import get_supabase


def _require_supabase():
    supabase = get_supabase()
    if supabase is None:
        raise RuntimeError(
            "Supabase client not configured. Set SUPABASE_URL + SUPABASE_SERVICE_KEY."
        )
    return supabase


async def get_all_clients(rm_id: str | None = None) -> list[dict[str, Any]]:
    """Return every client row, optionally scoped to one RM."""
    supabase = _require_supabase()
    q = (
        supabase.table("clients")
        .select(
            "id, name, aum_cr, risk_profile, language_pref, "
            "tone_pref, investment_horizon, client_since, next_review_date, "
            "rm_id"
        )
        .order("name")
    )
    if rm_id:
        q = q.eq("rm_id", rm_id)
    res = q.execute()
    return res.data or []


async def get_client(client_id: str) -> dict[str, Any] | None:
    """Return a single client joined with its RM contact info."""
    supabase = _require_supabase()
    res = (
        supabase.table("clients")
        .select(
            "id, name, pan_last4, dob, client_since, aum_cr, "
            "risk_profile, investment_horizon, liquidity_need_pct, "
            "income_need_monthly, tax_bracket, language_pref, tone_pref, "
            "next_review_date, last_meeting_date, last_meeting_notes, "
            "referral_source, rm_phone, rm_email, "
            "rms(id, name, email, firm_name, designation, phone)"
        )
        .eq("id", client_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    row = rows[0]
    rm = row.pop("rms", None) or {}
    row["rm_name"] = rm.get("name")
    row["rm_firm"] = rm.get("firm_name")
    row["rm_designation"] = rm.get("designation")
    # Fallbacks if client-level overrides aren't set.
    row["rm_email"] = row.get("rm_email") or rm.get("email")
    row["rm_phone"] = row.get("rm_phone") or rm.get("phone")
    return row


async def get_portfolio(client_id: str) -> dict[str, Any] | None:
    """Return the latest portfolio row for ``client_id``."""
    supabase = _require_supabase()
    res = (
        supabase.table("portfolios")
        .select(
            "id, client_id, holdings, benchmark, inception_date, "
            "inception_return, xirr, sharpe_ratio, max_drawdown, "
            "fees_this_quarter, fees_since_inception, updated_at"
        )
        .eq("client_id", client_id)
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


async def get_transactions(
    client_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return the most recent ``limit`` transactions for ``client_id``."""
    supabase = _require_supabase()
    res = (
        supabase.table("transactions")
        .select(
            "id, txn_type, ticker, isin, quantity, price, "
            "total_value, txn_date, rationale, executed_by"
        )
        .eq("client_id", client_id)
        .order("txn_date", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def list_all_clients(sb=None) -> list[dict]:
    """Return every client row (id only). Service-role only — used by cron."""
    from db.supabase_client import get_supabase
    if sb is None:
        sb = get_supabase()
    if sb is None:
        return []
    resp = sb.table("clients").select("id").execute()
    return resp.data or []

