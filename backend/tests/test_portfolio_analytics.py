import pytest
from services.portfolio_analytics import compute_concentration


def _h(ticker, qty, price, sector="Technology"):
    return {"ticker": ticker, "qty": qty, "current_price": price, "sector": sector, "buy_price": price}


def test_concentration_top3_of_5():
    holdings = [
        _h("A", 100, 1000),   # 100k — top 1
        _h("B", 100,  800),   # 80k  — top 2
        _h("C", 100,  600),   # 60k  — top 3
        _h("D", 100,  400),   # 40k
        _h("E", 100,  100),   # 10k
    ]
    # top-3 total = 240k, grand total = 290k → 82.76%
    assert compute_concentration(holdings) == pytest.approx(82.7586, abs=0.01)


def test_concentration_empty_returns_none():
    assert compute_concentration([]) is None


def test_concentration_zero_mv_returns_none():
    holdings = [_h("A", 0, 0), _h("B", 0, 0)]
    assert compute_concentration(holdings) is None


def test_concentration_two_holdings_returns_100():
    holdings = [_h("A", 100, 1000), _h("B", 100, 500)]
    assert compute_concentration(holdings) == pytest.approx(100.0)


from services.portfolio_analytics import compute_absolute_gain


def test_absolute_gain_full_data():
    holdings = [
        {"ticker": "A", "qty": 100, "buy_price": 800, "current_price": 1000},
        {"ticker": "B", "qty":  50, "buy_price": 200, "current_price":  300},
    ]
    result = compute_absolute_gain(holdings)
    assert result["value"] == pytest.approx(25000.0)
    assert result["partial"] is False
    assert result["missing_tickers"] == []


def test_absolute_gain_partial_missing_price():
    holdings = [
        {"ticker": "A", "qty": 100, "buy_price": 800, "current_price": 1000},
        {"ticker": "B", "qty":  50, "buy_price": 200, "current_price": None},
    ]
    result = compute_absolute_gain(holdings)
    assert result["value"] == pytest.approx(20000.0)
    assert result["partial"] is True
    assert result["missing_tickers"] == ["B"]


def test_absolute_gain_all_missing_returns_none_value():
    holdings = [
        {"ticker": "A", "qty": 100, "buy_price": 800, "current_price": None},
        {"ticker": "B", "qty":  50, "buy_price": 200, "current_price": None},
    ]
    result = compute_absolute_gain(holdings)
    assert result["value"] is None
    assert result["partial"] is True
    assert sorted(result["missing_tickers"]) == ["A", "B"]


def test_absolute_gain_empty_holdings():
    result = compute_absolute_gain([])
    assert result == {"value": None, "partial": False, "missing_tickers": []}


def test_absolute_gain_negative_when_loss():
    holdings = [{"ticker": "A", "qty": 100, "buy_price": 1000, "current_price": 800}]
    result = compute_absolute_gain(holdings)
    assert result["value"] == pytest.approx(-20000.0)
    assert result["partial"] is False


from services.portfolio_analytics import compute_drift


def test_drift_perfect_match_aggressive():
    holdings = [
        {"qty": 700, "current_price": 1, "sector": "Technology"},
        {"qty": 250, "current_price": 1, "sector": "Debt"},
        {"qty":  50, "current_price": 1, "sector": "Cash"},
    ]
    assert compute_drift(holdings, "aggressive") == pytest.approx(0.0, abs=0.01)


def test_drift_all_equity_vs_moderate():
    holdings = [{"qty": 100, "current_price": 100, "sector": "Technology"}]
    assert compute_drift(holdings, "moderate") == pytest.approx(50.0, abs=0.01)


def test_drift_unknown_risk_profile_uses_moderate():
    holdings = [{"qty": 100, "current_price": 100, "sector": "Technology"}]
    assert compute_drift(holdings, "gambler") == pytest.approx(50.0, abs=0.01)


def test_drift_none_risk_profile_uses_moderate():
    holdings = [{"qty": 100, "current_price": 100, "sector": "Technology"}]
    assert compute_drift(holdings, None) == pytest.approx(50.0, abs=0.01)


def test_drift_zero_total_mv_returns_none():
    holdings = [{"qty": 0, "current_price": 0, "sector": "Technology"}]
    assert compute_drift(holdings, "moderate") is None


def test_drift_empty_holdings_returns_none():
    assert compute_drift([], "moderate") is None


def test_drift_debt_sector_recognized():
    holdings = [
        {"qty": 100, "current_price": 100, "sector": "Technology"},
        {"qty": 100, "current_price": 100, "sector": "Fixed Income"},
    ]
    # 50/50 vs aggressive (70/25/5) → equity drift = 20, debt drift = 25, cash = 5
    assert compute_drift(holdings, "aggressive") == pytest.approx(25.0, abs=0.01)


from datetime import date
from services.portfolio_analytics import compute_xirr


def test_xirr_simple_doubling_in_one_year():
    # 2024-01-01 → 2025-01-01 spans 366 days (leap year). With days/365.0 the
    # back-solved rate is 2^(365/366)-1 ≈ 0.9962 — still ~100% p.a. within 0.5%.
    txns = [{"txn_type": "BUY", "txn_date": date(2024, 1, 1), "total_value": 100}]
    result = compute_xirr(txns, current_value=200, today=date(2025, 1, 1))
    assert result == pytest.approx(1.0, abs=0.005)


def test_xirr_flat_returns_zero():
    txns = [{"txn_type": "BUY", "txn_date": date(2024, 1, 1), "total_value": 100}]
    result = compute_xirr(txns, current_value=100, today=date(2025, 1, 1))
    assert result == pytest.approx(0.0, abs=0.001)


def test_xirr_empty_transactions_returns_none():
    assert compute_xirr([], current_value=100) is None


def test_xirr_zero_current_value_returns_none():
    txns = [{"txn_type": "BUY", "txn_date": date(2024, 1, 1), "total_value": 100}]
    assert compute_xirr(txns, current_value=0) is None


def test_xirr_handles_sell_transactions():
    txns = [
        {"txn_type": "BUY",  "txn_date": date(2024, 1, 1), "total_value": 100},
        {"txn_type": "SELL", "txn_date": date(2024, 7, 1), "total_value":  50},
    ]
    result = compute_xirr(txns, current_value=60, today=date(2025, 1, 1))
    assert result is not None
    assert -0.5 < result < 0.5


def test_xirr_non_convergent_returns_none():
    # All cashflows same sign — no root exists in [-0.99, 10.0]
    txns = [
        {"txn_type": "SELL", "txn_date": date(2024, 1, 1), "total_value": 100},
        {"txn_type": "SELL", "txn_date": date(2024, 7, 1), "total_value": 100},
    ]
    result = compute_xirr(txns, current_value=100, today=date(2025, 1, 1))
    assert result is None
