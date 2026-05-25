#!/usr/bin/env python3
"""Phase 3 demo: two opposing forces engage and take casualties."""

import asyncio
from core.simulation import Simulation
from core.logging import configure_logging

configure_logging()


async def main():
    sim = Simulation(db_path="demo_phase3.db", checkpoint_dir="checkpoints/demo3")
    await sim.initialize()
    await sim.start(time_scale=5.0)

    print("\n=== STRATEGOS Phase 3 — Combat Demo ===\n")

    # Blue force: 3 infantry at x=0
    blue_ids = []
    for i in range(3):
        eid = await sim.create_entity(
            "infantry", (float(i * 10), 0.0, 0.0),
            faction="blue",
            engagement_range=150.0,
        )
        blue_ids.append(eid)
        print(f"  [BLUE] Infantry {str(eid)[:8]} created at ({i*10}, 0)")

    # Red force: 2 tanks at x=100
    red_ids = []
    for i in range(2):
        eid = await sim.create_entity(
            "tank", (100.0 + float(i * 15), 0.0, 0.0),
            faction="red",
            engagement_range=200.0,
        )
        red_ids.append(eid)
        print(f"  [RED]  Tank     {str(eid)[:8]} created at ({100 + i*15}, 0)")

    print("\nForces in range — combat begins...\n")

    # Subscribe to key events for live reporting
    engagement_log = []
    damage_log = []
    destroyed_log = []

    async def on_engagement(event):
        if event.event_type.value == "engagement.started":
            a = event.data["entity_a"][:8]
            b = event.data["entity_b"][:8]
            t = event.simulation_time
            engagement_log.append(f"  [t={t:.2f}s] ENGAGE  {a}… ⚔  {b}…")

    async def on_damaged(event):
        eid = event.data["entity_id"][:8]
        dmg = event.data["damage"]
        hp  = event.data["health_after"]
        t   = event.simulation_time
        damage_log.append(f"  [t={t:.2f}s] DAMAGE  {eid}… -{dmg:.1f}hp → {hp:.1f}hp remaining")

    async def on_destroyed(event):
        eid = event.data["entity_id"][:8]
        t   = event.simulation_time
        destroyed_log.append(f"  [t={t:.2f}s] DESTROYED {eid}…")

    from core.events import EventType
    sim.on_event(EventType.ENGAGEMENT_STARTED, on_engagement)
    sim.on_event(EventType.ENTITY_DAMAGED,     on_damaged)
    sim.on_event(EventType.UNIT_DESTROYED,     on_destroyed)

    # Run for 5 simulation seconds (1s real @ 5x scale)
    for tick in range(10):
        await asyncio.sleep(0.2)
        t = sim.clock.get_time()

        alive_blue = [eid for eid in blue_ids if sim.get_entity(eid)]
        alive_red  = [eid for eid in red_ids  if sim.get_entity(eid)]
        active_engagements = sim.get_engagements()

        print(f"t={t:.1f}s | Blue: {len(alive_blue)}/3 | Red: {len(alive_red)}/2 | Engagements: {len(active_engagements)}")

        if not alive_blue or not alive_red:
            print("\n  Combat over — one side eliminated!")
            break

    await sim.stop()

    # Print event summary
    print("\n--- Engagement Events ---")
    for line in engagement_log[:10]:
        print(line)

    print(f"\n--- Damage Events ({len(damage_log)} total) ---")
    for line in damage_log[:15]:
        print(line)
    if len(damage_log) > 15:
        print(f"  ... ({len(damage_log) - 15} more)")

    print("\n--- Destroyed ---")
    for line in destroyed_log:
        print(line)

    print("\n=== Demo complete ===")
    await sim.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
