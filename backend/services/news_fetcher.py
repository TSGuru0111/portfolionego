"""RSS / NewsAPI / GNews fetchers.

Configuration is loaded from ``backend/config/feeds.json`` (writable via
the Config tab). All network calls are wrapped in best-effort try/except —
a failing feed never breaks the pipeline; it logs to ``error_logs`` and
returns an empty list.
"""
from __future__ import annotations

import asyncio
import os
from datetime import date
from typing import Any

import feedparser
import requests

from services import config_store
from services.error_logger import log_error

USER_AGENT = "PortfolioNarrator/0.1 (+contact rm@wealthfirm.example)"
REQUEST_TIMEOUT = 12  # seconds


def _log_error_safe(job: str, exc: Exception, context: dict | None = None) -> None:
    """Fire-and-forget error log that works from sync or async context.

    The fetchers below run inside ``asyncio.to_thread`` worker threads which
    have no running event loop, so ``asyncio.create_task`` raises
    ``RuntimeError: no running event loop``. This helper schedules the log
    appropriately for either context and never re-raises.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(log_error(job, exc, context or {}))
        return
    except RuntimeError:
        pass
    try:
        asyncio.run(log_error(job, exc, context or {}))
    except Exception:  # noqa: BLE001
        print(f"[error_log_fail] {job}: {exc}")


# ────────────────────────────────────────────────── config readers ──

def load_feed_config() -> dict[str, Any]:
    return config_store.read_feeds()


def enabled_rss_feeds() -> list[dict[str, Any]]:
    return [f for f in load_feed_config().get("rss", []) if f.get("enabled")]


def newsapi_queries() -> list[str]:
    cfg = load_feed_config().get("newsapi") or {}
    if not cfg.get("enabled"):
        return []
    return list(cfg.get("queries") or [])


def gnews_sectors() -> list[str]:
    cfg = load_feed_config().get("gnews") or {}
    if not cfg.get("enabled"):
        return []
    return list(cfg.get("sectors") or [])


def newsapi_language() -> str:
    cfg = load_feed_config().get("newsapi") or {}
    return str(cfg.get("language") or "en")


# ────────────────────────────────────────────────────── fetchers ──

def fetch_rss(
    url: str,
    limit: int = 5,
    category: str = "general",
    source_label: str | None = None,
) -> list[dict[str, str]]:
    """Parse an RSS/Atom feed and return up to ``limit`` normalised items."""
    try:
        parsed = feedparser.parse(url, agent=USER_AGENT)
    except Exception as exc:  # noqa: BLE001
        _log_error_safe("rss_parse", exc, {"url": url})
        return []

    entries = getattr(parsed, "entries", []) or []
    out: list[dict[str, str]] = []
    today = date.today().isoformat()
    for entry in entries[:limit]:
        title = (getattr(entry, "title", "") or "").strip()
        if not title:
            continue
        summary = (
            getattr(entry, "summary", None)
            or getattr(entry, "description", None)
            or ""
        )
        out.append(
            {
                "date": today,
                "category": category,
                "headline": title[:500],
                "summary": str(summary)[:2000],
                "source": source_label or url,
            }
        )
    return out


def fetch_newsapi(query: str, limit: int = 3) -> list[dict[str, str]]:
    """Top headlines for a query via NewsAPI.org /v2/everything."""
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        return []
    try:
        res = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "language": newsapi_language(),
                "sortBy": "publishedAt",
                "pageSize": limit,
                "apiKey": api_key,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        res.raise_for_status()
        payload = res.json()
    except Exception as exc:  # noqa: BLE001
        _log_error_safe("newsapi_fetch", exc, {"query": query})
        return []

    today = date.today().isoformat()
    items = payload.get("articles", []) or []
    out: list[dict[str, str]] = []
    for art in items[:limit]:
        title = (art.get("title") or "").strip()
        if not title:
            continue
        source = (art.get("source") or {}).get("name") or "NewsAPI"
        out.append(
            {
                "date": today,
                "category": "newsapi",
                "headline": title[:500],
                "summary": (art.get("description") or "")[:2000],
                "source": source,
            }
        )
    return out


def fetch_gnews(sector: str, limit: int = 3) -> list[dict[str, str]]:
    """Top headlines for a sector via GNews.io /search."""
    api_key = os.getenv("GNEWS_API_KEY")
    if not api_key:
        return []
    try:
        res = requests.get(
            "https://gnews.io/api/v4/search",
            params={
                "q": sector,
                "lang": "en",
                "country": "in",
                "max": limit,
                "apikey": api_key,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        res.raise_for_status()
        payload = res.json()
    except Exception as exc:  # noqa: BLE001
        _log_error_safe("gnews_fetch", exc, {"sector": sector})
        return []

    today = date.today().isoformat()
    items = payload.get("articles", []) or []
    out: list[dict[str, str]] = []
    for art in items[:limit]:
        title = (art.get("title") or "").strip()
        if not title:
            continue
        source = (art.get("source") or {}).get("name") or "GNews"
        out.append(
            {
                "date": today,
                "category": f"gnews_{sector}",
                "headline": title[:500],
                "summary": (art.get("description") or "")[:2000],
                "source": source,
            }
        )
    return out


# ───────────────────────────────────────────────── aggregators ──

async def collect_daily_news() -> list[dict[str, str]]:
    """Pull from every enabled source. Used by the daily cron job."""

    def _gather_all() -> list[dict[str, str]]:
        bag: list[dict[str, str]] = []
        for feed in enabled_rss_feeds():
            bag.extend(
                fetch_rss(
                    feed["url"],
                    limit=5,
                    category=feed.get("category") or "general",
                    source_label=feed.get("label") or feed.get("url"),
                )
            )
        for q in newsapi_queries():
            bag.extend(fetch_newsapi(q, limit=3))
        for s in gnews_sectors():
            bag.extend(fetch_gnews(s, limit=3))
        return bag

    return await asyncio.to_thread(_gather_all)


def _portfolio_sectors(portfolio: dict[str, Any]) -> list[str]:
    holdings = portfolio.get("holdings") or []
    seen: list[str] = []
    for h in holdings:
        sector = (h.get("sector") or "").strip().lower()
        if sector and sector not in seen:
            seen.append(sector)
    return seen


def _portfolio_tickers(portfolio: dict[str, Any]) -> list[str]:
    holdings = portfolio.get("holdings") or []
    out: list[str] = []
    for h in holdings:
        tkr = (h.get("ticker") or "").strip()
        if tkr and tkr not in out:
            out.append(tkr)
    return out


async def fetch_client_relevant_news(
    client_id: str,
    portfolio: dict[str, Any],
    per_source_limit: int = 3,
) -> dict[str, Any]:
    """Portfolio-aware news bundle for one client's report.

    Mixes:
      - GNews per sector in the client's holdings
      - NewsAPI per top ticker (company name preferred if present)
      - Configured RSS feeds (small slice for broader context)
    """
    sectors = _portfolio_sectors(portfolio)[:5]
    tickers = _portfolio_tickers(portfolio)[:5]
    holdings = portfolio.get("holdings") or []

    # Use company_name if available for richer NewsAPI queries.
    ticker_queries: list[str] = []
    for h in holdings[:5]:
        q = h.get("company_name") or h.get("ticker")
        if q and q not in ticker_queries:
            ticker_queries.append(str(q))

    def _gather() -> dict[str, Any]:
        per_sector: dict[str, list[dict[str, str]]] = {}
        for sector in sectors:
            per_sector[sector] = fetch_gnews(sector, limit=per_source_limit)

        per_ticker: dict[str, list[dict[str, str]]] = {}
        for query in ticker_queries:
            per_ticker[query] = fetch_newsapi(query, limit=per_source_limit)

        rss_context: list[dict[str, str]] = []
        for feed in enabled_rss_feeds()[:3]:
            rss_context.extend(
                fetch_rss(
                    feed["url"],
                    limit=3,
                    category=feed.get("category") or "general",
                    source_label=feed.get("label") or feed.get("url"),
                )
            )
        return {
            "by_sector": per_sector,
            "by_ticker": per_ticker,
            "rss_context": rss_context,
        }

    bundle = await asyncio.to_thread(_gather)
    bundle["client_id"] = client_id
    bundle["tickers"] = tickers
    bundle["sectors"] = sectors
    return bundle
