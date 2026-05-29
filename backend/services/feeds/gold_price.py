"""IBJA daily gold-rate scraper."""
from __future__ import annotations
from datetime import datetime, timezone
import re
import httpx


IBJA_URL = "https://ibja.co/"

_SPAN_IDS = {
    "999": "lblFineGold999",
    "22k": "lblKarat22",
}


def parse_ibja_html(html: str, purity: str) -> float | None:
    """Find the gold-rate value matching the requested purity.

    IBJA now renders rates inside a named span:
      <span id="lblFineGold999">₹ 15646</span>
    Falls back to the legacy <li> list pattern for resilience.
    """
    # Primary: named span pattern (current IBJA layout)
    span_id = _SPAN_IDS.get(purity)
    if span_id:
        m = re.search(
            rf'id="{re.escape(span_id)}"[^>]*>\s*₹?\s*([0-9,]+(?:\.[0-9]+)?)',
            html,
            re.IGNORECASE,
        )
        if m:
            return float(m.group(1).replace(",", ""))

    # Fallback: plain numeric after "Fine Gold (999):" in a <li>
    m = re.search(
        rf"Fine\s+Gold\s*\({re.escape(purity)}\)[^<]*<[^>]+>\s*₹?\s*([0-9,]+(?:\.[0-9]+)?)",
        html,
        re.IGNORECASE,
    )
    if m:
        return float(m.group(1).replace(",", ""))

    return None


def fetch_gold_price_per_gram(purity: str = "999", timeout: float = 30.0) -> dict:
    """Return current per-gram INR price for the requested purity."""
    resp = httpx.get(IBJA_URL, timeout=timeout)
    resp.raise_for_status()
    px = parse_ibja_html(resp.text, purity)
    if px is None:
        raise ValueError(f"could not parse gold rate for purity={purity}")
    return {
        "price_per_gram": px,
        "purity": purity,
        "source": "ibja",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
