# STRATEGOS — Claude Code Guide

## What This Project Is

STRATEGOS is a multi-scale geopolitical wargame simulation engine. It models conflict across military, economic, industrial, and social domains using AI agents, event sourcing, and continuous time mechanics.

The architecture is designed so each phase delivers a standalone, runnable capability. Phases build incrementally.

## Current Status

- **Phase 1** (Time Engine + Event Sourcing): Complete
- **Phase 2** (Spatial Layer + Entities + Movement): Complete
- **Phase 3** (Combat System): Complete
- **Phase 4** (AI Agents): Next

## Project Layout

```
core/               # Simulation engine
  config.py         # StrategosConfig (pydantic-settings, STRATEGOS_ env prefix)
  simulation.py     # Simulation orchestrator — entry point for most logic
  state.py          # WorldState — entity registry + engagement tracking
  time.py           # SimulationClock — variable time scaling
  event_store.py    # EventStore — SQLite append-only log via aiosqlite
  events.py         # Event dataclass (frozen), EventType enum, EventValidator
  event_handlers.py # EventHandlerRegistry — type-specific subscriptions
  checkpoints.py    # CheckpointStore — binary snapshots for fast seek
  exceptions.py     # Domain exceptions
  logging.py        # structlog configuration

spatial/            # Phase 2: Geospatial layer
  entities.py       # Entity data schema + create_entity_data() (includes combat fields)
  index.py          # SpatialIndex — proximity queries
  movement.py       # MovementSystem — position interpolation, velocity

combat/             # Phase 3: Combat system
  __init__.py       # Exports CombatSystem, UNIT_DEFAULTS, defaults_for_type, calculate_damage
  attributes.py     # Default stats by unit type (health, firepower, armor, engagement_range, morale)
  resolution.py     # calculate_damage() — Lanchester-inspired attrition formula
  system.py         # CombatSystem — async 10Hz loop, engagement detection + resolution

api.py              # FastAPI app — REST + WebSocket, lifespan startup
static/             # Vanilla JS frontend (no build step)
  index.html        # 3-column grid layout with spawn panel + combat panel
  styles.css
  app.js            # ApiClient, WebSocketClient, EntityStore, CanvasRenderer,
                    # SidebarController, RightPanelController, SpawnController, StrategosApp

tests/              # pytest-asyncio, full coverage of core + spatial + combat
  test_combat_attributes.py   # Unit defaults, override params
  test_combat_resolution.py   # calculate_damage() math, armor clamping
  test_combat_system.py       # Engagement detection, bidirectional damage, unit destruction
  test_phase3.py              # End-to-end: opposing forces → casualties + events
strategos.py        # One-command launcher (checks deps, starts API, opens browser)
strategos.sh        # Shell wrapper that activates .venv first
run_simulation.py   # CLI demo / interactive mode
demo_phase2b.py     # Phase 2 entity + movement demo
demo_phase3.py      # Phase 3 combat demo: blue infantry vs red tanks
Makefile            # make ui / make test / make demo / make run
```

## Running the Project

```bash
# Activate venv first
source .venv/bin/activate

# Full UI (recommended)
python strategos.py          # starts API + opens browser
# or
make ui

# Tests — default (fast, excludes slow movement integration tests)
make test
# or directly:
.venv/bin/python -m pytest tests/ -k "not test_movement" -v

# Full test suite including slow real-time movement/replay tests
make test-all

# Phase 3 combat demo (two opposing squads fight to conclusion)
python demo_phase3.py

# CLI demo
make demo
python run_simulation.py --interactive
```

> **Note on test speed**: `test_movement.py` and `test_movement_replay.py` use real-time `asyncio.sleep()` calls and take 30–60s to run. The default `make test` skips them with `-k "not test_movement"`. Run `make test-all` when you need to verify movement behavior or before a release.

Default API: http://localhost:8000  
WebSocket: ws://localhost:8000/ws/events  
Swagger docs: http://localhost:8000/docs

## Architecture Patterns

**Event sourcing**: All state changes are events appended to the EventStore (SQLite). State is rebuilt from events + checkpoints. Never mutate state directly — emit an event.

**Time travel**: `SimulationClock` drives simulation time independently of wall time. `CheckpointStore` snapshots state periodically so `seek()` can reconstruct any point in <1s.

**Entity lifecycle**: Entities live in `WorldState.entities` (dict keyed by UUID). Created via `simulation.create_entity()`, which emits `entity.created`. Position is interpolated by `MovementSystem` between events. Destroyed via `simulation.destroy_entity()`, which emits `entity.destroyed`.

