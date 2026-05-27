"""AMFI India daily NAV file parser and fetcher."""
from __future__ import annotations
from datetime import datetime
import httpx


AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"


def _parse_date(s: str) -> str:
    return datetime.strptime(s.strip(), "%d-%b-%Y").strftime("%Y-%m-%d")


def parse_navall(text: str) -> list[dict]:
    """Parse the AMFI NAVAll.txt body into scheme rows.

    The file is pipe (`;`)-separated with AMC names appearing as bare lines
    between scheme blocks. Blank lines, schema headers, and section titles
    are skipped.
    """
    rows: list[dict] = []
    current_amc: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ";" not in line:
            if line.startswith("Open Ended") or line.startswith("Close Ended"):
                continue
            current_amc = line
            continue
        parts = line.split(";")
        if len(parts) < 6 or parts[0].strip().lower() == "scheme code":
            continue
        code = parts[0].strip()
        if not code.isdigit():
            continue
        try:
            nav = float(parts[4].strip())
        except ValueError:
            continue
        try:
            nav_date = _parse_date(parts[5])
        except ValueError:
            continue
        rows.append(
            {
                "scheme_code": code,
                "amc": current_amc or "Unknown",
                "scheme_name": parts[3].strip(),
                "nav": nav,
                "nav_date": nav_date,
            }
        )
    return rows


def fetch_nav_rows(timeout: float = 30.0) -> list[dict]:
    """Download and parse the AMFI NAVAll file."""
    resp = httpx.get(AMFI_URL, timeout=timeout)
    resp.raise_for_status()
    return parse_navall(resp.text)
