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
