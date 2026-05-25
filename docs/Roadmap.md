# STRATEGOS Development Phases

## Phase 1: Time Engine + Event Sourcing Foundation ✅ COMPLETE

### Goal

Build the temporal backbone - prove you can simulate, pause, rewind, and fast-forward with complete fidelity.

### Components

- `SimulationClock` with variable time scaling (1x, 10x, 100x, etc.)
- `EventStore` with append-only log and replay capability (SQLite via aiosqlite)
- `CheckpointStore` for efficient state reconstruction
- FastAPI endpoints for time control (play, pause, seek, scale)
- WebSocket streaming for real-time event delivery
- `EventHandlerRegistry` for type-specific event subscriptions
- `EventValidator` for event schema validation
- `StrategosConfig` via pydantic-settings
- Structured logging via structlog

### Success Criteria

- ✅ Variable time scaling works smoothly
- ✅ Rewind/fast-forward operations complete quickly
- ✅ Events persist and replay identically
- ✅ WebSocket clients receive event stream in real-time

### Value Proposition

A reusable event-sourcing framework suitable for any time-based simulation system.

---

## Phase 2: Spatial Layer + Basic Entities ✅ COMPLETE

### Goal

Add geography and movable entities to create a geospatial simulation foundation.

### Components

- `Entity` data model with position (x,y,z), velocity, heading, speed, max_speed
- `SpatialIndex` for proximity queries
- `MovementSystem` with real-time position interpolation (velocity × Δt)
- REST API: `POST /entities`, `GET /entities`, `GET /entities/{id}`, `POST /entities/{id}/velocity`
- 3-column canvas UI: sidebar controls / HTML5 canvas map / entity inspector
  - Zoom + pan, adaptive grid, faction/type-based entity colors
  - Entity list with click-to-select; inspector shows position, velocity, heading
  - Combat panel placeholder (grayed out, ready for Phase 3)

### Success Criteria

- ✅ Entities created and tracked in WorldState with full lifecycle events
- ✅ Velocity-based position interpolation between events (smooth canvas motion)
- ✅ Spatial queries via SpatialIndex
- ✅ Canvas renders entities in real-time via RAF loop
- ✅ Entity list + inspector cross-wired with canvas selection

### Value Proposition

A general-purpose geospatial simulation engine suitable for logistics, traffic, or movement modeling.

---

## Phase 3: Combat Resolution System 🚧 NEXT

### Goal

Enable entities to engage in combat with realistic mechanics and outcomes.

### Components

- Combat strength modeling (firepower, armor, range, morale)
- Engagement detection (line of sight, range bands, targeting)
- Resolution mechanics (Lanchester equations, attrition models, or Monte Carlo)
- Unit degradation (casualties reduce combat effectiveness)
- Combat event types (engagement started, shots fired, unit destroyed)
- Combat visualization (engagement lines, damage indicators)

### Deliverable

A combat engine where:

- Units automatically engage enemies in range
- Casualties accumulate realistically over time
- Combat effectiveness degrades with damage
- Outcomes are deterministic and replayable

### Runnable Demo

```python
# Create two opposing forces
# Watch them detect and engage each other
# Observe casualties and unit degradation
# Rewind and test different formations/tactics
```

### Success Criteria

- ✅ Attrition rates match historical combat data
- ✅ Combat outcomes feel plausible and balanced
- ✅ 100+ simultaneous engagements without performance degradation
- ✅ Morale and suppression affect combat effectiveness

### Value Proposition

A tactical wargame engine - publishable as "STRATEGOS: Combat Engine" with standalone value for military simulation.

---

## Phase 4: First AI Agent (Tactical Commander)

### Goal

Introduce autonomous decision-making agents that command units without player intervention.

### Components

- `Agent` base class with perception-decision-action loop
- Information filtering (fog of war, intelligence gathering)
- Goal and objective system
- Decision-making engine (rule-based or LLM-based)
- Agent personality/doctrine parameters
- Agent action events (orders issued, objectives changed)

### Deliverable

AI agents that:

- Perceive the battlefield through limited information
- Make tactical decisions based on objectives
- Issue movement and engagement orders to units
- Adapt to changing battlefield conditions

### Runnable Demo

```python
# Create two AI commanders with opposing objectives
# Watch them maneuver forces autonomously
# Observe emergent tactics (flanking, concentration of force)
# Inject new objectives mid-battle
# Compare different agent personalities/doctrines
```

### Success Criteria

