# STRATEGOS

A multi-scale geopolitical simulation engine with AI-driven autonomous agents, continuous time mechanics, and event sourcing architecture.

## Overview

STRATEGOS is a grand strategy wargame engine designed to model modern conflicts across military, economic, industrial, and social domains. Unlike traditional wargames, STRATEGOS uses AI agents as autonomous decision-makers at strategic, operational, and tactical levels, creating emergent scenarios without scripted events.

## Key Features

- **Continuous Time Simulation** - Variable speed control with full rewind/fast-forward capability
- **Event Sourcing Architecture** - Complete audit trail with deterministic replay from any point in time
- **Multi-Scale Modeling** - Seamless integration from tactical combat to strategic national decision-making
- **AI Agent Framework** - Autonomous agents with limited information, realistic fog of war, and adaptive decision-making
- **Multi-Domain Integration** - Military operations interconnected with economics, logistics, industry, and population health
- **Real-Time Streaming** - WebSocket-based event streaming for live simulation observation

## Architecture

- **Backend**: Python with FastAPI
- **Time Engine**: Custom continuous time simulation with checkpoint-based state management
- **Event Store**: PostgreSQL with event sourcing pattern
- **AI Integration**: LLM-based strategic reasoning + traditional AI for tactical/operational decisions
- **Spatial Engine**: Geospatial indexing for efficient proximity queries and movement
- **API**: RESTful endpoints + WebSocket streaming

## Planned Development Phases

1. **Time Engine + Event Sourcing** - Core temporal backbone with rewind/FF
2. **Spatial Layer** - Geography, entities, movement, and pathfinding
3. **Combat System** - Engagement mechanics and resolution
4. **AI Agents** - Autonomous tactical commanders
5. **Logistics** - Supply networks and resource management
6. **Economic Model** - National economies and industrial capacity
7. **Strategic AI** - National-level decision-making agents

Each phase delivers a runnable, independently valuable simulation capability.

## Use Cases

- **Analytical Wargaming** - Model hypothetical modern conflicts
- **Strategic Planning** - Explore multi-domain campaign dynamics
- **AI Research** - Study emergent behavior in multi-agent systems
- **Educational Tool** - Teach strategic thinking and systems analysis

## Project Status

🚧 **In Development** - Currently building Phase 1 (Time Engine + Event Sourcing)

## Development Setup

### Python Environment Isolation

This project uses a per-project virtual environment and a pinned Python version.

1. Ensure you have Python 3.12.10 available (pyenv recommended).
2. Create and activate the virtual environment:
   - Create: `python -m venv .venv`
   - Activate (macOS/Linux): `source .venv/bin/activate`

3. Install dependencies:
   - `pip install -r requirements.txt`

The workspace is configured to use `.venv` automatically in VS Code.

## Quick Start

### 🚀 One-Command Launch

The easiest way to start STRATEGOS:

```bash
# Using the launcher script (recommended)
python strategos.py

# Or using the shell wrapper (auto-activates venv)
./strategos.sh

# Or using Make
make ui
```

This will:
- ✅ Check your Python version and dependencies
- ✅ Create necessary directories
- ✅ Start the API server
- ✅ Open the web UI in your browser

### 📋 Other Launch Options

```bash
# Run tests first, then start
python strategos.py --test

# Run tests only
python strategos.py --test-only
make test

# Start without opening browser
python strategos.py --no-browser
make run

# Use custom port
python strategos.py --port 3000

# Run CLI demo
python strategos.py --demo
make demo

# Run interactive mode
python strategos.py --interactive
make interactive

# Skip environment checks
python strategos.py --skip-checks
```

## Running the Application

### Option 1: CLI Demo (Quick Test)

Run a simple demonstration of the simulation engine:

```bash
python run_simulation.py
```

Or run in interactive mode:

```bash
python run_simulation.py --interactive
```

Interactive commands:
- `start` - Start the simulation
- `stop` - Stop the simulation
- `pause` - Pause the simulation
- `resume` - Resume the simulation
- `status` - Show simulation status
- `marker <msg>` - Create a marker event
- `scale <n>` - Set time scale (e.g., `scale 2.0` for 2x speed)
- `quit` - Exit

### Option 2: FastAPI Server (Production)

Run the REST API + WebSocket server:

```bash
python api.py
```

Or with uvicorn directly:

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

API will be available at:
- **API Docs**: http://localhost:8000/docs
- **Root**: http://localhost:8000/
- **WebSocket**: ws://localhost:8000/ws/events

### REST API Endpoints

- `GET /` - API information
- `GET /status` - Get simulation status
- `POST /start` - Start simulation
- `POST /stop` - Stop simulation
- `POST /pause` - Pause simulation
- `POST /resume` - Resume simulation
- `POST /time-scale` - Change simulation speed
- `POST /seek` - Seek to specific time
- `POST /marker` - Create marker event
- `GET /events` - Query events from event store
- `WS /ws/events` - Real-time event stream

### Running Tests

```bash
pytest tests/
```

Run with coverage:

```bash
pytest --cov=core tests/
```

## Technology Stack

- Python 3.11+
- FastAPI
- PostgreSQL (event store)
- WebSockets
- Anthropic Claude API (for strategic AI agents)
- NumPy/SciPy (combat models and optimization)
- NetworkX (supply chain and trade networks)

## License

MIT License

## Author

Jim - Transformative leader with background in software development, artificial intelligence, and simulation systems
