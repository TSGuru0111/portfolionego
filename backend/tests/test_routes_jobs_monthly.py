"""Tests for monthly snapshots cron handler."""
from __future__ import annotations

import os
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


@patch.dict(os.environ, {"JOB_SECRET": "S3CR3T"})
def test_monthly_snapshots_rejects_bad_secret():
    r = client.post("/jobs/monthly-snapshots?secret=wrong")
    assert r.status_code == 403


@patch.dict(os.environ, {"JOB_SECRET": "S3CR3T"})
@patch("routes.jobs.log_job_run")
@patch("routes.jobs._persist_snapshot")
@patch("routes.jobs.list_all_clients")
def test_monthly_snapshots_iterates_all_clients(mock_list, mock_persist, mock_log):
    c1, c2, c3 = uuid4(), uuid4(), uuid4()
    mock_list.return_value = [
        {"id": str(c1)}, {"id": str(c2)}, {"id": str(c3)},
    ]
    mock_persist.return_value = {"id": str(uuid4())}
    mock_log.return_value = None

    r = client.post("/jobs/monthly-snapshots?secret=S3CR3T")
    assert r.status_code == 200
    body = r.json()
    assert body["clients_total"] == 3
    assert body["ok"] == 3
    assert body["failed"] == 0
    assert mock_persist.call_count == 3


@patch.dict(os.environ, {"JOB_SECRET": "S3CR3T"})
@patch("routes.jobs.log_error")
@patch("routes.jobs.log_job_run")
@patch("routes.jobs._persist_snapshot")
@patch("routes.jobs.list_all_clients")
def test_monthly_snapshots_continues_on_per_client_failure(
    mock_list, mock_persist, mock_log_run, mock_log_err
):
    c1, c2 = uuid4(), uuid4()
    mock_list.return_value = [{"id": str(c1)}, {"id": str(c2)}]
    mock_persist.side_effect = [RuntimeError("boom"), {"id": str(uuid4())}]
    mock_log_run.return_value = None
    mock_log_err.return_value = None

    r = client.post("/jobs/monthly-snapshots?secret=S3CR3T")
    assert r.status_code == 200
    body = r.json()
    assert body["clients_total"] == 2
    assert body["ok"] == 1
    assert body["failed"] == 1
