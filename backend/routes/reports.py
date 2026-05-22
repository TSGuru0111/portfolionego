"""Report routes.

Day 5: list-reports + export-pdf wired.
Day 6: generate-stream (Cohere streaming + QA + save) is wired in
``report_generator.py`` and switched on here.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from db import reports_db
from models.report import GenerateReportRequest
from services import pdf_exporter

router = APIRouter()


@router.post("/generate-stream")
async def generate_report(request: GenerateReportRequest) -> dict:
    """TODO(Day 6): StreamingResponse → Cohere streaming pipeline."""
    raise HTTPException(
        status_code=501,
        detail="reports.generate_report — Day 6",
    )


@router.get("")
async def list_reports(client_id: str = Query(...)) -> list[dict]:
    """Every report saved for ``client_id``, newest first."""
    try:
        return await reports_db.get_reports_for_client(client_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{report_id}")
async def get_report_row(report_id: str) -> dict:
    """Return one report row (English + Hindi text + QA score)."""
    try:
        row = await reports_db.get_report(report_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    return row


@router.get("/{report_id}/export-pdf")
async def export_pdf(report_id: str, lang: str = "english") -> Response:
    """Render the saved report → WeasyPrint PDF → ``application/pdf``."""
    try:
        row = await reports_db.get_report(report_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    text = (
        row.get("hindi_text")
        if lang == "hindi" and row.get("hindi_text")
        else row.get("generated_text")
    )
    if not text:
        raise HTTPException(status_code=409, detail="Report has no text yet")

    try:
        pdf_bytes = await pdf_exporter.generate_pdf_for_report(row, text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"PDF render failed: {exc}") from exc

    filename = f"portfolio-review-{row.get('month', 'report')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
