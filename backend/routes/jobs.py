"""Scheduled-job endpoints hit by EasyCron.

All endpoints validate ``JOB_SECRET`` as a query-string parameter so
EasyCron's simple HTTP scheduler can call them without auth headers.
"""
from __future__ import annotations

import os
import time

from fastapi import APIRouter, HTTPException, Query

from db.cache_db import log_job_run
from db.news_db import save_daily_news
from services.error_logger import log_error
from services.news_fetcher import collect_daily_news

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
    """TODO(Day 4): summarise last 7 days via Cohere Command R."""
    _verify_job_secret(secret)
    raise HTTPException(
        status_code=501,
        detail="jobs.weekly_summarise — Day 4",
    )


@router.get("/generate-monthly")
async def generate_monthly(secret: str = Query(...)) -> dict:
    """TODO(Day 6): sequential generate_report for every active client."""
    _verify_job_secret(secret)
    raise HTTPException(
        status_code=501,
        detail="jobs.generate_monthly — Day 6",
    )
