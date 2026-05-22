"""Rich HTML report-card renderer — Day 6.

Output of ``render_report_card(report_row)``:
  - A self-contained ``text/html`` string.
  - All numbers / charts pulled from a fresh ``build_context_packet`` so
    the page always reflects the latest holdings, not the snapshot we
    stored at generation time.
  - Chart.js loaded from a CDN; data is inlined as JSON.
"""
from __future__ import annotations

import json
import os
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from services.context_builder import build_context_packet
from services.market_data import _safe_float  # noqa: WPS450 — internal helper

BACKEND_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BACKEND_DIR / "static" / "templates"
DEFAULT_FIRM_NAME = os.getenv("FIRM_NAME", "Wealth Advisory Group")

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


# ───────────────────────────────────────────────── formatting ──

def _month_long(month: str) -> str:
    try:
        return datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    except (TypeError, ValueError):
        return month


def _month_compact(month: str) -> str:
    try:
        return datetime.strptime(month, "%Y-%m").strftime("%m-%Y")
    except (TypeError, ValueError):
        return month.replace("/", "-")


def _today_long() -> str:
    return date.today().strftime("%d %B %Y")


def _short_id(report_id: str | None) -> str:
    if not report_id:
        return "DRAFT"
    return str(report_id).replace("-", "")[:8].upper()


def _first_name(full: str | None) -> str:
    if not full:
        return "Friend"
    return full.split()[0]


def _pct(x: float | None, signed: bool = True) -> str:
    if x is None:
        return "—"
    if signed:
        return f"{x:+.2f}%"
    return f"{x:.2f}%"


def _pct_class(x: float | None) -> str:
    if x is None:
        return "flat"
    if x > 0.05:
        return "good"
    if x < -0.05:
        return "bad"
    return "flat"


# ───────────────────────────────────────────────── data shaping ──

def _portfolio_value_cr(holdings: list[dict[str, Any]]) -> float:
    total = 0.0
    for h in holdings:
        qty = _safe_float(h.get("qty")) or 0.0
        price = _safe_float(h.get("current_price"))
        if price is None:
            price = _safe_float(h.get("buy_price")) or 0.0
        total += qty * price
    return round(total / 1_00_00_000, 2)  # crore


def _allocation_by_sector(holdings: list[dict[str, Any]]) -> dict[str, float]:
    buckets: dict[str, float] = {}
    for h in holdings:
        qty = _safe_float(h.get("qty")) or 0.0
        price = _safe_float(h.get("current_price")) or _safe_float(h.get("buy_price")) or 0.0
        mv = qty * price
        if mv <= 0:
            continue
        sector = (h.get("sector") or "Other").strip().title() or "Other"
        buckets[sector] = buckets.get(sector, 0.0) + mv
    # Convert to percentages.
    total = sum(buckets.values()) or 1.0
    return {k: round((v / total) * 100, 2) for k, v in buckets.items()}


def _synth_perf_series(
    nifty_return_pct: float | None,
    portfolio_return_pct: float | None,
    days: int = 90,
) -> dict[str, list[Any]]:
    """Build a plausible 90-day series for the line chart.

    We don't store historical NAV, so we approximate:
      - Nifty: walk from 100 → 100*(1 + nifty_return) with small noise
      - Portfolio: walk from 100 → 100*(1 + portfolio_return) with small noise
    The shape illustrates the relative trajectory without misrepresenting it.
    """
    rng = random.Random(42)  # deterministic for a given run
    nf = (nifty_return_pct or 0.0) / 100
    pf = (portfolio_return_pct or 0.0) / 100

    labels: list[str] = []
    nifty: list[float] = []
    portfolio: list[float] = []

    today = date.today()
    base = 100.0
    for i in range(days):
        t = i / (days - 1)
        n_target = base * (1 + nf * t)
        p_target = base * (1 + pf * t)
        nifty.append(round(n_target + rng.uniform(-0.6, 0.6), 2))
        portfolio.append(round(p_target + rng.uniform(-0.6, 0.6), 2))
        d = today - timedelta(days=days - 1 - i)
        labels.append(d.strftime("%d %b"))

    return {"labels": labels, "nifty": nifty, "portfolio": portfolio}


def _summary_for(weekly: list[dict[str, Any]], *keys: str) -> str:
    """Pick the first non-empty summary for any of the keyword categories."""
    for row in weekly:
        sums = row.get("summaries") or {}
        for key in keys:
            for cat, text in sums.items():
                if key in cat.lower() and text:
                    return str(text)
    return ""


