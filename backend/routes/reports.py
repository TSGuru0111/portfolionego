"""Report generation + export routes — wired on Day 6."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.report import GenerateReportRequest

router = APIRouter()


@router.post("/generate-stream")
async def generate_report(request: GenerateReportRequest) -> dict:
    """TODO(Day 6): StreamingResponse → Cohere streaming pipeline."""
    raise HTTPException(
        status_code=501,
        detail="reports.generate_report — Day 6",
    )


@router.get("")
async def list_reports(client_id: str) -> list[dict]:
    """TODO(Day 5-6): list saved reports for a client."""
    raise HTTPException(status_code=501, detail="reports.list_reports — Day 5")


@router.get("/{report_id}/export-pdf")
async def export_pdf(report_id: str, lang: str = "english") -> dict:
    """TODO(Day 5-6): render PDF via WeasyPrint."""
    raise HTTPException(status_code=501, detail="reports.export_pdf — Day 5")
