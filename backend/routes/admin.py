"""Admin endpoints — manual triggers, error log, health check.

Protected by ADMIN_SECRET (query parameter).
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query

from datetime import datetime, timezone

from db import clients_db
from db.cache_db import log_job_run
from db.news_db import save_daily_news
from db.supabase_client import get_supabase
from services import report_generator
from services.context_builder import build_context_packet
from services.error_logger import log_error
from services.news_fetcher import collect_daily_news
from services.summariser import weekly_summarisation

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
    """Manual run of the weekly news summariser."""
    _verify_admin_secret(secret)
    try:
        result = await weekly_summarisation()
        await log_job_run(
            "admin_trigger_weekly",
            status="success" if result.get("status") == "ok" else "skipped",
            records=result.get("categories", 0),
        )
        return result
    except Exception as exc:  # noqa: BLE001
        await log_error("admin_trigger_weekly", exc)
        await log_job_run("admin_trigger_weekly", status="error")
        raise HTTPException(500, str(exc)) from exc


def _previous_month() -> str:
    """Return last completed month in ``YYYY-MM`` form."""
    now = datetime.now(timezone.utc)
    year, month = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    return f"{year:04d}-{month:02d}"


async def _run_batch_for_all_clients(
    job_name: str,
    month: str | None,
) -> dict:
    """Loop every client → non-streamed generate → save → return summary."""
    target_month = month or _previous_month()
    clients = await clients_db.get_all_clients()
    results: list[dict] = []
    ok = 0
    failed = 0
    for c in clients:
        cid = c.get("id")
        if not cid:
            continue
        try:
            ctx = await build_context_packet(cid, target_month)
            res = await report_generator.generate_report_batch(
                client_id=cid,
                month=target_month,
                context=ctx,
            )
        except Exception as exc:  # noqa: BLE001
            await log_error(job_name, exc, {"client_id": cid})
            res = {
                "client_id": cid,
                "month": target_month,
                "status": "error",
                "detail": str(exc),
            }
        results.append(res)
        if res.get("status") == "ok":
            ok += 1
        else:
            failed += 1

    await log_job_run(
        job_name,
        status="success" if failed == 0 else "partial",
        records=ok,
    )
    return {
        "status": "ok" if failed == 0 else "partial",
        "month": target_month,
        "total": len(results),
        "ok": ok,
        "failed": failed,
        "results": results,
    }


@router.post("/trigger-all-reports")
async def trigger_all_reports(
    secret: str = Query(...),
    month: str | None = None,
) -> dict:
    """Generate a report for every client. Returns per-client status."""
    _verify_admin_secret(secret)
    try:
        return await _run_batch_for_all_clients("admin_trigger_all_reports", month)
    except Exception as exc:  # noqa: BLE001
        await log_error("admin_trigger_all_reports", exc)
        await log_job_run("admin_trigger_all_reports", status="error")
        raise HTTPException(500, str(exc)) from exc


@router.get("/job-runs")
async def list_job_runs(secret: str = Query(...), limit: int = 10) -> list[dict]:
    """Most recent rows from ``job_runs``."""
    _verify_admin_secret(secret)
    supabase = get_supabase()
    if supabase is None:
        return []
    res = (
        supabase.table("job_runs")
        .select("id, job_name, status, records, duration_ms, run_at")
        .order("run_at", desc=True)
        .limit(max(1, min(limit, 100)))
        .execute()
    )
    return res.data or []
