from services.risk_profile import target_for, TARGET_ALLOCATION_BY_RISK


def test_target_for_conservative():
    assert target_for("conservative") == {"equity": 30, "debt": 60, "cash": 10}


def test_target_for_moderate():
    assert target_for("moderate") == {"equity": 50, "debt": 40, "cash": 10}


def test_target_for_aggressive():
    assert target_for("aggressive") == {"equity": 70, "debt": 25, "cash": 5}


def test_target_for_case_insensitive():
    assert target_for("Aggressive") == target_for("aggressive")


def test_target_for_none_defaults_moderate():
    assert target_for(None) == TARGET_ALLOCATION_BY_RISK["moderate"]


def test_target_for_unknown_defaults_moderate():
    assert target_for("gambler") == TARGET_ALLOCATION_BY_RISK["moderate"]


def test_buckets_sum_to_100():
    for bucket in TARGET_ALLOCATION_BY_RISK.values():
        assert sum(bucket.values()) == 100
