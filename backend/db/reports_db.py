"""Reports CRUD against Supabase.

Table: ``reports`` — columns: id, client_id, month, generated_text,
hindi_text, qa_score, pdf_url, created_at.
"""
from __future__ import annotations

from typing import Any

from db.supabase_client import get_supabase


def _require_supabase():
    supabase = get_supabase()
    if supabase is None:
        raise RuntimeError(
            "Supabase client not configured. Set SUPABASE_URL + SUPABASE_SERVICE_KEY."
        )
    return supabase


async def save_report(
    client_id: str,
    month: str,
    generated_text: str,
    qa_score: int | None = None,
    qa_reasons: list[str] | None = None,
    hindi_text: str | None = None,
    pdf_url: str | None = None,
    cadence: str = "monthly",
) -> str | None:
    """Insert one report row. Returns the new row id, or None on failure."""
    supabase = _require_supabase()
    payload: dict[str, Any] = {
        "client_id": client_id,
        "month": month,
        "generated_text": generated_text,
        "qa_score": qa_score,
        "qa_reasons": qa_reasons or [],
        "cadence": cadence,
    }
    if hindi_text is not None:
        payload["hindi_text"] = hindi_text
    if pdf_url is not None:
        payload["pdf_url"] = pdf_url
    res = supabase.table("reports").insert(payload).execute()
    rows = res.data or []
    return rows[0].get("id") if rows else None


async def get_report(report_id: str) -> dict[str, Any] | None:
    """Return one report row or None."""
    supabase = _require_supabase()
    res = (
        supabase.table("reports")
        .select(
            "id, client_id, month, generated_text, hindi_text, "
            "qa_score, qa_reasons, pdf_url, created_at"
        )
        .eq("id", report_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


async def get_reports_for_client(client_id: str) -> list[dict[str, Any]]:
    """Return every report for ``client_id``, newest first."""
    supabase = _require_supabase()
    res = (
        supabase.table("reports")
        .select(
            "id, client_id, month, qa_score, pdf_url, created_at"
        )
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


async def update_report_hindi(report_id: str, hindi_text: str) -> bool:
    """Patch the ``hindi_text`` column for one report."""
    supabase = _require_supabase()
    res = (
        supabase.table("reports")
        .update({"hindi_text": hindi_text})
        .eq("id", report_id)
        .execute()
    )
    return bool(res.data)


async def update_report_text(report_id: str, generated_text: str) -> bool:
    """Patch the ``generated_text`` column for one report.

    Returns True if a row was updated, False otherwise.
    """
    supabase = _require_supabase()
    res = (
        supabase.table("reports")
        .update({"generated_text": generated_text})
        .eq("id", report_id)
        .execute()
    )
    return bool(res.data)
