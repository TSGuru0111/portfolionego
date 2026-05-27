"""Aggregate all non-equity wealth buckets for one client into a WealthSnapshot.

Read-only. Falls back through live -> cached -> unavailable like
`services.market_data`. Not wired into `context_builder` in Phase 1.
"""
from __future__ import annotations
from datetime import date
from db import (
    mutual_funds_db,
    bonds_db,
    gold_db,
    cash_db,
    fds_db,
    insurance_db,
    liabilities_db,
    market_yields_db,
    nav_cache_db,
    gold_price_cache_db,
)
from models.wealth import (
    AssetBucket,
    InsuranceBucket,
    LiabilityBucket,
    WealthSnapshot,
)
from services.valuators.fd_valuator import value_fd
from services.valuators.liability_valuator import outstanding_balance
from services.valuators.bond_pricer import price_bond
from services.valuators.insurance_valuator import surrender_value


def _parse_date(s: str | date) -> date:
    if isinstance(s, date):
        return s
    return date.fromisoformat(s)


def _mf_bucket(client_id: str, stale: list[str]) -> AssetBucket:
    rows = mutual_funds_db.get_for_client(client_id)
    holdings, total, invested = [], 0.0, 0.0
    for r in rows:
        cache = nav_cache_db.get(r["scheme_code"])
        if cache:
            nav = float(cache["nav"])
            src = "cached"
        else:
            nav = float(r["purchase_nav"])
            src = "unavailable"
            stale.append("mutual_funds")
        units = float(r["units"])
        cur = units * nav
        inv = units * float(r["purchase_nav"])
        total += cur
        invested += inv
        holdings.append({**r, "current_nav": nav, "current_value": cur,
                         "invested_value": inv, "source": src})
    return AssetBucket(
        asset_class="mutual_funds",
        holdings=holdings,
        current_value=total,
        invested_value=invested,
        unrealised_gain=total - invested,
    )


def _gold_bucket(client_id: str, stale: list[str]) -> AssetBucket:
    rows = gold_db.get_for_client(client_id)
    holdings, total, invested = [], 0.0, 0.0
    for r in rows:
        cache = gold_price_cache_db.get_latest(r["purity"])
        if cache:
            ppg = float(cache["price_per_gram"])
        else:
            ppg = float(r["purchase_price_per_gram"])
            stale.append("gold")
        grams = float(r["weight_grams"])
        cur = grams * ppg
        inv = grams * float(r["purchase_price_per_gram"])
        total += cur
        invested += inv
        holdings.append({**r, "current_price_per_gram": ppg,
                         "current_value": cur, "invested_value": inv})
    return AssetBucket(
        asset_class="gold",
        holdings=holdings,
        current_value=total,
        invested_value=invested,
        unrealised_gain=total - invested,
    )


def _cash_bucket(client_id: str) -> AssetBucket:
    rows = cash_db.get_for_client(client_id)
    total = sum(float(r["balance"]) for r in rows)
    return AssetBucket(
        asset_class="cash",
        holdings=rows,
        current_value=total,
        invested_value=total,
        unrealised_gain=0.0,
    )


def _fd_bucket(client_id: str, as_of: date) -> AssetBucket:
    rows = fds_db.get_for_client(client_id)
    holdings, total, invested = [], 0.0, 0.0
    for r in rows:
        cur = value_fd(
            principal=float(r["principal"]),
            rate=float(r["rate_pct"]) / 100.0,
            start=_parse_date(r["start_date"]),
            compounding=r["compounding"],
            as_of=as_of,
        )
        inv = float(r["principal"])
        total += cur
        invested += inv
        holdings.append({**r, "current_value": cur, "invested_value": inv})
    return AssetBucket(
        asset_class="fixed_deposits",
        holdings=holdings,
        current_value=total,
        invested_value=invested,
        unrealised_gain=total - invested,
    )


