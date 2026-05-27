"""CRUD for the market_yields support table (G-Sec yield curve)."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get_curve(curve: str = "gsec") -> list[dict[str, Any]]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = (
        sb.table("market_yields")
        .select("*")
        .eq("curve", curve)
        .order("tenor_years")
        .execute()
    )
    return res.data or []


def upsert(rows: list[dict[str, Any]]) -> None:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    sb.table("market_yields").upsert(rows, on_conflict="curve,tenor_years").execute()
