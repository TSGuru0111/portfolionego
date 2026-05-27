import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app


_SECRET = os.environ.setdefault("JOB_SECRET", "test-secret")
client = TestClient(app)


def test_refresh_nav_cache_rejects_bad_secret():
    r = client.get("/jobs/refresh-nav-cache?secret=wrong")
    assert r.status_code in (401, 403)


def test_refresh_nav_cache_happy_path():
    fake_rows = [
        {"scheme_code": "120503", "amc": "ICICI", "scheme_name": "X",
         "nav": 100.0, "nav_date": "2026-05-25"}
    ]
    with patch("routes.jobs.fetch_nav_rows", return_value=fake_rows), \
         patch("routes.jobs.nav_cache_db.upsert") as upsert, \
         patch("routes.jobs.job_runs_db.insert"):
        r = client.get(f"/jobs/refresh-nav-cache?secret={_SECRET}")
    assert r.status_code == 200
    body = r.json()
    assert body["records"] == 1
    upsert.assert_called_once()


def test_refresh_gold_price_happy_path():
    fake = {"purity": "999", "price_per_gram": 7234.5,
            "source": "ibja", "fetched_at": "2026-05-25T00:00:00+00:00"}
    with patch("routes.jobs.fetch_gold_price_per_gram", return_value=fake), \
         patch("routes.jobs.gold_price_cache_db.insert") as ins, \
         patch("routes.jobs.job_runs_db.insert"):
        r = client.get(f"/jobs/refresh-gold-price?secret={_SECRET}")
    assert r.status_code == 200
    ins.assert_called_once_with(fake)
