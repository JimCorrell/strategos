# Phase 4: AI Agents — Tactical Commander

## Context

Phases 1–3 are complete: time engine, spatial layer, and combat system all running. Phase 4 adds autonomous tactical commanders — AI agents that perceive the battlefield through a limited sensor range and issue movement and engagement orders to all units of their faction. Each agent runs a rule-based decision loop (2Hz), with an optional LLM override per doctrine that calls the Anthropic API.

Design decisions confirmed with user:
- **Decision engine**: Rule-based by default; `doctrine.decision_engine = "llm"` routes through Claude API with rule-based fallback on failure
- **Perception**: Sensor range (partial information) — agents see enemies only within `doctrine.sensor_range` of any friendly unit. No full omniscience.
- **Agent granularity**: One `TacticalAgent` per faction, commanding all friendly units on that side

---

## New Module: `agents/`

```
agents/
  __init__.py     # exports AgentSystem, TacticalAgent, AgentDoctrine, DOCTRINE_PRESETS
  doctrine.py     # AgentDoctrine dataclass + preset configs
  agent.py        # TacticalAgent — perception, rule-based decide, LLM decide, execute
  system.py       # AgentSystem — async 2Hz loop, manages all agents
```

### `agents/doctrine.py`

```python
@dataclass
class AgentDoctrine:
    name: str = "balanced"
    aggression: float = 0.7          # 0=passive, 1=always advance
    retreat_threshold: float = 0.25  # Health fraction that triggers retreat
    sensor_range: float = 500.0      # Max perception radius (units)
    decision_engine: str = "rules"   # "rules" | "llm"

DOCTRINE_PRESETS = {
    "aggressive":  AgentDoctrine(name="aggressive",  aggression=0.95, retreat_threshold=0.10),
    "balanced":    AgentDoctrine(name="balanced",    aggression=0.70, retreat_threshold=0.25),
    "defensive":   AgentDoctrine(name="defensive",   aggression=0.30, retreat_threshold=0.50),
    "llm":         AgentDoctrine(name="llm",         aggression=0.70, retreat_threshold=0.25, decision_engine="llm"),
}
```

### `agents/agent.py` — TacticalAgent

**`_perceive() -> dict`**
1. Gather all alive friendly units from `sim.state.entities`
2. For each friendly unit, call `sim.query_entities_in_radius(pos, sensor_range)`
3. Union of results → deduplicated enemy entities = `visible_enemies`
4. Return `{friendly, visible_enemies, sim_time}`

**`_rule_based_decide(perception) -> list[Order]`** (Order = `{unit_id, action, target}`)
- Per unit:
  - `health_pct < retreat_threshold` + enemies visible → `retreat_from` nearest enemy position
  - enemies visible → `move_to` nearest enemy position (CombatSystem handles shooting when in range; agent just drives the unit toward engagement_range)
  - no enemies → `hold` (zero velocity)
- Only emit `agent.order_issued` when a unit's action **changes** (advance→retreat, etc.) to avoid log noise

**`_llm_decide(perception) -> list[Order]`**
- Format perception as a compact JSON prompt (unit positions, health%, enemy positions)
- Call `anthropic.Anthropic().messages.create(model="claude-haiku-4-5-20251001", max_tokens=512, ...)`
- System prompt instructs Claude to return a JSON array of `{unit_id, action, target}` orders
- Parse and validate response; fall back to `_rule_based_decide()` on any error

**`_execute(orders)`**
- `hold` → `sim.set_entity_velocity(uid, (0, 0, 0))`
- `move_to` → compute normalized direction vector × max_speed → `sim.set_entity_velocity(...)`
- `retreat_from` → compute direction away from threat × max_speed → `sim.set_entity_velocity(...)`

### `agents/system.py` — AgentSystem

Mirrors CombatSystem lifecycle exactly:

```python
_UPDATE_RATE = 2  # Hz — agents think at 2Hz (slower than combat's 10Hz)

class AgentSystem:
    def __init__(self, simulation):
        self._agents: dict[str, TacticalAgent] = {}  # faction → agent
        self._frame_time = 1.0 / _UPDATE_RATE

    async def initialize(self) -> None: pass
    async def start(self) -> None:  # spawn asyncio.create_task(_update_loop())
    async def stop(self) -> None:   # cancel task
    async def _tick(self) -> None:  # skip if not sim._running; call agent.tick() for each

    def create_agent(self, faction: str, doctrine: AgentDoctrine) -> TacticalAgent
    def remove_agent(self, faction: str) -> None
    def get_agents(self) -> list[dict]  # serializable list for API
```

---

## New Event Types — `core/events.py`

```python
AGENT_CREATED       = "agent.created"        # {agent_id, faction, doctrine}
AGENT_ORDER_ISSUED  = "agent.order_issued"   # {agent_id, entity_id, action, target} — only on change
```

Add EventValidator schemas for both.

---

## Modified Files

### `core/simulation.py`

- `self.agent_system: Optional[AgentSystem] = None`
- `initialize()`: create + `await agent_system.initialize()` after CombatSystem
- `start()`/`stop()`: start/stop AgentSystem alongside other systems
- Add `create_agent(faction, doctrine) -> TacticalAgent` — emits `agent.created`
- Add `get_agents() -> list[dict]`
- Add `remove_agent(faction) -> None`

### `api.py`

