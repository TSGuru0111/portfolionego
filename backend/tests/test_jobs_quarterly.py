from __future__ import annotations
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
import routes.jobs as jobs_module


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def test_quarterly_rejects_wrong_secret(client, monkeypatch):
    monkeypatch.setenv("JOB_SECRET", "real-secret")
    assert client.post("/jobs/quarterly-reports?secret=wrong").status_code == 403


def test_quarterly_iterates_all_clients(client, monkeypatch):
    monkeypatch.setenv("JOB_SECRET", "test-secret")
    fake_clients = [{"id": "c1"}, {"id": "c2"}]

    async def _fake_ctx(cid, quarter, cadence="monthly"):
        return {"client": {"id": cid, "name": "X"},
                "holdings": [{"ticker": "T", "current_price": 1}]}

    with patch.object(jobs_module, "list_all_clients", return_value=fake_clients), \
         patch("routes.jobs.build_context_packet", side_effect=_fake_ctx), \
         patch("routes.jobs.report_generator") as mock_gen, \
         patch("routes.jobs.log_error", new_callable=AsyncMock), \
         patch("routes.jobs.log_job_run", new_callable=AsyncMock):
        mock_gen.generate_report_batch = AsyncMock(return_value={"status": "ok"})
        resp = client.post("/jobs/quarterly-reports?secret=test-secret")

    assert resp.status_code == 200
    body = resp.json()
    assert body["clients_total"] == 2
    assert body["ok"] == 2
    assert body["failed"] == 0


def test_quarterly_tolerates_per_client_failure(client, monkeypatch):
    monkeypatch.setenv("JOB_SECRET", "test-secret")
    fake_clients = [{"id": "c1"}, {"id": "c2"}]

    async def _fail_c1(cid, quarter, cadence="monthly"):
        if cid == "c1":
            raise RuntimeError("context build failed")
        return {"client": {"id": cid, "name": "X"},
                "holdings": [{"ticker": "T", "current_price": 1}]}

    with patch.object(jobs_module, "list_all_clients", return_value=fake_clients), \
         patch("routes.jobs.build_context_packet", side_effect=_fail_c1), \
         patch("routes.jobs.report_generator") as mock_gen, \
         patch("routes.jobs.log_error", new_callable=AsyncMock), \
         patch("routes.jobs.log_job_run", new_callable=AsyncMock):
        mock_gen.generate_report_batch = AsyncMock(return_value={"status": "ok"})
        resp = client.post("/jobs/quarterly-reports?secret=test-secret")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] == 1
    assert body["failed"] == 1