def _bond_bucket(client_id: str, as_of: date, stale: list[str]) -> AssetBucket:
    rows = bonds_db.get_for_client(client_id)
    curve_rows = market_yields_db.get_curve("gsec")
    curve = [(float(r["tenor_years"]), float(r["yield_pct"])) for r in curve_rows]
    holdings, total, invested = [], 0.0, 0.0
    for r in rows:
        face = float(r["face_value"])
        units = float(r.get("units", 1))
        if curve:
            px = price_bond(
                face=face,
                coupon_pct=float(r["coupon_pct"]),
                maturity=_parse_date(r["maturity_date"]),
                as_of=as_of,
                curve=curve,
                spread_bps=int(r.get("credit_spread_bps", 0)),
                frequency=int(r.get("payment_frequency", 1)),
            )
        else:
            px = float(r.get("purchase_price", face))
            stale.append("bonds")
        cur = px * units
        inv = float(r.get("purchase_price", face)) * units
        total += cur
        invested += inv
        holdings.append({**r, "current_price": px, "current_value": cur,
                         "invested_value": inv})
    return AssetBucket(
        asset_class="bonds",
        holdings=holdings,
        current_value=total,
        invested_value=invested,
        unrealised_gain=total - invested,
    )


def _insurance_bucket(client_id: str, as_of: date) -> InsuranceBucket:
    rows = insurance_db.get_for_client(client_id)
    total_cover, total_surrender = 0.0, 0.0
    for r in rows:
        total_cover += float(r.get("sum_assured", 0.0))
        sv = surrender_value(
            policy_type=r["policy_type"],
            premium_amount=float(r["premium_amount"]),
            premium_frequency=r["premium_frequency"],
            start=_parse_date(r["start_date"]),
            as_of=as_of,
        )
        r["surrender_value"] = sv
        total_surrender += sv
    return InsuranceBucket(
        policies=rows,
        total_cover=total_cover,
        total_surrender_value=total_surrender,
    )


def _liability_bucket(client_id: str, as_of: date) -> LiabilityBucket:
    rows = liabilities_db.get_for_client(client_id)
    total = 0.0
    for r in rows:
        bal = outstanding_balance(
            principal=float(r["original_amount"]),
            rate=float(r["rate_pct"]) / 100.0,
            months=int(r["tenor_months"]),
            start=_parse_date(r["start_date"]),
            as_of=as_of,
            emi=float(r["emi"]) if r.get("emi") else None,
        )
        r["outstanding_balance"] = bal
        total += bal
    return LiabilityBucket(loans=rows, total_outstanding=total)


def build_wealth_snapshot(client_id: str, as_of: date | None = None) -> WealthSnapshot:
    """Build a full multi-asset wealth snapshot for one client."""
    if as_of is None:
        as_of = date.today()
    stale: list[str] = []
    mfs = _mf_bucket(client_id, stale)
    bonds = _bond_bucket(client_id, as_of, stale)
    gold = _gold_bucket(client_id, stale)
    cash = _cash_bucket(client_id)
    fds = _fd_bucket(client_id, as_of)
    insurance = _insurance_bucket(client_id, as_of)
    liabilities = _liability_bucket(client_id, as_of)

    asset_total = (
        mfs.current_value + bonds.current_value + gold.current_value
        + cash.current_value + fds.current_value
        + insurance.total_surrender_value
    )
    net_worth = asset_total - liabilities.total_outstanding
    allocation: dict[str, float] = {}
    if asset_total > 0:
        allocation = {
            "mutual_funds": mfs.current_value / asset_total,
            "bonds": bonds.current_value / asset_total,
            "gold": gold.current_value / asset_total,
            "cash": cash.current_value / asset_total,
            "fixed_deposits": fds.current_value / asset_total,
            "insurance": insurance.total_surrender_value / asset_total,
        }
    return WealthSnapshot(
        client_id=client_id,
        as_of=as_of.isoformat(),
        mutual_funds=mfs,
        bonds=bonds,
        gold=gold,
        cash=cash,
        fixed_deposits=fds,
        insurance=insurance,
        liabilities=liabilities,
        net_worth=net_worth,
        asset_allocation=allocation,
        has_stale_values=bool(stale),
        stale_sources=sorted(set(stale)),
    )
