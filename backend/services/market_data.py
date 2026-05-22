"""Market data via yfinance with Supabase price_cache fallback.

All public functions are safe to ``await`` from FastAPI handlers — the
yfinance calls themselves are blocking and run on the default thread
executor via ``asyncio.to_thread``.

Ticker convention: Indian NSE tickers must carry the ``.NS`` suffix for
yfinance (e.g. ``TCS`` → ``TCS.NS``, ``RELIANCE`` → ``RELIANCE.NS``).
BSE tickers use ``.BO``.
"""
from __future__ import annotations

import asyncio
import math
from typing import Any

import yfinance as yf

from db.cache_db import get_cached_price, save_price_cache
from services.error_logger import log_error

NIFTY_SYMBOL = "^NSEI"
USDINR_SYMBOL = "INR=X"
CRUDE_SYMBOL = "CL=F"

DEFAULT_EXCHANGE_SUFFIX = ".NS"


def _normalise_ticker(ticker: str) -> str:
    """Append ``.NS`` if no exchange suffix is present."""
    t = ticker.strip().upper()
    if "." not in t:
        t = f"{t}{DEFAULT_EXCHANGE_SUFFIX}"
    return t


def _safe_float(x: Any) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _fetch_price_blocking(ticker: str) -> dict[str, Any] | None:
    """yfinance call wrapped to swallow exceptions and normalise output."""
    symbol = _normalise_ticker(ticker)
    try:
        tkr = yf.Ticker(symbol)
        hist = tkr.history(period="2d", auto_adjust=False)
        if hist is None or hist.empty:
            return None
        closes = hist["Close"].dropna().tolist()
        if not closes:
            return None
        last = _safe_float(closes[-1])
        prev = _safe_float(closes[-2]) if len(closes) >= 2 else None
        if last is None:
            return None
        change_pct = 0.0
        if prev and prev > 0:
            change_pct = ((last - prev) / prev) * 100.0
        return {
            "ticker": ticker,
            "price": last,
            "change_pct": change_pct,
            "source": "live",
        }
    except Exception:  # noqa: BLE001 — yfinance throws a zoo of exceptions
        return None


async def fetch_stock_price_safe(ticker: str) -> dict[str, Any]:
    """Live yfinance → cached fallback → unavailable.

    Always returns a dict with at least ``ticker`` and ``source``;
    ``price``/``change_pct`` may be ``None`` if both sources fail.
    """
    live = await asyncio.to_thread(_fetch_price_blocking, ticker)
    if live and live.get("price") is not None:
        # Best-effort cache write — never block return on cache failure.
        try:
            await save_price_cache(
                ticker, live["price"], live.get("change_pct") or 0.0
            )
        except Exception as exc:  # noqa: BLE001
            await log_error("price_cache_write", exc, {"ticker": ticker})
        return live

    cached = await get_cached_price(ticker)
    if cached and cached.get("price") is not None:
        return {
            "ticker": ticker,
            "price": _safe_float(cached["price"]),
            "change_pct": _safe_float(cached.get("change_pct")) or 0.0,
            "source": "cached",
            "fetched_at": cached.get("fetched_at"),
        }

    return {
        "ticker": ticker,
        "price": None,
        "change_pct": None,
        "source": "unavailable",
    }


def _period_return_blocking(symbol: str, period: str) -> float | None:
    try:
        tkr = yf.Ticker(symbol)
        hist = tkr.history(period=period, auto_adjust=False)
        if hist is None or hist.empty:
            return None
        closes = hist["Close"].dropna().tolist()
        if len(closes) < 2:
            return None
        first = _safe_float(closes[0])
        last = _safe_float(closes[-1])
        if not first or not last or first <= 0:
            return None
        return ((last - first) / first) * 100.0
    except Exception:  # noqa: BLE001
        return None


async def fetch_nifty_return(period: str = "1mo") -> float | None:
    """Nifty 50 return % over ``period`` (e.g. ``1mo``, ``3mo``, ``1y``)."""
    return await asyncio.to_thread(_period_return_blocking, NIFTY_SYMBOL, period)


async def fetch_macro_data() -> dict[str, Any]:
    """USD/INR and crude oil 1-month change %."""
    usdinr, crude = await asyncio.gather(
        asyncio.to_thread(_period_return_blocking, USDINR_SYMBOL, "1mo"),
        asyncio.to_thread(_period_return_blocking, CRUDE_SYMBOL, "1mo"),
    )
    return {
        "usdinr_change_pct": usdinr,
        "crude_change_pct": crude,
    }


# ────────────────────────────────────────── portfolio analytics ──

def _holding_return_pct(holding: dict[str, Any]) -> float | None:
    """Return % from buy_price → current_price for one holding row."""
    buy = _safe_float(holding.get("buy_price"))
    curr = _safe_float(holding.get("current_price"))
    if not buy or buy <= 0 or curr is None:
        return None
    return ((curr - buy) / buy) * 100.0


def _holding_market_value(holding: dict[str, Any]) -> float:
    qty = _safe_float(holding.get("qty")) or 0.0
    curr = _safe_float(holding.get("current_price"))
    buy = _safe_float(holding.get("buy_price")) or 0.0
    price = curr if curr is not None else buy
    return qty * price


def compute_portfolio_return(holdings: list[dict[str, Any]]) -> float | None:
    """Market-value-weighted average return across all priced holdings."""
    weighted_sum = 0.0
    total_value = 0.0
    for h in holdings:
        ret = _holding_return_pct(h)
        if ret is None:
            continue
        mv = _holding_market_value(h)
        if mv <= 0:
            continue
        weighted_sum += ret * mv
        total_value += mv
    if total_value <= 0:
        return None
    return weighted_sum / total_value


def get_top_performers(
    holdings: list[dict[str, Any]],
    n: int = 3,
) -> list[dict[str, Any]]:
    """Top ``n`` holdings sorted by return % descending."""
    enriched = [
        {**h, "return_pct": _holding_return_pct(h)}
        for h in holdings
        if _holding_return_pct(h) is not None
    ]
    enriched.sort(key=lambda x: x["return_pct"], reverse=True)
    return enriched[:n]


def get_underperformers(
    holdings: list[dict[str, Any]],
    n: int = 3,
) -> list[dict[str, Any]]:
    """Bottom ``n`` holdings sorted by return % ascending."""
    enriched = [
        {**h, "return_pct": _holding_return_pct(h)}
        for h in holdings
        if _holding_return_pct(h) is not None
    ]
    enriched.sort(key=lambda x: x["return_pct"])
    return enriched[:n]


async def enrich_holdings_with_prices(
    holdings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Attach ``current_price``/``change_pct``/``source`` to every holding.

    Returns ``(enriched_holdings, stale_tickers)`` where ``stale_tickers``
    contains tickers whose price came from cache or is unavailable.
    """
    tasks = [fetch_stock_price_safe(h["ticker"]) for h in holdings]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    enriched: list[dict[str, Any]] = []
    stale: list[str] = []
    for h, res in zip(holdings, results):
        out = dict(h)
        if isinstance(res, Exception) or not isinstance(res, dict):
            out["current_price"] = None
            out["change_pct"] = None
            out["source"] = "unavailable"
            stale.append(h["ticker"])
        else:
            out["current_price"] = res.get("price")
            out["change_pct"] = res.get("change_pct")
            out["source"] = res.get("source", "live")
            if out["source"] != "live":
                stale.append(h["ticker"])
        enriched.append(out)
    return enriched, stale
