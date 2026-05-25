# tests/test_combat_attributes.py

import pytest
from combat.attributes import defaults_for_type, merge_combat_attrs, UNIT_DEFAULTS


def test_known_types_have_defaults():
    for unit_type in ("infantry", "tank", "aircraft"):
        d = defaults_for_type(unit_type)
        assert d["health"] > 0
        assert d["firepower"] > 0
        assert d["armor"] >= 0
        assert d["engagement_range"] > 0
        assert d["morale"] > 0


def test_unknown_type_returns_fallback():
    d = defaults_for_type("unknown_unit")
    assert d["health"] == 100.0
    assert d["engagement_range"] == 100.0


def test_defaults_are_copies():
    a = defaults_for_type("tank")
    b = defaults_for_type("tank")
    a["health"] = 999
    assert b["health"] != 999


def test_merge_uses_defaults_for_none():
    merged = merge_combat_attrs("infantry")
    expected = defaults_for_type("infantry")
    assert merged["health"] == expected["health"]
    assert merged["firepower"] == expected["firepower"]


def test_merge_overrides_when_provided():
    merged = merge_combat_attrs("infantry", health=50.0, firepower=99.0)
    assert merged["health"] == 50.0
    assert merged["firepower"] == 99.0
    # Other fields still use defaults
    assert merged["armor"] == defaults_for_type("infantry")["armor"]


def test_merge_clamps_health_to_max_health():
    merged = merge_combat_attrs("infantry", health=999.0, max_health=100.0)
    assert merged["health"] == 100.0


def test_tank_has_more_health_than_infantry():
    tank = defaults_for_type("tank")
    inf = defaults_for_type("infantry")
    assert tank["health"] > inf["health"]


def test_tank_has_higher_armor_than_infantry():
    tank = defaults_for_type("tank")
    inf = defaults_for_type("infantry")
    assert tank["armor"] > inf["armor"]
