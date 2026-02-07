# core/checkpoints.py (updated)

from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path
import pickle
from .exceptions import CheckpointCreationError, CheckpointNotFoundError, CheckpointRestoreError
from .logging import get_logger

logger = get_logger(__name__)


@dataclass
class Checkpoint:
    """Snapshot of world state at a specific time."""

    simulation_time: float
    state_data: bytes  # Pickled state
    checkpoint_id: str = field(default="")
    metadata: dict = field(default_factory=dict)

    def deserialize_state(self) -> Any:
        """Restore state object from bytes."""
        return pickle.loads(self.state_data)

    @classmethod
    def create(
        cls, simulation_time: float, state: Any, metadata: dict | None = None
    ) -> "Checkpoint":
        """Create checkpoint from state object."""
        checkpoint_id = f"checkpoint_{simulation_time:.6f}"
        logger.info(
            "checkpoint.created",
            simulation_time=simulation_time,
            checkpoint_id=checkpoint_id,
            state_size_bytes=len(pickle.dumps(state)),
        )
        return cls(
            simulation_time=simulation_time,
            state_data=pickle.dumps(state),
            checkpoint_id=checkpoint_id,
            metadata=metadata or {},
        )


class CheckpointStore:
    """Manages state snapshots for fast rewind."""

    def __init__(self, checkpoint_dir: str, checkpoint_interval: float = 1000.0):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_interval = checkpoint_interval
        self.logger = get_logger(f"{__name__}.CheckpointStore")

        self.logger.info("checkpoint_store.initialized", checkpoint_interval=checkpoint_interval)

    async def save(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint to disk.

        Args:
            checkpoint: Checkpoint to save

        Raises:
            CheckpointCreationError: If checkpoint cannot be saved
        """
        try:
            filename = self.checkpoint_dir / f"checkpoint_{checkpoint.simulation_time:.6f}.pkl"
            with open(filename, "wb") as f:
                pickle.dump(checkpoint, f)

            self.logger.info(
                "checkpoint.saved",
                simulation_time=checkpoint.simulation_time,
            )
        except Exception as e:
            self.logger.error(
                "checkpoint.save_failed",
                simulation_time=checkpoint.simulation_time,
                error=str(e),
            )
            raise CheckpointCreationError(
                f"Failed to save checkpoint at time {checkpoint.simulation_time}: {e}"
            ) from e

    async def create_checkpoint(
        self, simulation_time: float, state: Any, metadata: dict | None = None
    ) -> Checkpoint:
        """Create and save a checkpoint."""
        checkpoint = Checkpoint.create(simulation_time, state, metadata)
        await self.save(checkpoint)
        return checkpoint

    async def get_nearest_before(self, simulation_time: float) -> Optional[Checkpoint]:
        """Get the most recent checkpoint before the target time.

        Args:
            simulation_time: Target time to search for

        Returns:
            Nearest checkpoint before target time, or None if not found

        Raises:
            CheckpointRestoreError: If checkpoint file exists but cannot be loaded
        """
        try:
            checkpoints = []
            for filename in self.checkpoint_dir.glob("checkpoint_*.pkl"):
                try:
                    ts_str = filename.stem.replace("checkpoint_", "")
                    ts = float(ts_str)
                    if ts <= simulation_time:
                        checkpoints.append((ts, filename))
                except ValueError:
                    continue

            if not checkpoints:
                self.logger.debug("checkpoint.not_found", target_time=simulation_time)
                return None

            # Get the nearest one
            checkpoints.sort(reverse=True)
            _, filename = checkpoints[0]

            with open(filename, "rb") as f:
                checkpoint = pickle.load(f)

            self.logger.debug(
                "checkpoint.retrieved",
                checkpoint_time=checkpoint.simulation_time,
                target_time=simulation_time,
            )
            return checkpoint
        except Exception as e:
            self.logger.error(
                "checkpoint.restore_failed",
                target_time=simulation_time,
                error=str(e),
            )
            raise CheckpointRestoreError(
                f"Failed to restore checkpoint for time {simulation_time}: {e}"
            ) from e

    async def restore_checkpoint(self, checkpoint_id: str) -> Any:
        """Restore and return the state from a checkpoint.

        Args:
            checkpoint_id: ID of checkpoint to restore

        Returns:
            Deserialized state object

        Raises:
            CheckpointNotFoundError: If checkpoint does not exist
            CheckpointRestoreError: If checkpoint cannot be loaded
        """
        filename = self.checkpoint_dir / f"{checkpoint_id}.pkl"
        if not filename.exists():
            raise CheckpointNotFoundError(f"Checkpoint {checkpoint_id} not found")

        try:
            with open(filename, "rb") as f:
                checkpoint = pickle.load(f)

            return checkpoint.deserialize_state()
        except Exception as e:
            self.logger.error(
                "checkpoint.restore_failed",
                checkpoint_id=checkpoint_id,
                error=str(e),
            )
            raise CheckpointRestoreError(
                f"Failed to restore checkpoint {checkpoint_id}: {e}"
            ) from e

    def get_nearest_checkpoint(self, simulation_time: float) -> Optional[Checkpoint]:
        """Get the most recent checkpoint at or before the target time (alias for get_nearest_before)."""
        return self.get_nearest_before(simulation_time)

    async def list_checkpoints(self) -> list[Checkpoint]:
        """List all available checkpoints."""
        checkpoints = []
        for filename in self.checkpoint_dir.glob("checkpoint_*.pkl"):
            try:
                with open(filename, "rb") as f:
                    checkpoint = pickle.load(f)
                    checkpoints.append(checkpoint)
            except Exception as e:
                self.logger.warning("checkpoint.load_failed", filename=str(filename), error=str(e))

        checkpoints.sort(key=lambda c: c.simulation_time)
        return checkpoints

    async def delete_checkpoint(self, checkpoint_id_or_time: float | str) -> None:
        """Delete a specific checkpoint by ID or simulation time.

        Args:
            checkpoint_id_or_time: Either a checkpoint ID (str) or simulation time (float)
        """
        if isinstance(checkpoint_id_or_time, str):
            # It's a checkpoint_id
            filename = self.checkpoint_dir / f"{checkpoint_id_or_time}.pkl"
        else:
            # It's a simulation_time (float)
            filename = self.checkpoint_dir / f"checkpoint_{checkpoint_id_or_time:.6f}.pkl"

        if filename.exists():
            filename.unlink()
            self.logger.info("checkpoint.deleted", identifier=str(checkpoint_id_or_time))

    async def cleanup_old_checkpoints(self, keep_count: int = 10) -> None:
        """Keep only the most recent N checkpoints."""
        checkpoints = await self.list_checkpoints()
        if len(checkpoints) <= keep_count:
            return

        # Delete oldest checkpoints
        to_delete = checkpoints[:-keep_count]
        for checkpoint in to_delete:
            await self.delete_checkpoint(checkpoint.simulation_time)

    def should_create_checkpoint(self, simulation_time: float) -> bool:
        """Determine if we should create a checkpoint based on simulation time."""
        if abs(simulation_time) < 1e-9:
            return True  # Always checkpoint at start

        # Check if we've crossed a checkpoint interval boundary
        remainder = simulation_time % self.checkpoint_interval
        return abs(remainder) < 1e-9 or abs(remainder - self.checkpoint_interval) < 1e-9

    def set_interval(self, new_interval: int) -> None:
        """Update checkpoint interval."""
        old_interval = self.checkpoint_interval
        self.checkpoint_interval = new_interval
        self.logger.info(
            "checkpoint_interval.changed", old_interval=old_interval, new_interval=new_interval
        )
