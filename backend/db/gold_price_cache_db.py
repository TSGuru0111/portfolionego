"""CRUD for the gold_price_cache support table."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get_latest(purity: str = "999") -> dict[str, Any] | None:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = (
        sb.table("gold_price_cache")
        .select("*")
        .eq("purity", purity)
        .order("fetched_at", desc=True)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def insert(row: dict[str, Any]) -> None:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    sb.table("gold_price_cache").insert(row).execute()
