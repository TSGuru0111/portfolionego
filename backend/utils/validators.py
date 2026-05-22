"""Context-packet validation used before any LLM call."""
from __future__ import annotations

from typing import Any


def validate_context(context: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate context packet before sending to LLM.

    Returns (is_valid, reason).
    """
    if not context.get("client_name"):
        return False, "Client name is missing"

    holdings = context.get("holdings") or []
    if not holdings:
        return False, "Portfolio has no holdings — cannot generate report"

    if context.get("portfolio_return") is None:
        return False, "Could not compute portfolio return — check price data"

    if context.get("nifty_return") is None:
        return False, "Nifty benchmark data unavailable — try again later"

    unavailable = [
        h.get("ticker", "?")
        for h in holdings
        if h.get("source") == "unavailable"
    ]
    if len(unavailable) > len(holdings) * 0.5:
        return (
            False,
            f"Price data unavailable for too many holdings: {unavailable}",
        )

    return True, "OK"
