# spatial/entities.py

"""Entity schema utilities for spatial layer."""

from typing import Any
from uuid import UUID


# Type alias for position
Position = tuple[float, float, float]


def validate_position(position: Any) -> Position:
    """Validate and normalize position to (x, y, z) tuple.

    Args:
        position: Position data (list, tuple, or dict with x/y/z keys)

    Returns:
        Normalized (x, y, z) tuple

    Raises:
        ValueError: If position format is invalid
    """
    if isinstance(position, (list, tuple)):
        if len(position) == 2:
            return (float(position[0]), float(position[1]), 0.0)
        elif len(position) == 3:
            return (float(position[0]), float(position[1]), float(position[2]))
        else:
            raise ValueError(f"Position must have 2 or 3 coordinates, got {len(position)}")
    elif isinstance(position, dict):
        x = position.get("x", position.get("X"))
        y = position.get("y", position.get("Y"))
        z = position.get("z", position.get("Z", 0.0))
        if x is None or y is None:
            raise ValueError("Position dict must have 'x' and 'y' keys")
        return (float(x), float(y), float(z))
    else:
        raise ValueError(f"Invalid position type: {type(position)}")


def create_entity_data(
    entity_id: UUID,
    entity_type: str,
    position: Position,
    max_speed: float = 10.0,
    metadata: dict | None = None,
    simulation_time: float = 0.0,
) -> dict[str, Any]:
    """Create entity data dictionary with all required fields.

    Args:
        entity_id: Unique entity identifier
        entity_type: Entity type (e.g., "infantry", "tank")
        position: Initial (x, y, z) position
        max_speed: Maximum speed in m/s
        metadata: Optional additional metadata
        simulation_time: Current simulation time

    Returns:
        Complete entity data dictionary
    """
    return {
        "entity_id": str(entity_id),
        "type": entity_type,
        "position": position,
        "velocity": (0.0, 0.0, 0.0),
        "heading": 0.0,  # radians, 0 = north
        "speed": 0.0,  # current speed m/s
        "max_speed": float(max_speed),
        "created_at": simulation_time,
        "destroyed_at": None,
        "waypoints": [],
        "metadata": metadata or {},
        "last_update_time": simulation_time,
    }


def calculate_distance(pos1: Position, pos2: Position) -> float:
    """Calculate Euclidean distance between two positions (ignoring Z).

    Args:
        pos1: First position (x, y, z)
        pos2: Second position (x, y, z)

    Returns:
        Distance in same units as positions
    """
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    return (dx * dx + dy * dy) ** 0.5


def calculate_distance_3d(pos1: Position, pos2: Position) -> float:
    """Calculate 3D Euclidean distance between two positions.

    Args:
        pos1: First position (x, y, z)
        pos2: Second position (x, y, z)

    Returns:
        3D distance in same units as positions
    """
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    dz = pos2[2] - pos1[2]
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def normalize_vector(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    """Normalize a 3D vector to unit length.

    Args:
        vector: (x, y, z) vector

    Returns:
        Normalized (x, y, z) vector
    """
    magnitude = (vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2) ** 0.5
    if magnitude == 0:
        return (0.0, 0.0, 0.0)
    return (vector[0] / magnitude, vector[1] / magnitude, vector[2] / magnitude)


def get_interpolated_position(
    position: Position,
    velocity: tuple[float, float, float],
    last_update_time: float,
    current_time: float,
) -> Position:
    """Calculate interpolated position based on velocity.

    Args:
        position: Last known position
        velocity: Velocity vector (m/s)
        last_update_time: Time of last position update
        current_time: Current simulation time

    Returns:
        Interpolated (x, y, z) position
    """
    dt = current_time - last_update_time
    return (
        position[0] + velocity[0] * dt,
        position[1] + velocity[1] * dt,
        position[2] + velocity[2] * dt,
    )
