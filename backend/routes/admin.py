"""Admin endpoints — manual triggers, error log, health check.

Protected by ADMIN_SECRET (query parameter).
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query

from db.cache_db import log_job_run
from db.news_db import save_daily_news
from db.supabase_client import get_supabase
from services.error_logger import log_error
from services.news_fetcher import collect_daily_news

router = APIRouter()


def _verify_admin_secret(secret: str) -> None:
    expected = os.getenv("ADMIN_SECRET")
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


@router.get("/health")
async def admin_health() -> dict:
    """Supabase ping — confirms backend can reach the DB."""
    supabase = get_supabase()
    if supabase is None:
        return {"status": "unconfigured", "supabase": False}
    try:
        # Cheapest possible query — count rows in error_logs (always exists).
        result = (
            supabase.table("error_logs")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )
        return {"status": "ok", "supabase": True, "error_count": result.count}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "supabase": False, "detail": str(exc)}


@router.get("/errors")
async def list_errors(
    secret: str = Query(...),
    limit: int = 20,
) -> list[dict]:
    """Last ``limit`` entries from the error_logs table."""
    _verify_admin_secret(secret)
    supabase = get_supabase()
    if supabase is None:
        return []
    res = (
        supabase.table("error_logs")
        .select("id, job, error, context, timestamp")
        .order("timestamp", desc=True)
        .limit(max(1, min(limit, 100)))
        .execute()
    )
    return res.data or []


@router.post("/trigger-news-collection")
async def trigger_news(secret: str = Query(...)) -> dict:
    """Admin convenience endpoint — same path as the EasyCron job."""
    _verify_admin_secret(secret)
    try:
        headlines = await collect_daily_news()
        inserted = await save_daily_news(headlines) if headlines else 0
        await log_job_run(
            "admin_trigger_news",
            status="success",
            records=inserted,
        )
        return {
            "status": "ok",
            "collected": len(headlines),
            "inserted": inserted,
        }
    except Exception as exc:  # noqa: BLE001
        await log_error("admin_trigger_news", exc)
        await log_job_run("admin_trigger_news", status="error")
        raise HTTPException(500, str(exc)) from exc


@router.post("/trigger-weekly-summary")
async def trigger_weekly(secret: str = Query(...)) -> dict:
    _verify_admin_secret(secret)
    raise HTTPException(status_code=501, detail="admin.trigger_weekly — Day 8")


@router.post("/trigger-all-reports")
async def trigger_all_reports(secret: str = Query(...)) -> dict:
    _verify_admin_secret(secret)
    raise HTTPException(
        status_code=501, detail="admin.trigger_all_reports — Day 8"
    )
