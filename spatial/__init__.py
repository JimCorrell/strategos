# spatial/__init__.py

"""Spatial layer for STRATEGOS - Entities, movement, and geospatial indexing."""

from .entities import (
    Position,
    calculate_distance,
    calculate_distance_3d,
    create_entity_data,
    get_interpolated_position,
    normalize_vector,
    validate_position,
)
from .index import SpatialIndex
from .movement import MovementSystem

__all__ = [
    "SpatialIndex",
    "MovementSystem",
    "Position",
    "create_entity_data",
    "validate_position",
    "calculate_distance",
    "calculate_distance_3d",
    "normalize_vector",
    "get_interpolated_position",
]
