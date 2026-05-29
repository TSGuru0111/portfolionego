"""Tests for rationale-events endpoints on clients router."""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _hdr() -> dict[str, str]:
    return {"Authorization": "Bearer fake-jwt"}


@patch("routes.clients._current_rm_id")
@patch("routes.clients.persist_snapshot")
@patch("routes.clients.link_transactions_to_event")
@patch("routes.clients.insert_rationale_event")
def test_post_manual_event_happy_path(mock_event, mock_link, mock_snap, mock_rm):
    mock_rm.return_value = uuid4()
    event_id = uuid4()
    snap_id = uuid4()
    mock_event.return_value = {"id": str(event_id)}
    mock_snap.return_value = {"id": str(snap_id)}

    payload = {
        "event_type": "rebalance",
        "event_date": "2026-04-15",
        "title": "Quarterly rebalance",
        "body": "Trimmed equity exposure",
        "transaction_ids": [],
    }
    r = client.post(f"/clients/{uuid4()}/rationale-events", headers=_hdr(), json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["event_id"] == str(event_id)
    assert body["snapshot_id"] == str(snap_id)


@patch("routes.clients._current_rm_id")
def test_post_manual_event_rejects_target_change(mock_rm):
    mock_rm.return_value = uuid4()
    payload = {
        "event_type": "target_change",
        "event_date": "2026-04-15",
        "title": "x",
        "body": "y",
    }
    r = client.post(f"/clients/{uuid4()}/rationale-events", headers=_hdr(), json=payload)
    assert r.status_code == 422


@patch("routes.clients._current_rm_id")
def test_post_manual_event_rejects_onboarding(mock_rm):
    mock_rm.return_value = uuid4()
    payload = {
        "event_type": "onboarding",
        "event_date": "2026-04-15",
        "title": "x",
        "body": "y",
    }
    r = client.post(f"/clients/{uuid4()}/rationale-events", headers=_hdr(), json=payload)
    assert r.status_code == 422


@patch("routes.clients._current_rm_id")
@patch("routes.clients.list_rationale_events")
def test_get_events_returns_list(mock_list, mock_rm):
    mock_rm.return_value = uuid4()
    mock_list.return_value = [
        {"id": str(uuid4()), "event_type": "rebalance", "event_date": "2026-04-15"}
    ]
    r = client.get(
        f"/clients/{uuid4()}/rationale-events?from=2026-01-01&to=2026-06-30",
        headers=_hdr(),
    )
    assert r.status_code == 200
    assert len(r.json()) == 1
