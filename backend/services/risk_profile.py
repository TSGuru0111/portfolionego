"""Maps client.risk_profile to a target equity/debt/cash allocation.

v2 stop-gap before clients.target_allocation JSONB column lands.
Adjust the percentages in TARGET_ALLOCATION_BY_RISK if firm policy changes.
"""
from __future__ import annotations

TARGET_ALLOCATION_BY_RISK: dict[str, dict[str, int]] = {
    "conservative": {"equity": 30, "debt": 60, "cash": 10},
    "moderate":     {"equity": 50, "debt": 40, "cash": 10},
    "aggressive":   {"equity": 70, "debt": 25, "cash":  5},
}

_DEFAULT_BUCKET = "moderate"


def target_for(risk_profile: str | None) -> dict[str, int]:
    """Return the target allocation dict for a risk profile.

    Unknown or null profiles default to 'moderate'. Case-insensitive lookup.
    """
    if not risk_profile:
        return TARGET_ALLOCATION_BY_RISK[_DEFAULT_BUCKET]
    return TARGET_ALLOCATION_BY_RISK.get(
        risk_profile.lower(),
        TARGET_ALLOCATION_BY_RISK[_DEFAULT_BUCKET],
    )
