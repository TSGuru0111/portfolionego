"""Supabase error-log writer.

Wrapped so the main pipeline never crashes if logging itself fails.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from db.supabase_client import get_supabase


async def log_error(
    job: str,
    error: str | Exception,
    context: dict[str, Any] | None = None,
) -> None:
    """Insert an entry into the ``error_logs`` table. Never raises."""
    try:
        supabase = get_supabase()
        if supabase is None:
            print(f"[ERROR LOG — no Supabase client] {job}: {error}")
            return
        supabase.table("error_logs").insert(
            {
                "job": job,
                "error": str(error)[:1000],
                "context": context or {},
                "timestamp": datetime.utcnow().isoformat(),
            }
        ).execute()
    except Exception as inner:  # noqa: BLE001
        # Last-resort logging — Render logs will catch this.
        print(f"[ERROR LOG FAILED] {job}: {error}  |  logger error: {inner}")