- ✅ Agents make sensible tactical decisions
- ✅ Different agent personalities produce distinct behaviors
- ✅ System remains deterministic (same seed = same outcome)
- ✅ Agents respond appropriately to changing conditions

### Value Proposition

AI vs AI combat simulation - valuable for testing tactics, training scenarios, and studying emergent military behavior.

---

## Phase 5: Supply & Logistics Layer

### Goal

Add resource constraints and supply chain mechanics that affect combat operations.

### Components

- Supply network graph (depots, supply routes, transport capacity)
- Resource types (fuel, ammunition, food, spare parts)
- Consumption rates and stockpile tracking
- Supply routing algorithms (network flow optimization)
- Interdiction mechanics (destroying supply lines)
- Supply state visualization (flow diagrams, stockpile levels)

### Deliverable

A logistics system where:

- Units consume supplies during movement and combat
- Supply levels affect combat effectiveness and movement speed
- Supply lines can be cut or contested
- Logistics planning becomes strategically important

### Runnable Demo

```python
# Establish supply networks from rear areas to front lines
# Watch units consume fuel and ammunition
# Cut a critical supply route and observe unit degradation
# See how logistics constraints affect operational tempo
```

### Success Criteria

- ✅ Supply state visibly affects combat performance
- ✅ Network flow algorithms handle complex supply graphs
- ✅ Supply visualization clearly shows bottlenecks
- ✅ Realistic consumption rates based on historical data

### Value Proposition

Operational-level wargaming with logistics - this level of fidelity matches or exceeds most commercial wargames.

---

## Phase 6: Economic Model Integration

### Goal

Add national economies that produce resources, fund military operations, and suffer from war damage.

### Components

- National economy state (GDP, industrial capacity, resource extraction)
- Production queues (building units costs resources and time)
- Economic damage model (combat destroys productive capacity)
- Trade networks between nations
- Economic policy decisions (spending priorities, mobilization)
- Economic indicators and visualization

### Deliverable

An economic system where:

- Nations have productive economies that generate resources
- Military operations consume economic output
- Combat damages economic infrastructure
- Economic strength determines sustainable military force

### Runnable Demo

```python
# Initialize nations with different economic profiles
# Watch military production consume economic capacity
# Conduct campaign that damages industrial centers
# Observe weakened economy reducing military replacement rates
# See economic recovery over time
```

### Success Criteria

- ✅ Economic output drives military sustainability
- ✅ War has measurable economic costs
- ✅ Economic damage and recovery modeled realistically
- ✅ Trade and resource flow affects national capabilities

### Value Proposition

Grand strategy simulation - moves beyond pure military conflict into economic-military interaction.

---

## Phase 7: Strategic AI Agents

### Goal

AI agents that make national-level decisions about war, peace, resource allocation, and grand strategy.

### Components

- Strategic-level agent (national leader/government role)
- Multi-domain decision-making (military + economic + diplomatic considerations)
- LLM integration for complex strategic reasoning
- Goal hierarchies (strategic goals → operational objectives → tactical tasks)
- Diplomatic mechanics (alliances, treaties, negotiations)
- Strategic decision events and reasoning logs

### Deliverable

Strategic AI that:

- Decides when to go to war or seek peace
- Allocates economic resources between military and civilian needs
- Plans multi-domain campaigns
- Forms and breaks alliances based on interests
- Adapts strategy based on changing conditions

### Runnable Demo

```python
# Initialize multiple AI-controlled nations
# Watch them make strategic decisions autonomously
# Observe emergent alliances and conflicts
# See how AI balances guns vs. butter
# Inject crises and watch strategic responses
```

### Success Criteria

- ✅ Strategic decisions are coherent and goal-directed
- ✅ Different nations pursue distinct strategies
- ✅ System generates interesting scenarios without scripting
- ✅ AI reasoning is explainable and debuggable

### Value Proposition

Fully autonomous grand strategy simulation - unprecedented capability for exploring geopolitical scenarios and multi-domain conflict dynamics.

---

## Phase 8+: Future Expansion

### Potential Future Phases

- **Phase 8**: Population health and social stability modeling
- **Phase 9**: Intelligence and information warfare
- **Phase 10**: Nuclear weapons and escalation dynamics
- **Phase 11**: Climate and environmental factors
- **Phase 12**: Cyber warfare domain
- **Phase 13**: Space domain operations
- **Phase 14**: Multi-player human-AI hybrid mode
- **Phase 15**: Scenario editor and modding tools

Each future phase maintains the principle: independently valuable, runnable, and builds incrementally on prior work.
