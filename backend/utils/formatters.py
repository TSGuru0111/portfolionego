"""Indian-locale formatters used in prompts, PDFs, and admin pages."""
from __future__ import annotations

from datetime import date, datetime


def format_inr(amount: float, decimals: int = 2) -> str:
    """Return Indian-grouped INR string, e.g. ₹1,23,456.78."""
    if amount is None:
        return "—"
    is_negative = amount < 0
    amount = abs(amount)
    int_part, _, dec_part = f"{amount:.{decimals}f}".partition(".")
    # Indian grouping: last 3 digits, then every 2.
    if len(int_part) > 3:
        head, tail = int_part[:-3], int_part[-3:]
        head_groups = []
        while len(head) > 2:
            head_groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            head_groups.insert(0, head)
            int_part = ",".join(head_groups) + "," + tail
        else:
            int_part = ",".join(head_groups) + "," + tail
    formatted = f"₹{int_part}.{dec_part}" if dec_part else f"₹{int_part}"
    return f"-{formatted}" if is_negative else formatted


def format_pct(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "—"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def format_cr(crores: float | None) -> str:
    if crores is None:
        return "—"
    return f"₹{crores:.2f} Cr"


_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def format_month(month_str: str) -> str:
    """Convert "2026-04" → "April 2026"."""
    try:
        year, month = month_str.split("-")
        idx = int(month) - 1
        if 0 <= idx < 12:
            return f"{_MONTHS[idx]} {year}"
    except (ValueError, AttributeError):
        pass
    return month_str


def format_date_in(value: date | datetime | str | None) -> str:
    """Return DD Mon YYYY in en-IN style."""
    if value is None:
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value).date()
        except ValueError:
            return value
    if isinstance(value, datetime):
        value = value.date()
    return f"{value.day:02d} {_MONTHS[value.month - 1]} {value.year}"
