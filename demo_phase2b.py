#!/usr/bin/env python3
"""Demo script for Phase 2b: Movement System.

Demonstrates:
- Creating entities
- Setting velocities
- Watching entities move
- Position interpolation
"""

import asyncio
from pathlib import Path

from core.simulation import Simulation


async def main():
    print("🎯 STRATEGOS Phase 2b Demo: Movement System\n")

    # Create simulation
    sim = Simulation(
        db_path="demo_phase2b.db",
        checkpoint_dir="checkpoints",
    )
    await sim.initialize()
    await sim.start()

    print("✅ Simulation started\n")

    # Create a few entities
    print("📍 Creating entities...")
    entity1 = await sim.create_entity(
        entity_type="infantry",
        position=(0.0, 0.0, 0.0),
    )
    print(f"  • Infantry unit at origin: {entity1}")

    entity2 = await sim.create_entity(
        entity_type="tank",
        position=(100.0, 0.0, 0.0),
    )
    print(f"  • Tank unit at (100, 0, 0): {entity2}")

    entity3 = await sim.create_entity(
        entity_type="aircraft",
        position=(0.0, 100.0, 50.0),
    )
    print(f"  • Aircraft at (0, 100, 50): {entity3}\n")

    # Set velocities
    print("🚀 Setting velocities...")
    await sim.set_entity_velocity(entity1, velocity=(10.0, 0.0, 0.0))
    print("  • Infantry moving at 10 m/s along X axis")

    await sim.set_entity_velocity(entity2, velocity=(-15.0, 0.0, 0.0))
    print("  • Tank moving at -15 m/s along X axis (toward infantry)")

    await sim.set_entity_velocity(entity3, velocity=(5.0, -10.0, 0.0))
    print("  • Aircraft moving at (5, -10, 0) m/s\n")

    # Watch movement for 3 seconds
    print("⏱️  Watching movement for 3 seconds...\n")

    for i in range(7):
        await asyncio.sleep(0.5)

        t = sim.clock.get_time()
        pos1 = sim.get_entity_position(entity1)
        pos2 = sim.get_entity_position(entity2)
        pos3 = sim.get_entity_position(entity3)

        print(f"t={t:.1f}s")
        print(f"  Infantry: ({pos1[0]:.1f}, {pos1[1]:.1f}, {pos1[2]:.1f})")
        print(f"  Tank:     ({pos2[0]:.1f}, {pos2[1]:.1f}, {pos2[2]:.1f})")
        print(f"  Aircraft: ({pos3[0]:.1f}, {pos3[1]:.1f}, {pos3[2]:.1f})")

        # Calculate distance between infantry and tank
        distance = abs(pos1[0] - pos2[0])
        print(f"  Distance between infantry & tank: {distance:.1f}m\n")

    # Test time rewind
    print("⏪ Rewinding to t=1.0s...")
    await sim.seek(1.0)

    pos1 = sim.get_entity_position(entity1)
    pos2 = sim.get_entity_position(entity2)
    pos3 = sim.get_entity_position(entity3)

    print(f"After rewind to t=1.0s:")
    print(f"  Infantry: ({pos1[0]:.1f}, {pos1[1]:.1f}, {pos1[2]:.1f})")
    print(f"  Tank:     ({pos2[0]:.1f}, {pos2[1]:.1f}, {pos2[2]:.1f})")
    print(f"  Aircraft: ({pos3[0]:.1f}, {pos3[1]:.1f}, {pos3[2]:.1f})\n")

    # Test spatial queries
    print("🔍 Spatial query at (50, 0, 0) with radius 60m...")
    results = sim.query_entities_in_radius((50.0, 0.0, 0.0), radius=60.0)
    print(f"  Found {len(results)} entities: {[str(e)[:8] for e in results]}\n")

    # Stop movement
    print("🛑 Stopping infantry...")
    await sim.set_entity_velocity(entity1, velocity=(0.0, 0.0, 0.0))

    await asyncio.sleep(1.0)

    pos1_stopped = sim.get_entity_position(entity1)
    print(f"  Infantry stopped at: ({pos1_stopped[0]:.1f}, {pos1_stopped[1]:.1f}, {pos1_stopped[2]:.1f})\n")

    # Cleanup
    print("✅ Phase 2b Demo Complete!")
    print(f"   Total simulation time: {sim.clock.get_time():.2f}s")
    print(f"   Total events: {sim.state.event_count}")
    print(f"   Movement system: {sim.movement_system.frame_count} frames processed")

    await sim.shutdown()

    # Cleanup demo files
    Path("demo_phase2b.db").unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
