"""Supabase client singleton.

Lazy-initialised so unit tests that don't need a real DB connection
don't blow up when SUPABASE_URL is missing.
"""
from __future__ import annotations

import os
from typing import Optional

try:
    from supabase import Client, create_client
except ImportError:  # supabase-py not installed yet in some envs
    Client = None  # type: ignore[assignment]
    create_client = None  # type: ignore[assignment]

_client: Optional["Client"] = None


def get_supabase() -> Optional["Client"]:
    """Return a process-wide Supabase client, or ``None`` if not configured."""
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key or create_client is None:
        return None

    _client = create_client(url, key)
    return _client


def reset_supabase_client() -> None:
    """Test helper — reset the cached client."""
    global _client
    _client = None
