# combat/attributes.py

"""Default combat attributes by unit type."""

UNIT_DEFAULTS: dict[str, dict] = {
    "infantry": {
        "health": 100.0,
        "max_health": 100.0,
        "firepower": 5.0,
        "armor": 1.0,
        "engagement_range": 50.0,
        "morale": 80.0,
    },
    "tank": {
        "health": 300.0,
        "max_health": 300.0,
        "firepower": 25.0,
        "armor": 7.0,
        "engagement_range": 200.0,
        "morale": 90.0,
    },
    "aircraft": {
        "health": 150.0,
        "max_health": 150.0,
        "firepower": 20.0,
        "armor": 2.0,
        "engagement_range": 300.0,
        "morale": 85.0,
    },
}

_FALLBACK: dict = {
    "health": 100.0,
    "max_health": 100.0,
    "firepower": 5.0,
    "armor": 1.0,
    "engagement_range": 100.0,
    "morale": 75.0,
}


def defaults_for_type(entity_type: str) -> dict:
    """Return a copy of default combat attributes for the given unit type."""
    return UNIT_DEFAULTS.get(entity_type, _FALLBACK).copy()


def merge_combat_attrs(
    entity_type: str,
    health: float | None = None,
    max_health: float | None = None,
    firepower: float | None = None,
    armor: float | None = None,
    engagement_range: float | None = None,
    morale: float | None = None,
) -> dict:
    """Return combat attributes, using per-type defaults for any unspecified values."""
    defaults = defaults_for_type(entity_type)
    attrs = {
        "health": health if health is not None else defaults["health"],
        "max_health": max_health if max_health is not None else defaults["max_health"],
        "firepower": firepower if firepower is not None else defaults["firepower"],
        "armor": armor if armor is not None else defaults["armor"],
        "engagement_range": engagement_range if engagement_range is not None else defaults["engagement_range"],
        "morale": morale if morale is not None else defaults["morale"],
    }
    # health can't exceed max_health
    attrs["health"] = min(attrs["health"], attrs["max_health"])
    return attrs
