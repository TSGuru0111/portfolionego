"""IBJA daily gold-rate scraper."""
from __future__ import annotations
from datetime import datetime, timezone
import re
import httpx


IBJA_URL = "https://ibja.co/"

_LABELS = {
    "999": ("Fine Gold", "999"),
    "22k": ("22 Karat", "916"),
}


def parse_ibja_html(html: str, purity: str) -> float | None:
    """Find the gold-rate cell matching the requested purity.

    The IBJA page renders rates inside a `<table>` with a row label like
    'Fine Gold (999)' followed by a numeric `<td>`. Matching is permissive
    so the parser tolerates whitespace and label variants.
    """
    label, code = _LABELS.get(purity, (None, None))
    if not label:
        return None
    pattern = re.compile(
        rf"{re.escape(label)}[^<]*\(?{code}\)?[^<]*</td>\s*<td[^>]*>\s*([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    )
    m = pattern.search(html)
    if not m:
        return None
    return float(m.group(1))


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
