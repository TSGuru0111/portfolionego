from datetime import date, datetime, timezone
from unittest.mock import patch
from services.wealth_aggregator import build_wealth_snapshot


_FAKE_MFS = [{
    "id": "mf1", "client_id": "c1", "scheme_code": "120503",
    "scheme_name": "ICICI Bluechip", "amc": "ICICI",
    "category": "equity", "sub_category": "largecap",
    "units": 1000.0, "purchase_nav": 80.0, "purchase_date": "2023-01-01",
}]
_FAKE_NAV_CACHE = {
    "scheme_code": "120503", "nav": 105.4321, "nav_date": "2026-05-25",
    "fetched_at": datetime.now(timezone.utc).isoformat(),
}
_FAKE_GOLD = [{
    "id": "g1", "client_id": "c1", "form": "physical",
    "weight_grams": 100.0, "purity": "999",
    "purchase_price_per_gram": 5500.0, "purchase_date": "2022-01-01",
}]
_FAKE_GOLD_CACHE = {
    "purity": "999", "price_per_gram": 7234.50, "source": "ibja",
    "fetched_at": datetime.now(timezone.utc).isoformat(),
}
_FAKE_FDS = [{
    "id": "fd1", "client_id": "c1", "bank": "HDFC",
    "principal": 500_000.0, "rate_pct": 7.5,
    "start_date": "2024-01-01", "maturity_date": "2027-01-01",
    "compounding": "quarterly",
}]
_FAKE_CASH = [{
    "id": "ca1", "client_id": "c1", "account_type": "savings",
    "bank": "HDFC", "balance": 250_000.0,
}]


def test_snapshot_aggregates_buckets():
    with patch("services.wealth_aggregator.mutual_funds_db.get_for_client", return_value=_FAKE_MFS), \
         patch("services.wealth_aggregator.bonds_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.gold_db.get_for_client", return_value=_FAKE_GOLD), \
         patch("services.wealth_aggregator.cash_db.get_for_client", return_value=_FAKE_CASH), \
         patch("services.wealth_aggregator.fds_db.get_for_client", return_value=_FAKE_FDS), \
         patch("services.wealth_aggregator.insurance_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.liabilities_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.nav_cache_db.get", return_value=_FAKE_NAV_CACHE), \
         patch("services.wealth_aggregator.gold_price_cache_db.get_latest", return_value=_FAKE_GOLD_CACHE), \
         patch("services.wealth_aggregator.market_yields_db.get_curve", return_value=[]):
        snap = build_wealth_snapshot("c1", as_of=date(2025, 6, 1))
    assert round(snap.mutual_funds.current_value, 2) == 105_432.10
    assert round(snap.gold.current_value, 2) == 723_450.00
    assert snap.cash.current_value == 250_000.0
    assert snap.fixed_deposits.current_value > 500_000.0
    assert snap.net_worth > 0


def test_snapshot_marks_stale_when_nav_cache_missing():
    with patch("services.wealth_aggregator.mutual_funds_db.get_for_client", return_value=_FAKE_MFS), \
         patch("services.wealth_aggregator.bonds_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.gold_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.cash_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.fds_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.insurance_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.liabilities_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.nav_cache_db.get", return_value=None), \
         patch("services.wealth_aggregator.gold_price_cache_db.get_latest", return_value=None), \
         patch("services.wealth_aggregator.market_yields_db.get_curve", return_value=[]):
        snap = build_wealth_snapshot("c1", as_of=date(2025, 6, 1))
    assert snap.has_stale_values is True
    assert "mutual_funds" in snap.stale_sources


def test_snapshot_asset_allocation_sums_to_one():
    with patch("services.wealth_aggregator.mutual_funds_db.get_for_client", return_value=_FAKE_MFS), \
         patch("services.wealth_aggregator.bonds_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.gold_db.get_for_client", return_value=_FAKE_GOLD), \
         patch("services.wealth_aggregator.cash_db.get_for_client", return_value=_FAKE_CASH), \
         patch("services.wealth_aggregator.fds_db.get_for_client", return_value=_FAKE_FDS), \
         patch("services.wealth_aggregator.insurance_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.liabilities_db.get_for_client", return_value=[]), \
         patch("services.wealth_aggregator.nav_cache_db.get", return_value=_FAKE_NAV_CACHE), \
         patch("services.wealth_aggregator.gold_price_cache_db.get_latest", return_value=_FAKE_GOLD_CACHE), \
         patch("services.wealth_aggregator.market_yields_db.get_curve", return_value=[]):
        snap = build_wealth_snapshot("c1", as_of=date(2025, 6, 1))
    total = sum(snap.asset_allocation.values())
    assert 0.999 <= total <= 1.001
