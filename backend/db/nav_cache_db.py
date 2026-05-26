"""CRUD for the nav_cache support table (single row per scheme_code)."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get(scheme_code: str) -> dict[str, Any] | None:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("nav_cache").select("*").eq("scheme_code", scheme_code).limit(1).execute()
    return (res.data or [None])[0]


def upsert(rows: list[dict[str, Any]]) -> None:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    sb.table("nav_cache").upsert(rows, on_conflict="scheme_code").execute()
