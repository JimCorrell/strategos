# tests/test_phase3.py — end-to-end Phase 3 integration test

import asyncio
import pytest


@pytest.fixture
async def running_sim(simulation):
    await simulation.start()
    yield simulation
    if simulation._running:
        await simulation.stop()


async def test_two_opposing_forces_engage_and_take_casualties(running_sim):
    """Full Phase 3 scenario: blue infantry vs red infantry, nearby."""
    sim = running_sim

    blue_ids = [
        await sim.create_entity(
            "infantry", (i * 5.0, 0.0, 0.0),
            faction="blue", engagement_range=200.0
        )
        for i in range(3)
    ]

    red_ids = [
        await sim.create_entity(
            "infantry", (100.0 + i * 5.0, 0.0, 0.0),
            faction="red", engagement_range=200.0
        )
        for i in range(3)
    ]

    # Let combat run for 1 second (10 ticks)
    await asyncio.sleep(1.2)

    # At least some engagements should have fired
    events = await sim.event_store.get_events(from_time=0.0)
    event_types = {
        (e.event_type.value if hasattr(e.event_type, "value") else e.event_type)
        for e in events
    }

    assert "engagement.started" in event_types, "Expected engagement.started events"
    assert "entity.damaged" in event_types, "Expected entity.damaged events"


async def test_engagement_ended_when_entity_destroyed(running_sim):
    """Verify that destroying a unit ends its engagements."""
    sim = running_sim

    victim = await sim.create_entity(
        "infantry", (0.0, 0.0, 0.0), faction="blue",
        health=1.0, max_health=1.0, armor=0.0, engagement_range=500.0
    )
    killer = await sim.create_entity(
        "tank", (10.0, 0.0, 0.0), faction="red",
        firepower=500.0, engagement_range=500.0
    )

    await asyncio.sleep(1.0)

    # Victim should be gone
    assert sim.get_entity(victim) is None

    # No engagements involving the destroyed unit
    for key in sim.state.engagements:
        assert victim not in key


async def test_entity_combat_attrs_stored_in_state(running_sim):
    """Verify all combat attributes are present in entity state."""
    sim = running_sim

    eid = await sim.create_entity(
        "tank", (0.0, 0.0, 0.0),
        faction="blue",
        health=200.0, max_health=300.0,
        firepower=30.0, armor=8.0,
        engagement_range=250.0, morale=95.0,
    )

    entity = sim.get_entity(eid)
    assert entity["faction"] == "blue"
    assert entity["health"] == 200.0
    assert entity["max_health"] == 300.0
    assert entity["firepower"] == 30.0
    assert entity["armor"] == 8.0
    assert entity["engagement_range"] == 250.0
    assert entity["morale"] == 95.0


async def test_get_engagements_returns_active(running_sim):
    """get_engagements() reflects current active engagements."""
    sim = running_sim

    a = await sim.create_entity("infantry", (0.0, 0.0, 0.0), faction="blue", engagement_range=200.0)
    b = await sim.create_entity("infantry", (50.0, 0.0, 0.0), faction="red", engagement_range=200.0)

    await asyncio.sleep(0.8)

    engs = sim.get_engagements()
    assert len(engs) == 1
    eng = engs[0]
    assert "entity_a" in eng and "entity_b" in eng


async def test_neutral_units_not_in_engagements(running_sim):
    sim = running_sim
    await sim.create_entity("infantry", (0.0, 0.0, 0.0), faction="neutral", engagement_range=500.0)
    await sim.create_entity("infantry", (5.0, 0.0, 0.0),  faction="neutral", engagement_range=500.0)

    await asyncio.sleep(0.5)

    assert len(sim.get_engagements()) == 0
