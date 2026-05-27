"""CRUD for the cash_balances table."""
from __future__ import annotations
from typing import Any
from db.supabase_client import get_supabase


def get_for_client(client_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("cash_balances").select("*").eq("client_id", client_id).execute()
    return res.data or []


def insert(row: dict[str, Any]) -> dict[str, Any]:
    sb = get_supabase()
    if sb is None:
        raise RuntimeError("Supabase unavailable")
    res = sb.table("cash_balances").insert(row).execute()
    return (res.data or [{}])[0]
