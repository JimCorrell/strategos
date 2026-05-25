# tests/test_combat_system.py

import asyncio
import pytest
from uuid import UUID


async def _wait(sim, seconds: float = 0.5, steps: int = 10):
    """Let the simulation run for a bit."""
    await asyncio.sleep(seconds)


async def _tick_n(sim, n: int = 5):
    """Sleep long enough for ~n combat ticks (10Hz → 0.1s each)."""
    await asyncio.sleep(n * 0.12)


@pytest.fixture
async def running_sim(simulation):
    await simulation.start()
    yield simulation
    if simulation._running:
        await simulation.stop()


async def test_combat_system_initializes(simulation):
    assert simulation.combat_system is not None


async def test_combat_system_starts_and_stops(simulation):
    await simulation.start()
    assert simulation.combat_system.running
    await simulation.stop()
    assert not simulation.combat_system.running


async def test_entities_created_with_faction(running_sim):
    sim = running_sim
    eid = await sim.create_entity("infantry", (0.0, 0.0, 0.0), faction="blue")
    entity = sim.get_entity(eid)
    assert entity["faction"] == "blue"


async def test_entities_created_with_combat_attrs(running_sim):
    sim = running_sim
    eid = await sim.create_entity("tank", (0.0, 0.0, 0.0), faction="blue")
    entity = sim.get_entity(eid)
    assert entity["health"] > 0
    assert entity["firepower"] > 0
    assert entity["armor"] >= 0
    assert entity["engagement_range"] > 0


async def test_no_engagement_same_faction(running_sim):
    sim = running_sim
    # Two blue units right on top of each other — should not engage
    a = await sim.create_entity("infantry", (0.0, 0.0, 0.0), faction="blue", engagement_range=500.0)
    b = await sim.create_entity("infantry", (1.0, 0.0, 0.0), faction="blue", engagement_range=500.0)

    await _tick_n(sim, 5)

    assert len(sim.get_engagements()) == 0


async def test_no_engagement_out_of_range(running_sim):
    sim = running_sim
    # Blue and red but very far apart relative to range
    a = await sim.create_entity("infantry", (0.0, 0.0, 0.0), faction="blue", engagement_range=10.0)
    b = await sim.create_entity("infantry", (1000.0, 0.0, 0.0), faction="red", engagement_range=10.0)

    await _tick_n(sim, 5)

    assert len(sim.get_engagements()) == 0


async def test_engagement_detected_when_in_range(running_sim):
    sim = running_sim
    # Blue and red within each other's range
    a = await sim.create_entity("infantry", (0.0, 0.0, 0.0), faction="blue", engagement_range=100.0)
    b = await sim.create_entity("infantry", (50.0, 0.0, 0.0), faction="red", engagement_range=100.0)

    await _tick_n(sim, 5)

    assert len(sim.get_engagements()) == 1


async def test_engagement_tracking_in_world_state(running_sim):
    sim = running_sim
    a = await sim.create_entity("infantry", (0.0, 0.0, 0.0), faction="blue", engagement_range=100.0)
    b = await sim.create_entity("infantry", (50.0, 0.0, 0.0), faction="red", engagement_range=100.0)

    await _tick_n(sim, 5)

    assert len(sim.state.engagements) == 1
    key = next(iter(sim.state.engagements))
    eng = sim.state.engagements[key]
    assert "entity_a" in eng
    assert "entity_b" in eng
    assert "started_at" in eng


async def test_damage_reduces_health(running_sim):
    sim = running_sim
    # High firepower red tank vs weak blue infantry in range
    a = await sim.create_entity(
        "infantry", (0.0, 0.0, 0.0), faction="blue",
        health=100.0, engagement_range=200.0, armor=0.0
    )
    b = await sim.create_entity(
        "tank", (10.0, 0.0, 0.0), faction="red",
        engagement_range=200.0
    )

    initial_health = sim.get_entity(a)["health"]
    await _tick_n(sim, 10)

    entity = sim.get_entity(a)
    if entity:  # might have been destroyed
        assert entity["health"] < initial_health
    # Either destroyed or damaged — both are correct outcomes


async def test_unit_destroyed_when_health_zero(running_sim):
    sim = running_sim
    # Very weak unit vs strong attacker — should be destroyed
    victim = await sim.create_entity(
        "infantry", (0.0, 0.0, 0.0), faction="blue",
        health=1.0, max_health=1.0, armor=0.0, engagement_range=500.0
    )
    attacker = await sim.create_entity(
        "tank", (5.0, 0.0, 0.0), faction="red",
        firepower=100.0, engagement_range=500.0
    )

    await _tick_n(sim, 8)

    # Victim should be gone
    assert sim.get_entity(victim) is None


async def test_neutral_entities_never_engage(running_sim):
    sim = running_sim
    a = await sim.create_entity("infantry", (0.0, 0.0, 0.0), faction="neutral", engagement_range=500.0)
    b = await sim.create_entity("tank",     (5.0, 0.0, 0.0),  faction="red",     engagement_range=500.0)

    await _tick_n(sim, 5)

    assert len(sim.get_engagements()) == 0
