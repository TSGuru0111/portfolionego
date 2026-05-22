"""File-backed config store.

All editable configuration lives under ``backend/config/``:

    config/
    ├── agents/              .md files prepended as system context
    ├── feeds.json           RSS / NewsAPI / GNews configuration
    └── style_samples/       previous RM letters, used as few-shot examples

This module exposes safe read/write helpers used by both the
``/config/*`` REST endpoints and the runtime services (news_fetcher,
prompt_builder).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIG_ROOT = Path(__file__).resolve().parent.parent / "config"
AGENTS_DIR = CONFIG_ROOT / "agents"
STYLE_DIR = CONFIG_ROOT / "style_samples"
FEEDS_FILE = CONFIG_ROOT / "feeds.json"

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_\-\.]+$")


def _ensure_dirs() -> None:
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    STYLE_DIR.mkdir(parents=True, exist_ok=True)


def _safe_md_name(name: str) -> str:
    """Reject path traversal, force .md extension."""
    name = name.strip()
    if not name:
        raise ValueError("Empty filename")
    if not name.endswith(".md"):
        name = f"{name}.md"
    base = name[:-3]
    if not _SAFE_NAME.match(base):
        raise ValueError(
            "Filename must contain only letters, digits, underscore, dash, dot"
        )
    return name


# --- Agents (system-context .md files) -------------------------------------

def list_agent_files() -> list[dict[str, Any]]:
    _ensure_dirs()
    out: list[dict[str, Any]] = []
    for path in sorted(AGENTS_DIR.glob("*.md")):
        stat = path.stat()
        out.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "updated_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    return out


def read_agent_file(name: str) -> str:
    _ensure_dirs()
    safe = _safe_md_name(name)
    path = AGENTS_DIR / safe
    if not path.exists():
        raise FileNotFoundError(f"Agent file not found: {safe}")
    return path.read_text(encoding="utf-8")


def write_agent_file(name: str, content: str) -> dict[str, Any]:
    _ensure_dirs()
    safe = _safe_md_name(name)
    path = AGENTS_DIR / safe
    path.write_text(content, encoding="utf-8")
    stat = path.stat()
    return {
        "name": safe,
        "size": stat.st_size,
        "updated_at": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
    }


def delete_agent_file(name: str) -> None:
    safe = _safe_md_name(name)
    path = AGENTS_DIR / safe
    if path.exists():
        path.unlink()


def read_all_agent_context() -> str:
    """Concatenate every .md file in ``agents/`` for system-prompt injection."""
    _ensure_dirs()
    parts: list[str] = []
    for path in sorted(AGENTS_DIR.glob("*.md")):
        parts.append(f"# {path.stem}\n\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n---\n\n".join(parts)


# --- Style samples (prior RM letters) --------------------------------------

def list_style_samples() -> list[dict[str, Any]]:
    _ensure_dirs()
    out: list[dict[str, Any]] = []
    for path in sorted(STYLE_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        stat = path.stat()
        out.append(
            {
                "id": path.stem,
                "name": path.name,
                "size": stat.st_size,
                "updated_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    return out


def read_style_sample(sample_id: str) -> str:
    safe = _safe_md_name(sample_id)
    path = STYLE_DIR / safe
    if not path.exists():
        raise FileNotFoundError(f"Style sample not found: {safe}")
    return path.read_text(encoding="utf-8")


def create_style_sample(
    content: str,
    title: str | None = None,
) -> dict[str, Any]:
    """Write a new sample. ``title`` becomes the filename if safe, else a uuid."""
    _ensure_dirs()
    if title:
        try:
            safe = _safe_md_name(title)
        except ValueError:
            safe = f"sample-{uuid.uuid4().hex[:8]}.md"
    else:
        safe = f"sample-{uuid.uuid4().hex[:8]}.md"
    path = STYLE_DIR / safe
    path.write_text(content, encoding="utf-8")
    stat = path.stat()
    return {
        "id": path.stem,
        "name": safe,
        "size": stat.st_size,
        "updated_at": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
    }


def delete_style_sample(sample_id: str) -> None:
    safe = _safe_md_name(sample_id)
    path = STYLE_DIR / safe
    if path.exists():
        path.unlink()


def read_all_style_samples() -> list[str]:
    """Return every uploaded sample's content for few-shot injection."""
    _ensure_dirs()
    out: list[str] = []
    for path in sorted(STYLE_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        out.append(path.read_text(encoding="utf-8").strip())
    return out


# --- Feeds (RSS + NewsAPI + GNews) -----------------------------------------

DEFAULT_FEEDS: dict[str, Any] = {
    "rss": [],
    "newsapi": {"enabled": True, "queries": [], "language": "en"},
    "gnews": {"enabled": True, "sectors": []},
}


def read_feeds() -> dict[str, Any]:
    _ensure_dirs()
    if not FEEDS_FILE.exists():
        return dict(DEFAULT_FEEDS)
    try:
        return json.loads(FEEDS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(DEFAULT_FEEDS)


def write_feeds(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_dirs()
    # Light validation — keep only the three top-level keys we know.
    rss = payload.get("rss") or []
    if not isinstance(rss, list):
        raise ValueError("'rss' must be a list")
    cleaned_rss = []
    for item in rss:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        cleaned_rss.append(
            {
                "id": str(item.get("id") or item["url"]),
                "label": str(item.get("label") or item["url"]),
                "url": str(item["url"]),
                "category": str(item.get("category") or "general"),
                "enabled": bool(item.get("enabled", True)),
            }
        )

    newsapi = payload.get("newsapi") or {}
    if not isinstance(newsapi, dict):
        raise ValueError("'newsapi' must be an object")
    cleaned_newsapi = {
        "enabled": bool(newsapi.get("enabled", True)),
        "queries": [str(q) for q in (newsapi.get("queries") or []) if str(q).strip()],
        "language": str(newsapi.get("language") or "en"),
    }

    gnews = payload.get("gnews") or {}
    if not isinstance(gnews, dict):
        raise ValueError("'gnews' must be an object")
    cleaned_gnews = {
        "enabled": bool(gnews.get("enabled", True)),
        "sectors": [str(s) for s in (gnews.get("sectors") or []) if str(s).strip()],
    }

    final = {
        "rss": cleaned_rss,
        "newsapi": cleaned_newsapi,
        "gnews": cleaned_gnews,
    }
    FEEDS_FILE.write_text(json.dumps(final, indent=2), encoding="utf-8")
    return final
