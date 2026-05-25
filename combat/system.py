# combat/system.py

"""CombatSystem: 10Hz engagement detection and Lanchester attrition resolution."""

import asyncio
import time
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from core.events import EventType
from core.logging import get_logger
from combat.resolution import calculate_damage

if TYPE_CHECKING:
    from core.simulation import Simulation

logger = get_logger(__name__)

_UPDATE_RATE = 10  # Hz


class CombatSystem:
    """Manages combat engagement detection and damage resolution.

    Runs at 10Hz. Each tick:
    1. Scans for enemy pairs within weapon range (via SpatialIndex).
    2. Emits engagement.started / engagement.ended events for state changes.
    3. Applies bidirectional damage via entity.damaged events.
    4. Destroys units whose health reaches zero.
    """

    def __init__(self, simulation: "Simulation"):
        self.simulation = simulation
        self.running = False
        self.update_task: Optional[asyncio.Task] = None
        self._frame_time = 1.0 / _UPDATE_RATE

        # Transient set of active engagement pair keys — rebuilt each tick.
        # Key: tuple(sorted(UUID, UUID))
        self._engagements: set[tuple[UUID, UUID]] = set()

        # Guard against re-entrant destruction within a single tick
        self._destroying: set[UUID] = set()

    async def initialize(self) -> None:
        logger.info("CombatSystem initialized", update_rate_hz=_UPDATE_RATE)

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.update_task = asyncio.create_task(self._update_loop())
        logger.info("CombatSystem started")

    async def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
            self.update_task = None
        logger.info("CombatSystem stopped")

    async def _update_loop(self) -> None:
        try:
            while self.running:
                frame_start = time.perf_counter()
                await self._tick()
                elapsed = time.perf_counter() - frame_start
                await asyncio.sleep(max(0.0, self._frame_time - elapsed))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("CombatSystem loop error", error=str(e), exc_info=True)
            self.running = False

    async def _tick(self) -> None:
        sim = self.simulation
        if not sim._running:
            return

        dt = self._frame_time * sim.clock.time_scale
        current_time = sim.clock.get_time()
        entities = sim.state.entities

        if not entities:
            return

        # Compute current engagement pairs from range checks
        new_pairs: set[tuple[UUID, UUID]] = set()

        for entity_id, entity in list(entities.items()):
            if entity_id in self._destroying:
                continue
            faction = entity.get("faction", "neutral")
            if faction == "neutral":
                continue

            eng_range = entity.get("engagement_range", 0.0)
            if eng_range <= 0:
                continue

            pos = sim.get_entity_position(entity_id)
            if pos is None:
                continue

            nearby = sim.query_entities_in_radius(pos, eng_range)
            for other_id in nearby:
                if other_id == entity_id or other_id in self._destroying:
                    continue
                other = entities.get(other_id)
                if other is None:
                    continue
                other_faction = other.get("faction", "neutral")
                if other_faction == "neutral" or other_faction == faction:
                    continue
                # Enemy in range — record pair (canonically sorted)
                pair: tuple[UUID, UUID] = (min(entity_id, other_id), max(entity_id, other_id))
                new_pairs.add(pair)

        # Emit engagement.started for newly detected pairs
        for pair in new_pairs - self._engagements:
            a_id, b_id = pair
            await sim.emit_event(
                EventType.ENGAGEMENT_STARTED,
                {
                    "entity_a": str(a_id),
                    "entity_b": str(b_id),
                    "started_at": current_time,
                },
            )
            logger.debug("engagement.started", entity_a=str(a_id), entity_b=str(b_id))

        # Emit engagement.ended for pairs that left range
        for pair in self._engagements - new_pairs:
            a_id, b_id = pair
            if a_id not in self._destroying and b_id not in self._destroying:
                await sim.emit_event(
                    EventType.ENGAGEMENT_ENDED,
                    {
                        "entity_a": str(a_id),
                        "entity_b": str(b_id),
                        "ended_at": current_time,
                        "reason": "out_of_range",
                    },
                )
                logger.debug("engagement.ended", entity_a=str(a_id), entity_b=str(b_id))

        self._engagements = new_pairs

        # Apply bidirectional damage to all active pairs
        for pair in list(new_pairs):
            a_id, b_id = pair
            if a_id in self._destroying or b_id in self._destroying:
                continue
            entity_a = entities.get(a_id)
            entity_b = entities.get(b_id)
            if entity_a is None or entity_b is None:
                continue

            dmg_to_b = calculate_damage(entity_a, entity_b, dt)
            dmg_to_a = calculate_damage(entity_b, entity_a, dt)

            await self._apply_damage(a_id, b_id, entity_a, dmg_to_a, current_time)
            await self._apply_damage(b_id, a_id, entity_b, dmg_to_b, current_time)

        self._destroying.clear()

    async def _apply_damage(
        self,
        target_id: UUID,
        attacker_id: UUID,
        target: dict,
        damage: float,
        current_time: float,
    ) -> None:
        """Emit entity.damaged and, if health hits zero, destroy the unit."""
        if target_id in self._destroying:
            return
        if damage <= 0:
            return

        health_before = target.get("health", 0.0)
        health_after = max(0.0, health_before - damage)

        await self.simulation.emit_event(
            EventType.ENTITY_DAMAGED,
            {
                "entity_id": str(target_id),
                "attacker_id": str(attacker_id),
                "damage": round(damage, 4),
                "health_before": round(health_before, 4),
                "health_after": round(health_after, 4),
            },
        )

        if health_after <= 0:
            self._destroying.add(target_id)
            await self.simulation.emit_event(
                EventType.UNIT_DESTROYED,
                {
                    "entity_id": str(target_id),
                    "attacker_id": str(attacker_id),
                },
            )
            await self.simulation.destroy_entity(target_id)
            logger.info(
                "unit.destroyed",
                entity_id=str(target_id),
                attacker_id=str(attacker_id),
            )
