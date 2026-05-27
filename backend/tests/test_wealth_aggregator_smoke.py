import os
import pytest
from datetime import date
from services.wealth_aggregator import build_wealth_snapshot
from db.supabase_client import get_supabase


_SKIP = pytest.mark.skipif(
    not os.getenv("SUPABASE_URL"),
    reason="needs live Supabase (set SUPABASE_URL + SUPABASE_KEY)",
)


@_SKIP
def test_smoke_build_snapshot_for_first_seed_client():
    sb = get_supabase()
    res = sb.table("clients").select("id").limit(1).execute()
    assert res.data, "no clients in DB — apply seed.sql + seed_v2.sql first"
    client_id = res.data[0]["id"]
    snap = build_wealth_snapshot(client_id, as_of=date.today())
    assert snap.client_id == client_id
    assert snap.net_worth is not None
    # At least one asset bucket should be populated for seeded clients.
    populated = [
        snap.mutual_funds.current_value, snap.bonds.current_value,
        snap.gold.current_value, snap.cash.current_value,
        snap.fixed_deposits.current_value,
    ]
    assert any(v > 0 for v in populated)
