"""Tests for backend.models.rationale_event."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from models.rationale_event import (
    EVENT_TYPES,
    RationaleEvent,
    RationaleEventWrite,
)


def test_event_types_has_eight_values():
    assert set(EVENT_TYPES) == {
        "target_change", "rebalance", "cash_deployment", "tax_harvest",
        "liquidity_event", "external_change", "market_commentary", "onboarding",
    }


def test_write_rejects_oversized_title():
    with pytest.raises(ValidationError):
        RationaleEventWrite(
            event_date=datetime.now(timezone.utc),
            event_type="rebalance",
            title="x" * 201,
            rationale_text="why",
        )


def test_write_accepts_minimal_body():
    body = RationaleEventWrite(
        event_date=datetime.now(timezone.utc),
        event_type="rebalance",
        title="Rebalanced equity",
        rationale_text="Trimmed equity by 4% after rally.",
    )
    assert body.link_transaction_ids == []


def test_full_row_round_trip():
    row = RationaleEvent.model_validate({
        "id": "11111111-1111-1111-1111-111111111111",
        "client_id": "22222222-2222-2222-2222-222222222222",
        "event_date": "2026-05-01T10:00:00+00:00",
        "event_type": "tax_harvest",
        "title": "Tax-loss harvest",
        "rationale_text": "Booked losses in XYZ.",
        "snapshot_id": None,
        "linked_target_id": None,
        "created_by_rm_id": "33333333-3333-3333-3333-333333333333",
        "created_at": "2026-05-01T10:05:00+00:00",
    })
    assert row.event_type == "tax_harvest"
    assert row.snapshot_id is None
