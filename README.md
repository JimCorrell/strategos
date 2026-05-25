# STRATEGOS

A multi-scale geopolitical simulation engine with AI-driven autonomous agents, continuous time mechanics, and event sourcing architecture.

## Overview

STRATEGOS is a grand strategy wargame engine designed to model modern conflicts across military, economic, industrial, and social domains. Unlike traditional wargames, STRATEGOS uses AI agents as autonomous decision-makers at strategic, operational, and tactical levels, creating emergent scenarios without scripted events.

## Key Features

- **Continuous Time Simulation** - Variable speed control with full rewind/fast-forward capability
- **Event Sourcing Architecture** - Complete audit trail with deterministic replay from any point in time
- **Multi-Scale Modeling** - Seamless integration from tactical combat to strategic national decision-making
- **Faction System** - Blue/red/neutral factions with automatic engagement detection
- **Combat Engine** - Lanchester attrition model with health, firepower, armor, and morale per unit
- **Entity Iconology** - Distinct canvas shapes per unit type (chevron for aircraft, triangle for infantry, hull for tank)
- **Spawn UI** - Create entities directly from the browser with click-to-place positioning
- **Real-Time Streaming** - WebSocket-based event streaming for live observation of movement, combat, and destruction
- **AI Agent Framework** (planned) - Autonomous agents with limited information, realistic fog of war, and adaptive decision-making

## Architecture

- **Backend**: Python 3.12 with FastAPI
- **Time Engine**: Custom continuous time simulation with checkpoint-based state management
- **Event Store**: SQLite (aiosqlite) with event sourcing pattern — all state changes are events
- **Spatial Engine**: Geospatial indexing for efficient proximity queries and movement interpolation
- **Combat Engine**: 10Hz async loop, range-based engagement detection, Lanchester bidirectional attrition
- **API**: RESTful endpoints + WebSocket streaming
- **Frontend**: Vanilla JS, no build step, HTML5 Canvas

## Development Phases

1. ✅ **Phase 1 Complete** — Time Engine + Event Sourcing (rewind, fast-forward, deterministic replay)
2. ✅ **Phase 2 Complete** — Spatial Layer (entities, movement, canvas UI with real-time interpolation)
3. ✅ **Phase 3 Complete** — Combat System (factions, health/firepower/armor, engagement detection, Lanchester attrition, combat visualization, spawn UI)
4. 🚧 **Phase 4 Next** — AI Agents (autonomous tactical commanders)
5. **Phase 5** — Logistics (supply networks, resource management)
6. **Phase 6** — Economic Model (national economies, industrial capacity)
7. **Phase 7** — Strategic AI (national-level decision-making agents)

Each phase delivers a runnable, independently valuable simulation capability.

## Use Cases

- **Analytical Wargaming** - Model hypothetical modern conflicts
- **Strategic Planning** - Explore multi-domain campaign dynamics
- **AI Research** - Study emergent behavior in multi-agent systems
- **Educational Tool** - Teach strategic thinking and systems analysis

## Development Setup

### Python Environment Isolation

This project uses a per-project virtual environment and a pinned Python version.

1. Ensure you have Python 3.12+ available (pyenv recommended).
2. Create and activate the virtual environment:
   - Create: `python -m venv .venv`
   - Activate (macOS/Linux): `source .venv/bin/activate`

3. Install dependencies:
   - `pip install -r requirements.txt`

The workspace is configured to use `.venv` automatically in VS Code.

## Quick Start

### One-Command Launch

```bash
# Using the launcher script (recommended)
python strategos.py

# Or using the shell wrapper (auto-activates venv)
./strategos.sh

# Or using Make
make ui
```

This will:
- Check your Python version and dependencies
- Create necessary directories
- Start the API server
- Open the web UI in your browser

### Other Launch Options

```bash
# Run tests first, then start
python strategos.py --test

# Run tests only (fast — skips slow real-time movement tests)
make test

# Full test suite including movement integration tests
make test-all

# Start without opening browser
python strategos.py --no-browser

# Phase 3 combat demo (blue infantry vs red tanks)
python demo_phase3.py

# Run interactive CLI
python run_simulation.py --interactive
```

## REST API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /status | Simulation status |
| POST | /start | Start simulation |
| POST | /stop | Stop |
| POST | /pause | Pause |
| POST | /resume | Resume |
| POST | /time-scale | Change simulation speed |
| POST | /seek | Seek to specific time |
| POST | /marker | Create marker event |
| GET | /events | Query event log |
| POST | /entities | Create entity (faction + combat attrs) |
| GET | /entities | List all entities with current health |
| GET | /entities/{id} | Get single entity |
| POST | /entities/{id}/velocity | Set velocity |
| GET | /engagements | List active engagements |
| WS | /ws/events | Real-time event stream |

API docs at: http://localhost:8000/docs

## Technology Stack

- Python 3.12+
- FastAPI + uvicorn
- SQLite / aiosqlite (event store)
- pydantic-settings (configuration)
- structlog (logging)
- pytest-asyncio (tests)
- Vanilla JS + HTML5 Canvas (frontend, no build step)

## License

MIT License

## Author

Jim — Transformative leader with background in software development, artificial intelligence, and simulation systems
