# tests/test_combat_resolution.py

import pytest
from combat.resolution import calculate_damage


def _entity(firepower=10.0, armor=0.0):
    return {"firepower": firepower, "armor": armor}


def test_zero_armor_full_damage():
    dmg = calculate_damage(_entity(firepower=10.0), _entity(armor=0.0), dt=1.0)
    assert dmg == pytest.approx(10.0)


def test_armor_reduces_damage():
    # armor=5 → 50% reduction
    dmg = calculate_damage(_entity(firepower=10.0), _entity(armor=5.0), dt=1.0)
    assert dmg == pytest.approx(5.0)


def test_armor_capped_at_90_percent():
    # armor=100 → capped at 90% reduction, not 100%
    dmg = calculate_damage(_entity(firepower=10.0), _entity(armor=100.0), dt=1.0)
    assert dmg == pytest.approx(1.0)


def test_dt_scales_damage_linearly():
    dmg_1s = calculate_damage(_entity(firepower=10.0), _entity(armor=0.0), dt=1.0)
    dmg_2s = calculate_damage(_entity(firepower=10.0), _entity(armor=0.0), dt=2.0)
    assert dmg_2s == pytest.approx(dmg_1s * 2)


def test_zero_firepower_deals_no_damage():
    dmg = calculate_damage(_entity(firepower=0.0), _entity(armor=0.0), dt=1.0)
    assert dmg == 0.0


def test_damage_is_never_negative():
    dmg = calculate_damage(_entity(firepower=-5.0), _entity(armor=0.0), dt=1.0)
    assert dmg >= 0.0


def test_partial_dt():
    dmg = calculate_damage(_entity(firepower=10.0), _entity(armor=0.0), dt=0.1)
    assert dmg == pytest.approx(1.0)


def test_armor_10_gives_max_normal_reduction():
    # armor=10 → exactly 90% reduction (boundary of formula, not capped)
    dmg = calculate_damage(_entity(firepower=10.0), _entity(armor=10.0), dt=1.0)
    assert dmg == pytest.approx(1.0)
