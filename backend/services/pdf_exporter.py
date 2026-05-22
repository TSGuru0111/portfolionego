"""WeasyPrint + Jinja2 PDF generator — Day 5.

Renders ``static/templates/letter_template.html`` against one saved
report and returns the PDF as bytes. The synchronous WeasyPrint call
runs on a thread so FastAPI handlers can ``await`` it.

WeasyPrint requires Pango/Cairo on the system path; the import is done
lazily so the rest of the service starts even when the system libs are
missing (Render image installs them via the build script).
"""
from __future__ import annotations

import asyncio
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from db import clients_db

BACKEND_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BACKEND_DIR / "static" / "templates"
FONT_DIR = BACKEND_DIR / "static" / "fonts"

DEFAULT_FIRM_NAME = os.getenv("FIRM_NAME", "Wealth Advisory Group")


# ─────────────────────────────────────────────────── helpers ──

def _month_long(month: str) -> str:
    """``2025-10`` → ``October 2025``. Falls back to the input on parse failure."""
    try:
        d = datetime.strptime(month, "%Y-%m")
        return d.strftime("%B %Y")
    except (TypeError, ValueError):
        return month


def _month_compact(month: str) -> str:
    """``2025-10`` → ``10-2025``."""
    try:
        d = datetime.strptime(month, "%Y-%m")
        return d.strftime("%m-%Y")
    except (TypeError, ValueError):
        return month.replace("/", "-")


def _today_long() -> str:
    return date.today().strftime("%d %B %Y")


def _letter_body_to_html(text: str) -> str:
    """Convert plain letter text (paragraphs separated by blank lines) to
    ``<p>`` blocks. Trims edge whitespace and escapes nothing — the
    Jinja2 template renders this via ``|safe`` after we've sanitised.
    """
    if not text:
        return ""
    # Normalise newlines.
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    blocks = [b.strip() for b in cleaned.split("\n\n") if b.strip()]
    # Escape HTML-special chars per block, then convert single newlines
    # within a block to <br/> (used for signature blocks).
    out_parts: list[str] = []
    for b in blocks:
        escaped = (
            b.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )
        out_parts.append(f"<p>{escaped}</p>")
    return "\n".join(out_parts)


def _short_id(report_id: str | None) -> str:
    if not report_id:
        return "DRAFT"
    return str(report_id).replace("-", "")[:8].upper()


# ─────────────────────────────────────────────────── rendering ──

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _render_html(ctx: dict[str, Any]) -> str:
    template = _env.get_template("letter_template.html")
    return template.render(**ctx)


def _render_pdf_blocking(html: str) -> bytes:
    """Lazy WeasyPrint import — only loaded when PDFs are actually rendered."""
    from weasyprint import HTML  # type: ignore
    from weasyprint.text.fonts import FontConfiguration  # type: ignore

    font_config = FontConfiguration()
    return HTML(string=html, base_url=str(BACKEND_DIR)).write_pdf(
        font_config=font_config
    )


# ─────────────────────────────────────────────────── public API ──

async def generate_pdf_for_report(
    report_row: dict[str, Any],
    letter_text: str,
    firm_name: str | None = None,
) -> bytes:
    """Render one report row → PDF bytes.

    Looks up the client + RM contact info from Supabase so the
    letterhead and signature are populated.
    """
    client_id = report_row.get("client_id")
    month = str(report_row.get("month") or "")

    client: dict[str, Any] = {}
    if client_id:
        try:
            client = await clients_db.get_client(client_id) or {}
        except RuntimeError:
            client = {}

    ctx: dict[str, Any] = {
        "firm_name": firm_name or client.get("rm_firm") or DEFAULT_FIRM_NAME,
        "font_dir": str(FONT_DIR),
        "client_name": client.get("name") or "Valued Client",
        "client_pan_last4": client.get("pan_last4"),
        "month_long": _month_long(month),
        "month_compact": _month_compact(month),
        "generated_date_long": _today_long(),
        "short_id": _short_id(report_row.get("id")),
        "rm_name": client.get("rm_name") or "Your Relationship Manager",
        "rm_designation": client.get("rm_designation") or "Relationship Manager",
        "rm_email": client.get("rm_email"),
        "rm_phone": client.get("rm_phone"),
        "letter_body_html": _letter_body_to_html(letter_text),
    }

    html = _render_html(ctx)
    return await asyncio.to_thread(_render_pdf_blocking, html)


async def generate_pdf(report_id: str, letter_text: str) -> bytes:
    """Convenience wrapper for tests — looks the report up by id."""
    from db import reports_db

    row = await reports_db.get_report(report_id)
    if not row:
        raise ValueError(f"Report {report_id!r} not found")
    return await generate_pdf_for_report(row, letter_text)
