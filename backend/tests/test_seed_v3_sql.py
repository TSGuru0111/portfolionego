"""Lightweight smoke test for seed_v3.sql — checks structure, not execution."""
from pathlib import Path

SEED = Path(__file__).parent.parent / "db_schema" / "seed_v3.sql"


def test_seed_v3_exists():
    assert SEED.exists(), "seed_v3.sql missing"


def test_seed_v3_has_five_onboarding_events():
    sql = SEED.read_text()
    assert sql.count("'onboarding'") == 5


def test_seed_v3_has_five_allocation_targets():
    sql = SEED.read_text()
    assert sql.lower().count("insert into allocation_targets") == 5


def test_seed_v3_references_all_five_demo_clients():
    sql = SEED.read_text()
    for uid in ("d62e9583", "e46486d4", "410834b9", "a5ab55c8", "5c406920"):
        assert uid in sql, f"missing demo client {uid}"


def test_seed_v3_uses_psql_rm_id_variable():
    sql = SEED.read_text()
    assert ":rm_id" in sql
