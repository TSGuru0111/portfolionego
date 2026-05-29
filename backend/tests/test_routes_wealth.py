"""Tests for backend/routes/wealth.py."""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

_HDR = {"Authorization": "Bearer fake-jwt"}


@patch("routes.wealth._current_rm_id")
@patch("routes.wealth.get_latest_snapshot")
def test_get_latest_snapshot_returns_row(mock_get, mock_rm):
    mock_rm.return_value = uuid4()
    snap_id = uuid4()
    client_id = uuid4()
    mock_get.return_value = {
        "id": str(snap_id),
        "client_id": str(client_id),
        "as_of": "2026-05-01T00:00:00+00:00",
        "trigger": "report",
        "net_worth": "1000000.00",
        "allocation_pct": {"equity": "0.5", "debt": "0.3"},
        "snapshot_json": {},
    }
    r = client.get(f"/clients/{client_id}/snapshots/latest", headers=_HDR)
    assert r.status_code == 200
    assert r.json()["net_worth"] == "1000000.00"
    mock_get.assert_called_once()


@patch("routes.wealth._current_rm_id")
@patch("routes.wealth.get_latest_snapshot")
def test_get_latest_snapshot_404_when_missing(mock_get, mock_rm):
    mock_rm.return_value = uuid4()
    mock_get.return_value = None
    r = client.get(f"/clients/{uuid4()}/snapshots/latest", headers=_HDR)
    assert r.status_code == 404


@patch("routes.wealth._current_rm_id")
@patch("routes.wealth.get_active_target")
def test_get_current_target_returns_row(mock_get, mock_rm):
    mock_rm.return_value = uuid4()
    mock_get.return_value = {
        "id": str(uuid4()),
        "effective_to": None,
        "equity_pct": "45",
    }
    r = client.get(f"/clients/{uuid4()}/allocation-target", headers=_HDR)
    assert r.status_code == 200


@patch("routes.wealth._current_rm_id")
@patch("routes.wealth.persist_snapshot")
@patch("routes.wealth.change_allocation_target")
@patch("routes.wealth.insert_rationale_event")
def test_put_allocation_target_happy_path(mock_event, mock_change, mock_persist, mock_rm):
    rm_id = uuid4()
    mock_rm.return_value = rm_id
    new_event_id = uuid4()
    new_target_id = uuid4()
    new_snap_id = uuid4()
    mock_event.return_value = {"id": str(new_event_id)}
    mock_change.return_value = {"id": str(new_target_id)}
    mock_persist.return_value = {"id": str(new_snap_id)}

    payload = {
        "risk_profile": "Aggressive",
        "target_pct": {
            "equity": "65", "debt": "20", "gold": "5",
            "cash": "8", "alternatives": "2",
        },
        "band_pct": {
            "equity": "5", "debt": "5", "gold": "2",
            "cash": "3", "alternatives": "3",
        },
        "rationale_text": "Aggressive growth",
    }
    r = client.put(f"/clients/{uuid4()}/allocation-target", headers=_HDR, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["target_id"] == str(new_target_id)
    assert body["event_id"] == str(new_event_id)
    assert body["snapshot_id"] == str(new_snap_id)


@patch("routes.wealth._current_rm_id")
@patch("routes.wealth.persist_snapshot")
@patch("routes.wealth.change_allocation_target")
@patch("routes.wealth.insert_rationale_event")
def test_put_allocation_target_snapshot_failure_does_not_abort(
    mock_event, mock_change, mock_persist, mock_rm
):
    mock_rm.return_value = uuid4()
    mock_event.return_value = {"id": str(uuid4())}
    mock_change.return_value = {"id": str(uuid4())}
    mock_persist.side_effect = RuntimeError("snapshot failed")

    payload = {
        "risk_profile": "Moderate",
        "target_pct": {
            "equity": "45", "debt": "35", "gold": "8",
            "cash": "10", "alternatives": "2",
        },
        "band_pct": {
            "equity": "5", "debt": "5", "gold": "2",
            "cash": "3", "alternatives": "3",
        },
        "rationale_text": "Routine review",
    }
    r = client.put(f"/clients/{uuid4()}/allocation-target", headers=_HDR, json=payload)
    assert r.status_code == 200
    assert r.json()["snapshot_id"] is None


@patch("routes.wealth._current_rm_id")
@patch("routes.wealth.get_active_target")
@patch("routes.wealth.get_latest_snapshot")
@patch("routes.wealth.compute_drift")
def test_get_drift_returns_list(mock_drift, mock_snap, mock_target, mock_rm):
    mock_rm.return_value = uuid4()
    mock_target.return_value = {
        "equity_pct": "45", "debt_pct": "35", "gold_pct": "8",
        "cash_pct": "10", "alternatives_pct": "2",
        "equity_band_pct": "5", "debt_band_pct": "5", "gold_band_pct": "2",
        "cash_band_pct": "3", "alternatives_band_pct": "3",
    }
    mock_snap.return_value = {"allocation_pct": {"equity": "0.6"}}
    mock_drift.return_value = [
        {"class": "equity", "target_pct": "45", "actual_pct": "60",
         "delta_pct": "15", "band_pct": "5", "status": "over"}
    ]
    r = client.get(f"/clients/{uuid4()}/drift", headers=_HDR)
    assert r.status_code == 200
    assert r.json()[0]["status"] == "over"
