from unittest.mock import patch, MagicMock
from services.feeds.amfi_nav import parse_navall, fetch_nav_rows


_SAMPLE = """\
Open Ended Schemes(Equity)

ICICI Prudential Mutual Fund

Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
120503;INF109K01Z48;INF109K01Z55;ICICI Prudential Bluechip Fund - Direct Plan - Growth;105.4321;25-May-2026
120601;INF109K01ABC;-;ICICI Prudential Value Discovery Fund - Direct Plan - Growth;88.1234;25-May-2026

Nippon India Mutual Fund

118989;INF204K01ZZ8;-;Nippon India Small Cap Fund - Direct Plan - Growth;195.7777;25-May-2026
"""


def test_parse_navall_extracts_scheme_rows_only():
    rows = parse_navall(_SAMPLE)
    codes = [r["scheme_code"] for r in rows]
    assert codes == ["120503", "120601", "118989"]


def test_parse_navall_captures_nav_and_date():
    rows = parse_navall(_SAMPLE)
    first = rows[0]
    assert first["scheme_code"] == "120503"
    assert first["nav"] == 105.4321
    assert first["nav_date"] == "2026-05-25"


def test_parse_navall_captures_amc_name():
    rows = parse_navall(_SAMPLE)
    assert rows[0]["amc"] == "ICICI Prudential Mutual Fund"
    assert rows[2]["amc"] == "Nippon India Mutual Fund"


def test_parse_navall_skips_blank_and_header_lines():
    rows = parse_navall(_SAMPLE)
    assert all("Scheme Code" not in r["scheme_name"] for r in rows)
    assert all(r["scheme_name"].strip() for r in rows)


def test_fetch_nav_rows_uses_mocked_http():
    fake = MagicMock()
    fake.text = _SAMPLE
    fake.status_code = 200
    with patch("services.feeds.amfi_nav.httpx.get", return_value=fake) as m:
        rows = fetch_nav_rows()
    m.assert_called_once()
    assert len(rows) == 3
