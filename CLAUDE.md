# STRATEGOS — Claude Code Guide

## What This Project Is

STRATEGOS is a multi-scale geopolitical wargame simulation engine. It models conflict across military, economic, industrial, and social domains using AI agents, event sourcing, and continuous time mechanics.

The architecture is designed so each phase delivers a standalone, runnable capability. Phases build incrementally.

## Current Status

- **Phase 1** (Time Engine + Event Sourcing): Complete
- **Phase 2** (Spatial Layer + Entities + Movement): Complete
- **Phase 3** (Combat System): Next

## Project Layout

```
core/               # Simulation engine
  config.py         # StrategosConfig (pydantic-settings, STRATEGOS_ env prefix)
  simulation.py     # Simulation orchestrator — entry point for most logic
  state.py          # WorldState — entity registry
  time.py           # SimulationClock — variable time scaling
  event_store.py    # EventStore — SQLite append-only log via aiosqlite
  events.py         # Event dataclass (frozen), EventType enum, EventValidator
  event_handlers.py # EventHandlerRegistry — type-specific subscriptions
  checkpoints.py    # CheckpointStore — binary snapshots for fast seek
  exceptions.py     # Domain exceptions
  logging.py        # structlog configuration

spatial/            # Phase 2: Geospatial layer
  entities.py       # Entity data schema + create_entity_data()
  index.py          # SpatialIndex — proximity queries
  movement.py       # MovementSystem — position interpolation, velocity

api.py              # FastAPI app — REST + WebSocket, lifespan startup
static/             # Vanilla JS frontend (no build step)
  index.html        # 3-column grid layout
  styles.css
  app.js            # ApiClient, WebSocketClient, EntityStore, CanvasRenderer,
                    # SidebarController, RightPanelController, StrategosApp

tests/              # pytest-asyncio, full coverage of core + spatial
strategos.py        # One-command launcher (checks deps, starts API, opens browser)
strategos.sh        # Shell wrapper that activates .venv first
run_simulation.py   # CLI demo / interactive mode
demo_phase2b.py     # Phase 2 entity + movement demo
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

# Tests
make test
# or
pytest tests/

# CLI demo
make demo
python run_simulation.py --interactive
```

Default API: http://localhost:8000  
WebSocket: ws://localhost:8000/ws/events  
Swagger docs: http://localhost:8000/docs

## Architecture Patterns

**Event sourcing**: All state changes are events appended to the EventStore (SQLite). State is rebuilt from events + checkpoints. Never mutate state directly — emit an event.

**Time travel**: `SimulationClock` drives simulation time independently of wall time. `CheckpointStore` snapshots state periodically so `seek()` can reconstruct any point in <1s.

**Entity lifecycle**: Entities live in `WorldState.entities` (dict keyed by UUID). Created via `simulation.create_entity()`, which emits `entity.created`. Position is interpolated by `MovementSystem` between events.

**Event handlers**: Register via `EventHandlerRegistry.on(event_type, handler)`. Handlers are called by the simulation loop; they should be async and fast.

**API → Simulation**: `api.py` holds a global `simulation` instance initialized in the FastAPI lifespan. All routes check `if not simulation` before use.

**Frontend data flow**:
- Page load → `GET /entities` → `EntityStore.loadSnapshot` → canvas fit
- `GET /status` poll (2s) → sidebar update + canvas `simTime` sync
- WebSocket `entity.moved` → `EntityStore` update (no list refresh; canvas RAF reads directly)
- WebSocket `entity.created/destroyed` → list refresh

## Key APIs

```python
# Start simulation and create an entity
await simulation.start()
entity_id = await simulation.create_entity("tank", [0.0, 0.0, 0.0], max_speed=15.0)
await simulation.set_entity_velocity(entity_id, (5.0, 3.0, 0.0))

# Emit a custom event
event = await simulation.emit_event("custom.event", {"key": "value"})

# Subscribe to events
simulation._event_handlers.on("entity.moved", my_async_handler)

# Seek (rewind/FF)
await simulation.seek(target_time=42.5)
```

## REST Endpoints (Phase 1 + 2)

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
| POST | /entities | Create entity |
| GET | /entities | List all entities (interpolated positions) |
| GET | /entities/{id} | Get single entity |
| POST | /entities/{id}/velocity | Set velocity |
| WS | /ws/events | Real-time event stream |

## Development Notes

- Python 3.12, virtual env at `.venv/`
- `aiosqlite` for SQLite (not PostgreSQL — config.py has Postgres fields but the running code uses `db_path`)
- `pydantic-settings` for config — env vars use `STRATEGOS_` prefix
- `structlog` for all logging — use `get_logger(__name__)`, not stdlib logging
- `pytest-asyncio` with `asyncio_mode = "auto"` — no need to mark tests with `@pytest.mark.asyncio`
- Tests use `tmp_path` fixtures for isolated SQLite DBs; no mocking of the database
- Frontend is vanilla JS, no build step, no framework

## Phase 3 Preview (Combat System)

Next phase adds:
- `CombatStrength` attributes on entities (firepower, armor, range, morale)
- Engagement detection (range + line of sight)
- Attrition resolution (Lanchester equations)
- New event types: `engagement.started`, `shots.fired`, `unit.destroyed`
- Combat visualization in the right panel (currently a grayed-out placeholder in the UI)

See `docs/Roadmap.md` for full phase definitions.
