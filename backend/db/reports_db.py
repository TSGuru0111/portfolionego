"""Reports CRUD — stub for Day 1-2."""
from __future__ import annotations

from typing import Any


async def save_report(
    client_id: str,
    month: str,
    generated_text: str,
    qa_score: int | None = None,
) -> str:
    raise NotImplementedError("reports_db.save_report — Day 5")


async def get_report(report_id: str) -> dict[str, Any] | None:
    raise NotImplementedError("reports_db.get_report — Day 5")


async def get_reports_for_client(client_id: str) -> list[dict[str, Any]]:
    raise NotImplementedError("reports_db.get_reports_for_client — Day 5")
