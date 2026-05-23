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