New Pydantic models:
```python
class CreateAgentRequest(BaseModel):
    faction: str          # "blue" | "red"
    doctrine: str = "balanced"  # preset name, or "llm"
    # Optional doctrine overrides:
    aggression: Optional[float] = None
    retreat_threshold: Optional[float] = None
    sensor_range: Optional[float] = None

class AgentResponse(BaseModel):
    agent_id: str
    faction: str
    doctrine: str
    decision_engine: str
    unit_count: int       # current friendly units alive
    aggression: float
    retreat_threshold: float
    sensor_range: float
```

New endpoints:
| Method | Path | Purpose |
|--------|------|---------|
| POST | /agents | Create tactical agent for a faction |
| GET | /agents | List all active agents |
| DELETE | /agents/{faction} | Remove agent |

### `static/index.html`

Add "Add Agent" sidebar section below Spawn Entity:
```html
<div class="sidebar-section">
  <div class="section-label">Add Agent</div>
  <div class="spawn-row">
    <label class="spawn-label">Faction</label>
    <select id="agent-faction" class="spawn-select">
      <option value="blue">Blue</option>
      <option value="red">Red</option>
    </select>
  </div>
  <div class="spawn-row">
    <label class="spawn-label">Doctrine</label>
    <select id="agent-doctrine" class="spawn-select">
      <option value="aggressive">Aggressive</option>
      <option value="balanced">Balanced</option>
      <option value="defensive">Defensive</option>
      <option value="llm">LLM (Claude)</option>
    </select>
  </div>
  <button id="btn-add-agent" class="btn btn-primary btn-sm spawn-btn">Add Agent</button>
  <div id="agent-error" class="spawn-error"></div>
</div>
```

Add "Agents" right panel section (below Combat):
```html
<div id="section-agents" class="right-section">
  <div class="right-section-header">
    Agents
    <span id="agent-count" class="engagement-count">0 active</span>
  </div>
  <div id="agent-list"></div>
</div>
```

### `static/app.js`

- `ApiClient`: add `getAgents()`, `createAgent(body)`, `deleteAgent(faction)`
- `AgentController` class (mirrors SpawnController):
  - `_addAgent()`: reads faction/doctrine dropdowns, calls `api.createAgent()`, shows error on 400
- `RightPanelController.updateAgents(agents)`: renders agent rows with faction color dot, doctrine tag, unit count
- `CanvasRenderer._drawEntities()`: AI-controlled units (those belonging to an active agent faction) get a small pulsing outer ring drawn around their shape (1px, faction color, 40% opacity). `renderer.agentFactions = Set<string>` updated from app.
- `StrategosApp`:
  - `this._agent_controller = new AgentController(api)`
  - `this.agentFactions = new Set()` — passed to canvas renderer
  - `_fetchAgents()` polls every 2s (alongside status + engagements)
  - WS handlers: `agent.created` + `agent.order_issued` → update agents list

### `static/styles.css`

Add agent panel styles:
- `.agent-row` — flex row, faction dot, doctrine tag, unit count
- `.doctrine-tag` — small badge like `.phase-tag`, distinct per doctrine (aggressive=danger, defensive=info, llm=primary)

---

## Tests

- **`tests/test_agent_doctrine.py`** — presets, dataclass defaults, override merging
- **`tests/test_agent_system.py`** — agent created, tick loop fires, rule-based units advance toward enemies, units retreat below health threshold, no action when no enemies
- **`tests/test_phase4.py`** — end-to-end: create blue aggressive agent + red defensive agent, spawn opposing units, run sim for N seconds, verify blue units moved toward red positions, verify a low-health blue unit reversed direction

For LLM tests: `unittest.mock.patch("anthropic.Anthropic")` to mock the client; return a fixture JSON response and verify `_llm_decide()` parses it correctly and falls back on invalid JSON.

---

## Demo: `demo_phase4.py`

- Spawn 3 blue infantry at (−300, 0), (−300, −50), (−300, 50)
- Spawn 2 red tanks at (300, 0), (300, 60)
- Create blue agent (aggressive doctrine), red agent (defensive doctrine)
- Start sim at 3× time scale
- Print `agent.order_issued` events as they fire
- Print health status every 5s
- End when one side is eliminated

---

## Implementation Order

1. `core/events.py` — 2 new event types + validator schemas
2. `agents/doctrine.py` — dataclass + presets (no deps)
3. `agents/agent.py` — TacticalAgent (perception + both decision paths + execute)
4. `agents/system.py` — AgentSystem loop
5. `agents/__init__.py` — exports
6. `core/simulation.py` — wire AgentSystem, add public agent methods
7. `api.py` — new models + 3 endpoints
8. `static/` — Add Agent sidebar, Agents panel, canvas AI indicator
9. `tests/` — 3 new test files
10. `demo_phase4.py`

---

## Verification

1. `pytest tests/ -k "not test_movement" -v` — all existing + new tests pass
2. `python demo_phase4.py` — units maneuver autonomously; one side wins without any manual velocity calls
3. `python strategos.py` → open browser:
   - Spawn blue and red units via UI
   - Add Blue (aggressive) + Red (defensive) agents via sidebar
   - Start simulation — units should move toward each other without manual velocity commands
   - Agents panel shows active agents, doctrine, unit count
   - Event strip shows `agent.order_issued` entries
   - Canvas shows AI indicator rings around agent-controlled units
   - Inspector confirms units change velocity as agent issues orders
4. LLM path: use `doctrine=llm` in demo, confirm Claude API is called and orders are parsed