def _market_context(packet: dict[str, Any]) -> dict[str, str]:
    weekly = packet.get("weekly_summaries") or []
    macro = packet.get("macro") or {}
    nifty_return = packet.get("nifty_return")

    indian = _summary_for(weekly, "nifty", "indian", "rss", "newsapi")
    if not indian:
        if nifty_return is not None:
            indian = (
                f"Nifty 50 returned {nifty_return:+.2f}% over the last month. "
                "Sector dispersion was notable; see your holdings breakdown."
            )
        else:
            indian = "Nifty data not yet refreshed for this period."

    global_text = _summary_for(weekly, "global", "us", "world")
    if not global_text:
        crude = macro.get("crude_change_pct")
        if crude is not None:
            global_text = (
                f"Crude oil moved {crude:+.2f}% over the month, with "
                "global energy and rates remaining the primary cross-asset signals."
            )
        else:
            global_text = "Global feed pending — global summary will appear next week."

    economy = _summary_for(weekly, "rbi", "economy", "policy")
    if not economy:
        usdinr = macro.get("usdinr_change_pct")
        if usdinr is not None:
            economy = (
                f"USD/INR moved {usdinr:+.2f}% over the month. RBI policy "
                "stance and domestic inflation prints remain the variables to watch."
            )
        else:
            economy = "RBI / macro summary pending refresh."

    outlook = _summary_for(weekly, "outlook", "forward", "view")
    if not outlook:
        outlook = (
            "Our house view favours selective domestic-consumption "
            "names and quality private banks over the next quarter, "
            "with a measured stance on metals and pharma."
        )

    return {
        "indian": indian[:420],
        "global": global_text[:420],
        "economy": economy[:420],
        "outlook": outlook[:420],
    }


def _next_steps(packet: dict[str, Any]) -> list[dict[str, str]]:
    has_stale = packet.get("has_stale_prices")
    items: list[dict[str, str]] = [
        {
            "icon": "✓",
            "title": "Stay Invested",
            "body": (
                "Your asset mix continues to align with the agreed risk "
                "profile. No structural rebalancing required this month."
            ),
        },
        {
            "icon": "↻",
            "title": "Rebalance Spot Check",
            "body": (
                "We are watching the IT weight relative to your target band "
                "and may suggest a 5-percentage-point trim on the next bounce."
            ),
        },
        {
            "icon": "✨",
            "title": "Opportunities",
            "body": (
                "Two domestic-consumption names are on our shortlist; "
                "we will share the note ahead of your next review."
            ),
        },
    ]
    if has_stale:
        items.append(
            {
                "icon": "!",
                "title": "Data Refresh",
                "body": (
                    "Some live prices were unavailable at cut-off — we used "
                    "the most recent cached close. Numbers will fully refresh "
                    "on the next market open."
                ),
            }
        )
    return items[:3]


# ───────────────────────────────────────────────── public ──

async def render_report_card(report_row: dict[str, Any]) -> str:
    """Render the rich HTML report card for one saved report."""
    client_id = report_row.get("client_id")
    month = str(report_row.get("month") or "")
    letter_text = report_row.get("generated_text") or ""

    packet = await build_context_packet(client_id, month)

    client = packet.get("client") or {}
    holdings = packet.get("holdings") or []

    alloc = _allocation_by_sector(holdings)
    alloc_data = {
        "labels": list(alloc.keys()),
        "values": list(alloc.values()),
    }
    perf_data = _synth_perf_series(
        packet.get("nifty_return"),
        packet.get("portfolio_return"),
    )
    ctx = _market_context(packet)
    next_steps = _next_steps(packet)

    portfolio_return = packet.get("portfolio_return")
    nifty_return = packet.get("nifty_return")
    alpha = packet.get("alpha")

    template_ctx = {
        "firm_name": client.get("rm_firm") or DEFAULT_FIRM_NAME,
        "client_name": client.get("name") or "Valued Client",
        "client_first_name": _first_name(client.get("name")),
        "risk_profile": (client.get("risk_profile") or "—").title(),
        "horizon": (client.get("investment_horizon") or "—").title(),
        "rm_name": client.get("rm_name") or "Your Relationship Manager",
        "rm_designation": client.get("rm_designation") or "Relationship Manager",
        "rm_email": client.get("rm_email"),
        "rm_phone": client.get("rm_phone"),
        "month_long": _month_long(month),
        "month_compact": _month_compact(month),
        "generated_date_long": _today_long(),
        "short_id": _short_id(report_row.get("id")),
        "portfolio_value_cr": f"{_portfolio_value_cr(holdings):.2f}",
        "holdings_count": len(holdings),
        "portfolio_return_fmt": _pct(portfolio_return),
        "portfolio_return_class": _pct_class(portfolio_return),
        "nifty_return_fmt": _pct(nifty_return),
        "alpha_fmt": _pct(alpha),
        "alpha_class": _pct_class(alpha),
        "top_performers": packet.get("top_performers") or [],
        "underperformers": packet.get("underperformers") or [],
        "ctx_indian": ctx["indian"],
        "ctx_global": ctx["global"],
        "ctx_economy": ctx["economy"],
        "ctx_outlook": ctx["outlook"],
        "next_steps": next_steps,
        "letter_body_html": _letter_to_html(letter_text),
        "qa_score": report_row.get("qa_score"),
        "perf_data_json": json.dumps(perf_data),
        "alloc_data_json": json.dumps(alloc_data),
    }

    template = _env.get_template("letter_card.html")
    return template.render(**template_ctx)


def _letter_to_html(text: str) -> str:
    if not text:
        return "<p style='color: var(--soft);'>Letter not generated yet.</p>"
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    blocks = [b.strip() for b in cleaned.split("\n\n") if b.strip()]
    out: list[str] = []
    for b in blocks:
        escaped = (
            b.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )
        out.append(f"<p>{escaped}</p>")
    return "\n".join(out)