**Combat system**: `CombatSystem` runs a 10Hz async loop. Each tick it queries `SpatialIndex` for enemies in range, emits `engagement.started`/`engagement.ended` for state transitions, applies bidirectional Lanchester attrition (`entity.damaged`), and calls `destroy_entity()` when health ≤ 0 (`unit.destroyed`). Active engagements are transient state in `CombatSystem._engagements`; the event log is the durable record.

**Event handlers**: Register via `EventHandlerRegistry.on(event_type, handler)`. Handlers are called by the simulation loop; they should be async and fast.

**API → Simulation**: `api.py` holds a global `simulation` instance initialized in the FastAPI lifespan. All routes check `if not simulation` before use.

**Frontend data flow**:
- Page load → `GET /entities` → `EntityStore.loadSnapshot` → canvas fit
- `GET /status` + `GET /engagements` poll (2s) → sidebar update + combat panel refresh
- WebSocket `entity.moved` → `EntityStore` update (no list refresh; canvas RAF reads directly)
- WebSocket `entity.created/destroyed` → list refresh
- WebSocket `entity.damaged` → `EntityStore` health update → canvas health bar redraws
- WebSocket `engagement.started/ended` → engagement list update

## Key APIs

```python
# Start simulation and create opposing forces
await simulation.start()

# Blue tank at (0,0), red infantry at (100,0) — they will engage automatically
blue = await simulation.create_entity("tank", [0.0, 0.0, 0.0], faction="blue", max_speed=15.0)
red  = await simulation.create_entity("infantry", [100.0, 0.0, 0.0], faction="red", max_speed=5.0)

# Set velocity toward each other
await simulation.set_entity_velocity(blue, (-5.0, 0.0, 0.0))
await simulation.set_entity_velocity(red,  (5.0, 0.0, 0.0))

# Query active engagements
engagements = simulation.get_engagements()

# Emit a custom event
event = await simulation.emit_event("custom.event", {"key": "value"})

# Subscribe to events
simulation._event_handlers.on("entity.damaged", my_async_handler)

# Seek (rewind/FF)
await simulation.seek(target_time=42.5)
```

## REST Endpoints (Phase 1 + 2 + 3)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /status | Simulation status |
| POST | /start | Start simulation |
| POST | /stop | Stop simulation |
| POST | /pause | Pause |
| POST | /resume | Resume |
| POST | /time-scale | Set speed multiplier |
| POST | /seek | Jump to simulation time |
| POST | /marker | Create timestamped marker |
| GET | /events | Query event log |
| POST | /entities | Create entity (with faction + combat attrs) |
| GET | /entities | List all entities (interpolated positions + health) |
| GET | /entities/{id} | Get single entity |
| POST | /entities/{id}/velocity | Set velocity |
| GET | /engagements | List active engagements |
| WS | /ws/events | Real-time event stream |

## Combat Attributes (Phase 3)

Default stats by unit type:

| Type | Health | Firepower | Armor | Range |
|------|--------|-----------|-------|-------|
| infantry | 100 | 5.0 | 1.0 | 50 |
| tank | 300 | 25.0 | 7.0 | 200 |
| aircraft | 150 | 20.0 | 2.0 | 300 |

Attrition formula: `damage = firepower × (1 − min(armor/10, 0.9)) × dt`

Factions: `"blue"`, `"red"`, `"neutral"`. Only entities of different non-neutral factions engage.

## Event Types

| Event | Key Data |
|-------|----------|
| `entity.created` | id, type, position, faction, health, firepower, armor, engagement_range, morale |
| `entity.moved` | id, position, velocity, heading |
| `entity.destroyed` | id |
| `engagement.started` | entity_a, entity_b, started_at |
| `engagement.ended` | entity_a, entity_b |
| `entity.damaged` | entity_id, damage, new_health, attacker_id |
| `unit.destroyed` | entity_id, killer_id |

## Development Notes

- Python 3.12, virtual env at `.venv/`
- `aiosqlite` for SQLite (not PostgreSQL — config.py has Postgres fields but the running code uses `db_path`)
- `pydantic-settings` for config — env vars use `STRATEGOS_` prefix
- `structlog` for all logging — use `get_logger(__name__)`, not stdlib logging
- `pytest-asyncio` with `asyncio_mode = "auto"` — no need to mark tests with `@pytest.mark.asyncio`
- Tests use `tmp_path` fixtures for isolated SQLite DBs; no mocking of the database
- Frontend is vanilla JS, no build step, no framework

## Phase 4 Preview (AI Agents)

Next phase adds:
- `Agent` base class with perception-decision-action loop
- Information filtering (fog of war, limited sensor range)
- Goal and objective system
- Decision engine (rule-based or LLM-based)
- Agent action events (orders issued, objectives changed)
- Agents issue movement and engagement orders to units autonomously

See `docs/Roadmap.md` for full phase definitions.
