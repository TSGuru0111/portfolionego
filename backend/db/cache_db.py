"""Price cache + job-run CRUD.

Tables: ``price_cache``, ``job_runs``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db.supabase_client import get_supabase


async def get_cached_price(ticker: str) -> dict[str, Any] | None:
    """Return the last cached row for ``ticker`` or ``None`` if unknown."""
    supabase = get_supabase()
    if supabase is None:
        return None
    res = (
        supabase.table("price_cache")
        .select("ticker, price, change_pct, fetched_at")
        .eq("ticker", ticker)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


async def save_price_cache(
    ticker: str,
    price: float,
    change_pct: float,
) -> None:
    """Upsert the latest price for ``ticker``."""
    supabase = get_supabase()
    if supabase is None:
        return
    supabase.table("price_cache").upsert(
        {
            "ticker": ticker,
            "price": float(price),
            "change_pct": float(change_pct),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="ticker",
    ).execute()


async def log_job_run(
    job_name: str,
    status: str,
    records: int = 0,
    duration_ms: int | None = None,
) -> None:
    """Insert a row into ``job_runs``. Never raises."""
    supabase = get_supabase()
    if supabase is None:
        return
    try:
        supabase.table("job_runs").insert(
            {
                "job_name": job_name,
                "status": status,
                "records": int(records),
                "duration_ms": int(duration_ms) if duration_ms is not None else None,
                "run_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001
        print(f"[job_runs insert failed] {job_name}: {exc}")
