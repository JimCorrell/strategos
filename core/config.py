# core/config.py

from pydantic_settings import BaseSettings
from typing import Optional


class StrategosConfig(BaseSettings):
    """Configuration for STRATEGOS simulation engine."""

    # Database
    database_url: str = "postgresql://strategos:strategos@localhost:5432/strategos"
    database_pool_min_size: int = 10
    database_pool_max_size: int = 20

    # Checkpointing
    checkpoint_interval: int = 1000  # Events between checkpoints

    # Time
    default_time_scale: float = 1.0

    # Logging
    log_level: str = "INFO"

    # Simulation
    simulation_update_rate: float = 0.016  # ~60 FPS

    class Config:
        env_file = ".env"
        env_prefix = "STRATEGOS_"


# Global config instance
config = StrategosConfig()
