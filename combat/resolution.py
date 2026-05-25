# combat/resolution.py

"""Lanchester-inspired attrition model for combat resolution."""


def calculate_damage(attacker: dict, target: dict, dt: float) -> float:
    """Compute damage dealt by attacker to target over time interval dt.

    Uses a simplified Lanchester model:
        damage = firepower × (1 − armor_reduction) × dt

    Armor stat (0–10) maps linearly to 0%–90% damage reduction.
    Capped at 90% so no unit is ever immune.

    Args:
        attacker: Entity data dict (must have "firepower")
        target: Entity data dict (must have "armor")
        dt: Simulated time elapsed in seconds

    Returns:
        Damage amount (always >= 0)
    """
    armor = target.get("armor", 0.0)
    armor_reduction = min(armor / 10.0, 0.9)
    firepower = attacker.get("firepower", 0.0)
    return max(0.0, firepower * (1.0 - armor_reduction) * dt)
