# tests/test_phase1.py

import asyncio
import tempfile
import shutil
from pathlib import Path
from uuid import uuid4
from core.event_store import EventStore
from core.checkpoints import CheckpointStore
from core.simulation import Simulation
from core.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def test_basic_flow():
    """Test basic simulation flow: start, events, pause, rewind."""

    # Create temporary directories
    temp_dir = Path(tempfile.mkdtemp())
    db_path = str(temp_dir / "test.db")
    checkpoint_dir = str(temp_dir / "checkpoints")
    Path(checkpoint_dir).mkdir()

    try:
        # Create simulation
        sim = Simulation(
            db_path=db_path,
            checkpoint_dir=checkpoint_dir,
            checkpoint_interval=10.0,  # Lower for testing
            time_scale=10.0,  # Fast for testing
        )

        await sim.initialize()

        logger.info("test.starting", test="basic_flow")

        # Start simulation
        await sim.start()

        # Let it run and create some markers
        for i in range(5):
            await asyncio.sleep(0.5)  # Real time
            await sim.create_marker(f"marker_{i}", {"index": i})
            logger.info("marker.created", index=i, sim_time=sim.clock.get_time())

        current_time = sim.clock.get_time()
        logger.info("simulation.running", current_time=current_time)

        # Pause
        await sim.pause()
        logger.info("simulation.paused")

        # Rewind to halfway point
        rewind_target = current_time / 2
        logger.info("rewinding", target=rewind_target)
        await sim.seek(rewind_target)

        assert abs(sim.clock.get_time() - rewind_target) < 0.1, "Rewind failed"
        logger.info("rewind.success", final_time=sim.clock.get_time())

        # Fast forward past original point
        ff_target = current_time * 1.5
        logger.info("fast_forwarding", target=ff_target)
        await sim.seek(ff_target)

        assert abs(sim.clock.get_time() - ff_target) < 0.1, "Fast forward failed"
        logger.info("fast_forward.success", final_time=sim.clock.get_time())

        # Change time scale
        await sim.set_time_scale(100.0)
        logger.info("time_scale.changed", new_scale=100.0)

        logger.info("test.completed", test="basic_flow", result="PASSED")

    finally:
        await sim.shutdown()
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_checkpoint_system():
    """Test that checkpoints enable fast rewind."""

    # Create temporary directories
    temp_dir = Path(tempfile.mkdtemp())
    db_path = str(temp_dir / "test.db")
    checkpoint_dir = str(temp_dir / "checkpoints")
    Path(checkpoint_dir).mkdir()

    try:
        sim = Simulation(
            db_path=db_path,
            checkpoint_dir=checkpoint_dir,
            checkpoint_interval=100.0,
            time_scale=1000.0,
        )

        await sim.initialize()

        await sim.start()

        logger.info("test.starting", test="checkpoint_system")

        # Generate 500 events (should create 5 checkpoints)
        for i in range(500):
            await sim.create_marker(f"event_{i}", {"index": i})
            if i % 100 == 0:
                logger.info("progress", events_created=i)

        final_time = sim.clock.get_time()
        await sim.pause()

        # Time a rewind with checkpoints
        import time

        start = time.time()
        await sim.seek(final_time * 0.5)
        rewind_duration = time.time() - start

        logger.info(
            "rewind.performance",
            duration_seconds=rewind_duration,
            events_total=500,
            target_time=final_time * 0.5,
        )

        # Should be fast (< 1 second for 500 events)
        assert rewind_duration < 1.0, f"Rewind too slow: {rewind_duration}s"

        logger.info("test.completed", test="checkpoint_system", result="PASSED")

    finally:
        await sim.shutdown()
        shutil.rmtree(temp_dir, ignore_errors=True)


async def main():
    """Run all Phase 1 tests."""
    from core.config import config

    configure_logging(log_level=config.log_level)

    logger.info("strategos.tests.starting", phase="phase_1")

    await test_basic_flow()
    await test_checkpoint_system()

    logger.info("strategos.tests.completed", phase="phase_1", result="ALL PASSED")


if __name__ == "__main__":
    asyncio.run(main())
