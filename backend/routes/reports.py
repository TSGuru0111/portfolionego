"""Report routes.

Day 5: list-reports + export-pdf wired.
Day 6: generate-stream (Cohere streaming + QA + save) is wired in
``report_generator.py`` and switched on here.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from db import reports_db
from models.report import GenerateReportRequest
from services import html_renderer, pdf_exporter, report_generator
from services.context_builder import build_context_packet

router = APIRouter()


class UpdateReportBody(BaseModel):
    generated_text: str = Field(..., min_length=1)


@router.post("/generate-stream")
async def generate_report(request: GenerateReportRequest) -> StreamingResponse:
    """Cohere streaming → letter chunks → QA → save → meta trailer.

    Response body is ``text/plain``; the frontend strips the trailing
    ``[[META]]{...}[[END]]`` block to learn ``report_id`` + ``qa_score``.
    """
    try:
        context = await build_context_packet(request.client_id, request.month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    async def _body():
        async for chunk in report_generator.generate_report_stream(
            client_id=request.client_id,
            month=request.month,
            context=context,
        ):
            yield chunk

    return StreamingResponse(
        _body(),
        media_type="text/plain; charset=utf-8",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
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


@router.get("/{report_id}/view-html")
async def view_html(report_id: str) -> Response:
    """Rich HTML report card — visual dashboard view of one saved report."""
    try:
        row = await reports_db.get_report(report_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    try:
        html = await html_renderer.render_report_card(row)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"HTML render failed: {exc}") from exc

    return Response(content=html, media_type="text/html; charset=utf-8")


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


@router.patch("/{report_id}")
async def patch_report(report_id: str, body: UpdateReportBody) -> dict:
    """Update only the ``generated_text`` column of one report.

    The RM can edit the letter inline; KPIs and charts stay locked.
    """
    try:
        row = await reports_db.get_report(report_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    ok = await reports_db.update_report_text(report_id, body.generated_text)
    if not ok:
        raise HTTPException(status_code=500, detail="Update failed")

    updated = await reports_db.get_report(report_id)
    return updated or row


@router.get("/{report_id}/data")
async def get_report_data(report_id: str) -> dict:
    """JSON shape consumed by the React dashboard.

    Loads the saved report row, rebuilds the context packet, and
    delegates to ``html_renderer.build_report_data`` — same source the
    server-rendered HTML uses.
    """
    try:
        row = await reports_db.get_report(report_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    try:
        packet = await build_context_packet(row["client_id"], row["month"])
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Bridge context_builder's flat keys → build_report_data's expected
    # ``market`` sub-dict. context_builder puts nifty_return / macro at
    # the top level; build_report_data reads market.nifty_mtd_pct.
    packet = {
        **packet,
        "report_id": report_id,
        "letter_text": row.get("generated_text") or "",
        "qa_score": row.get("qa_score"),
        "market": {
            "nifty_mtd_pct": packet.get("nifty_return"),
            "usd_inr_mtd_pct": (packet.get("macro") or {}).get("usdinr_change_pct"),
            "crude_mtd_pct": (packet.get("macro") or {}).get("crude_change_pct"),
        },
    }
    response = html_renderer.build_report_data(packet)
    response["qa_reasons"] = row.get("qa_reasons") or []
    return response
