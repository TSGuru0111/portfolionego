from unittest.mock import patch, MagicMock
from services.feeds.gold_price import parse_ibja_html, fetch_gold_price_per_gram


_SAMPLE_HTML = """
<html><body>
<span id="lblFineGold999">₹ 7234.50</span>
<span id="lblKarat22">₹ 6627.20</span>
</body></html>
"""


def test_parse_ibja_html_extracts_999_price():
    px = parse_ibja_html(_SAMPLE_HTML, purity="999")
    assert px == 7234.50


def test_parse_ibja_html_extracts_22k_price():
    px = parse_ibja_html(_SAMPLE_HTML, purity="22k")
    assert px == 6627.20


def test_parse_ibja_html_returns_none_when_purity_missing():
    assert parse_ibja_html("<html></html>", purity="999") is None


def test_fetch_gold_price_uses_mocked_http():
    fake = MagicMock()
    fake.text = _SAMPLE_HTML
    fake.status_code = 200
    with patch("services.feeds.gold_price.httpx.get", return_value=fake) as m:
        result = fetch_gold_price_per_gram(purity="999")
    m.assert_called_once()
    assert result["price_per_gram"] == 7234.50
    assert result["purity"] == "999"
    assert result["source"] == "ibja"
    assert "fetched_at" in result
