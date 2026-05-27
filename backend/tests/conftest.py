"""Shared pytest fixtures for the Phase 2 backend test suite."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
if (_ROOT / ".env.test").exists():
    load_dotenv(_ROOT / ".env.test", override=True)
elif (_ROOT / ".env").exists():
    load_dotenv(_ROOT / ".env", override=False)


@pytest.fixture
def fake_client_id() -> str:
    """Stable demo client UUID — Rajesh Mehta from seed_v2.sql."""
    return "d62e9583-9d56-4e45-8665-e0634b3db42a"


@pytest.fixture
def random_client_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def fake_rm_id() -> str:
    return "00000000-0000-0000-0000-000000000001"
