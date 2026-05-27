"""Synchronous CRUD for the job_runs table.

Used by sync job endpoints that cannot await the async log_job_run helper
in cache_db. Writes a single status row per job invocation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from db.supabase_client import get_supabase


def insert(row: dict[str, Any]) -> None:
    """Insert a job-run row. Never raises — failures are printed to stderr."""
    supabase = get_supabase()
    if supabase is None:
        print(f"[job_runs insert — no Supabase] {row}")
        return
    try:
        payload = {**row, "run_at": datetime.now(timezone.utc).isoformat()}
        supabase.table("job_runs").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        print(f"[job_runs insert failed] {row.get('job_name')}: {exc}")
