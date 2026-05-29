"""Scheduled-job endpoints hit by EasyCron.

All endpoints validate ``JOB_SECRET`` as a query-string parameter so
EasyCron's simple HTTP scheduler can call them without auth headers.
"""
from __future__ import annotations

import os
import time

from fastapi import APIRouter, HTTPException, Query

from datetime import datetime, timezone

from db import clients_db, nav_cache_db, gold_price_cache_db
from db import job_runs_db
from db.cache_db import log_job_run
from db.news_db import save_daily_news
from services import report_generator
from services.context_builder import build_context_packet
from services.error_logger import log_error
from services.feeds.amfi_nav import fetch_nav_rows
from services.feeds.gold_price import fetch_gold_price_per_gram
from services.news_fetcher import collect_daily_news
from services.summariser import weekly_summarisation

router = APIRouter()


def _verify_job_secret(secret: str) -> None:
    expected = os.getenv("JOB_SECRET")
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Invalid job secret")


@router.get("/collect-daily-news")
async def collect_daily_news_job(secret: str = Query(...)) -> dict:
    """Fetch from every enabled feed and persist to ``daily_news``."""
    _verify_job_secret(secret)
    started = time.monotonic()
    try:
        headlines = await collect_daily_news()
        inserted = await save_daily_news(headlines) if headlines else 0
        duration_ms = int((time.monotonic() - started) * 1000)
        await log_job_run(
            "collect_daily_news",
            status="success",
            records=inserted,
            duration_ms=duration_ms,
        )
        return {
            "status": "ok",
            "collected": len(headlines),
            "inserted": inserted,
            "duration_ms": duration_ms,
        }
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - started) * 1000)
        await log_error("collect_daily_news", exc)
        await log_job_run(
            "collect_daily_news",
            status="error",
            records=0,
            duration_ms=duration_ms,
        )
        raise HTTPException(500, f"News collection failed: {exc}") from exc


@router.get("/weekly-summarise")
async def weekly_summarise(secret: str = Query(...)) -> dict:
    """Summarise the last 7 days of ``daily_news`` via Cohere Command R."""
    _verify_job_secret(secret)
    started = time.monotonic()
    try:
        result = await weekly_summarisation()
        duration_ms = int((time.monotonic() - started) * 1000)
        await log_job_run(
            "weekly_summarise",
            status="success" if result.get("status") == "ok" else "skipped",
            records=result.get("categories", 0),
            duration_ms=duration_ms,
        )
        return {**result, "duration_ms": duration_ms}
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - started) * 1000)
        await log_error("weekly_summarise", exc)
        await log_job_run(
            "weekly_summarise",
            status="error",
            records=0,
            duration_ms=duration_ms,
        )
        raise HTTPException(500, f"Weekly summarisation failed: {exc}") from exc


def _previous_month() -> str:
    now = datetime.now(timezone.utc)
    year, month = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    return f"{year:04d}-{month:02d}"


@router.get("/generate-monthly")
async def generate_monthly(
    secret: str = Query(...),
    month: str | None = None,
) -> dict:
    """Sequentially generate the previous month's letter for every client.

    Called by EasyCron on the last day of the month at 06:00 IST. Reports
    are saved to ``reports`` and a summary row is written to ``job_runs``.
    """
    _verify_job_secret(secret)
    started = time.monotonic()
    target_month = month or _previous_month()
    try:
        clients = await clients_db.get_all_clients()
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
                if res.get("status") == "ok":
                    ok += 1
                else:
                    failed += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                await log_error(
                    "generate_monthly.client", exc, {"client_id": cid}
                )

        duration_ms = int((time.monotonic() - started) * 1000)
        await log_job_run(
            "generate_monthly",
            status="success" if failed == 0 else "partial",
            records=ok,
            duration_ms=duration_ms,
        )
        return {
            "status": "ok" if failed == 0 else "partial",
            "month": target_month,
            "total": len(clients),
            "ok": ok,
            "failed": failed,
            "duration_ms": duration_ms,
        }
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - started) * 1000)
        await log_error("generate_monthly", exc)
        await log_job_run(
            "generate_monthly",
            status="error",
            records=0,
            duration_ms=duration_ms,
        )
        raise HTTPException(500, f"Monthly generation failed: {exc}") from exc


@router.get("/refresh-nav-cache")
def refresh_nav_cache(secret: str = Query(...)) -> dict:
    """Download AMFI NAVAll.txt and upsert all scheme NAVs into nav_cache."""
    _verify_job_secret(secret)
    started = time.monotonic()
    try:
        rows = fetch_nav_rows()
        nav_cache_db.upsert(rows)
        duration_ms = int((time.monotonic() - started) * 1000)
        job_runs_db.insert({
            "job_name": "refresh-nav-cache",
            "status": "ok",
            "records": len(rows),
            "duration_ms": duration_ms,
        })
        return {"status": "ok", "records": len(rows), "duration_ms": duration_ms}
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - started) * 1000)
        job_runs_db.insert({
            "job_name": "refresh-nav-cache",
            "status": "error",
            "records": 0,
            "duration_ms": duration_ms,
        })
        raise HTTPException(500, f"NAV refresh failed: {exc}") from exc


@router.get("/refresh-gold-price")
def refresh_gold_price(secret: str = Query(...), purity: str = "999") -> dict:
    """Scrape IBJA for the current gold rate and insert into gold_price_cache."""
    _verify_job_secret(secret)
    started = time.monotonic()
    try:
        row = fetch_gold_price_per_gram(purity=purity)
        gold_price_cache_db.insert(row)
        duration_ms = int((time.monotonic() - started) * 1000)
        job_runs_db.insert({
            "job_name": "refresh-gold-price",
            "status": "ok",
            "records": 1,
            "duration_ms": duration_ms,
        })
        return {"status": "ok", "row": row, "duration_ms": duration_ms}
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.monotonic() - started) * 1000)
        job_runs_db.insert({
            "job_name": "refresh-gold-price",
            "status": "error",
            "records": 0,
            "duration_ms": duration_ms,
        })
        raise HTTPException(500, f"Gold price refresh failed: {exc}") from exc


# ─── Phase 2: monthly snapshots cron ─────────────────────────────────────────
# EasyCron schedule:
#   URL:      https://<host>/jobs/monthly-snapshots?secret=$JOB_SECRET
#   Cron:     30 0 1 * *
#   Timezone: Asia/Kolkata
#   Retries:  3 (EasyCron-side)

from db.clients_db import list_all_clients
from services.snapshot_service import persist_snapshot as _persist_snapshot


@router.post("/monthly-snapshots")
async def monthly_snapshots(secret: str = Query(...)):
    """Iterate every client and write a 'monthly' wealth snapshot."""
    _verify_job_secret(secret)

    from db.supabase_client import get_supabase
    sb = get_supabase()

    clients = list_all_clients(sb)
    ok = 0
    failed = 0

    for c in clients:
        cid = c["id"]
        try:
            _persist_snapshot(sb, client_id=cid, trigger="monthly")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            await log_error(job="cron.monthly-snapshots", error=exc, context={"client_id": cid})

    summary = {"clients_total": len(clients), "ok": ok, "failed": failed}
    await log_job_run(
        job_name="monthly-snapshots",
        status="ok" if failed == 0 else "partial",
        records=ok,
    )
    return summary
