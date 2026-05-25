# combat/__init__.py

from combat.attributes import UNIT_DEFAULTS, defaults_for_type, merge_combat_attrs
from combat.resolution import calculate_damage
from combat.system import CombatSystem

__all__ = [
    "CombatSystem",
    "UNIT_DEFAULTS",
    "defaults_for_type",
    "merge_combat_attrs",
    "calculate_damage",
]
