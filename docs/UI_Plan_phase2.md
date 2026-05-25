# Strategos UI Redesign Plan

## Context

The current Strategos frontend is a minimal single-page layout with basic play/pause/stop/resume buttons and a scrolling event log. It has no visual representation of the simulation space. The goal is to replace it with a proper simulation UI: a 2D canvas map showing entities moving in real-time, a dedicated admin sidebar for simulation controls, and an entity inspector in a right panel — all in vanilla JS with no build step. A combat placeholder panel is included, grayed out, ready for Phase 3.

---

## Layout

Three-column CSS Grid filling the full viewport:

```
+-sidebar (220px)-+------- canvas map --------+--right panel (280px)--+
| STRATEGOS  [WS] |  [+] [-] [Fit] 100%       | Entities (N)          |
| ─────────────── |                            | [entity rows...]      |
| Simulation      |   HTML5 Canvas             | ─────────────────     |
| [running] 00:00 |   entities as dots         | Inspector             |
| [Start] [Pause] |   zoom + pan               | [selected entity]     |
| [Resume][Stop]  |   adaptive grid            | ─────────────────     |
| Entities: N     |                            | Combat  [Phase 3]     |
| Events:   N     |                            | [disabled placeholder]|
| Scale:    1.0x  +------- event strip --------+                       |
| ─────────────── | [t=1.23s] entity.moved ... |                       |
| Time Scale      |                            |                       |
| [slider] 1.0x   |                            |                       |
| [Apply] PENDING |                            |                       |
| ─────────────── +----------------------------+-----------------------+
| Seek            
| [input] [Go]    
| ─────────────── 
| Markers         
| [input] [Add]   
| • [t=5.0s] foo  
+-----------------+
```

---

## Files to Change

### 1. `api.py` — Add two entity endpoints

**Add Pydantic models** (after existing models):
```python
class EntityResponse(BaseModel):
    entity_id: str
    type: str
    position: list[float]
    velocity: list[float]
    heading: float
    speed: float
    max_speed: float
    metadata: dict
    created_at: float
    destroyed_at: Optional[float] = None

class EntityListResponse(BaseModel):
    count: int
    entities: list[EntityResponse]
```

**Also fix `SimulationStatus`** — it's missing `entity_count` and `formatted_time` (fields already returned by `get_status()` but not in the Pydantic model).

**Add GET /entities** — snapshot of all living entities:
- Iterates `simulation.state.entities`
- Gets interpolated position via `simulation.movement_system.get_entity_position(entity_id)` (falls back to `entity_data["position"]` if movement system unavailable or returns None)
- Returns `EntityListResponse`

**Add GET /entities/{entity_id}** — single entity:
- Parses UUID, calls `simulation.get_entity(uid)`
- Returns 404 if not found, 400 if UUID invalid
- Same interpolated position logic

Place both routes after the existing `/events` route, before the WebSocket handler.

---

### 2. `static/index.html` — Complete replacement

Structure:
```html
<div id="app">                    <!-- CSS grid: 3 columns -->
  <aside id="sidebar">            <!-- left admin panel -->
    #sidebar-title (STRATEGOS + WS badge)
    #section-transport (clock state, time, buttons, stats)
    #section-timescale (slider + apply)
    #section-seek (input + go)
    #section-markers (input + add + list)
  </aside>
  <main id="map-area">            <!-- canvas + event strip -->
    #map-toolbar (zoom buttons + zoom% label)
    <canvas id="map-canvas">
    #event-strip (header + #event-list)
  </main>
  <aside id="right-panel">        <!-- entity list + inspector + combat -->
    #section-entity-list
    #section-inspector
    #section-combat.disabled-section  ← static, grayed out
  </aside>
</div>
```

---

### 3. `static/styles.css` — Complete replacement

Key rules:
- `#app`: `display: grid; grid-template-columns: 220px 1fr 280px; height: 100vh`
- `#map-area`: `display: grid; grid-template-rows: 32px 1fr 140px` (toolbar / canvas / event strip)
- `.disabled-section`: `opacity: 0.45; pointer-events: none` (combat placeholder)
- Color palette: unchanged from existing (dark navy, same button colors)
- Font: system-ui for UI; Monaco/monospace for data values and event log

---

### 4. `static/app.js` — Complete replacement

Seven classes:

**`ApiClient`** — all `fetch()` calls, one method per endpoint:
`getStatus()`, `getEntities()`, `getEntity(id)`, `start()`, `stop()`, `pause()`, `resume()`, `setTimeScale(scale)`, `seek(target_time)`, `createMarker(label)`

**`WebSocketClient`** — connection + reconnect + typed event dispatch:
- `on(type, fn)` / `_emit(type, payload)`
- Special types: `_connected`, `_disconnected`, `*` (catch-all)
- 3s auto-reconnect on close

**`EntityStore`** — in-memory entity state:
- `entities: Map<entity_id, entity_data>`
- `loadSnapshot(list)` — bulk load from GET /entities
- `onEntityCreated(event)`, `onEntityMoved(event)`, `onEntityDestroyed(event)`
- `getInterpolatedPosition(entity, sim_time)` — `pos + vel * (sim_time - last_update_time)`

**`CanvasRenderer`** — HTML5 Canvas + requestAnimationFrame loop:
- Transform: `screenX = (worldX - viewX) * zoom + w/2`; `screenY = (worldY - viewY) * zoom + h/2`
- `zoomIn()`, `zoomOut()`, `fitToEntities()`
- Mouse wheel zoom (cursor-anchored), left-drag pan, click to select entity
- `_drawGrid()` with adaptive step via `_niceGridStep()` (powers of 10, ~10-20 lines)
- Entity dots: 5px radius (7px selected), heading line, label when `zoom > 0.3`
- Colors: faction-based (blue/red) → type-based (infantry=green, tank=amber, aircraft=cyan) → grey fallback
- `onEntitySelect` callback for cross-wiring with right panel
- `ResizeObserver` to keep canvas sized to parent

**`SidebarController`** — left sidebar DOM bindings:
- `updateStatus(status)` — sets clock state badge, time, entity count, event count, scale
- Wires start/pause/resume/stop buttons to `ApiClient`
- Time scale slider with PENDING indicator (cleared on Apply)
- Seek input (Enter key + button)
- Marker creation + list (prepend newest)

**`RightPanelController`** — entity list, inspector, event strip:
- `refreshEntityList()` — rebuilds `#entity-list` from EntityStore
- `selectEntity(id)` — highlights list row + populates inspector
- `appendEvent(event)` — adds to event strip, caps at 200 items, auto-scroll
- Inspector shows: id (8 chars), type, faction, x/y/z, heading (degrees), speed, max_speed, velocity x/y

**`StrategosApp`** — root singleton, data flow wiring:
- On init: connects WS, loads entity snapshot, starts 2s status poll
- WS entity events → EntityStore → refresh entity list / deselect destroyed
- WS `*` → event strip
- WS simulation events (started/paused/resumed/time.scaled) → immediate status fetch
- Canvas `onEntitySelect` ↔ RightPanel `onEntitySelect` cross-wired
- Toolbar zoom buttons → CanvasRenderer, zoom label update
- `canvas.simTime` updated from status poll for interpolation accuracy

---

## Data Flow

```
Page load → GET /entities → EntityStore.loadSnapshot → canvas.fitToEntities
         → GET /status   → SidebarController.updateStatus

WS entity.moved     → EntityStore.onEntityMoved   (no list refresh; RAF reads directly)
WS entity.created   → EntityStore.onEntityCreated → refreshEntityList
WS entity.destroyed → EntityStore.onEntityDestroyed → refreshEntityList; deselect if needed
WS *                → RightPanelController.appendEvent

Status poll (2s)    → app._simTime updated → canvas.simTime updated → better interpolation
```

---

## Verification

1. `uvicorn api:app --reload` starts without errors; `curl /entities` returns `{"count":0,"entities":[]}`
2. `curl /entities/bad-uuid` returns 400; `curl /entities/00000000-...` returns 404
3. Page loads at `localhost:8000` with three-column layout, no console errors
4. WS badge turns green within 1s of page load
5. Click Start → clock state badge shows "running", time increments in sidebar
6. With entities in simulation: dots appear on canvas; "Fit" centers them
7. Mouse wheel zooms toward cursor; left-drag pans; grid adapts
8. Click canvas dot → right panel inspector populates; entity list row highlights
9. Click entity in list → canvas selection ring appears on that entity
10. Entities with velocity visibly move (smooth interpolation between events)
11. Time scale slider shows PENDING until Apply; PENDING clears after Apply
12. Seek to `5` → simulation time jumps; canvas reflects updated state
13. Combat section is visually dimmed; clicks inside it have no effect
14. Kill and restart server → WS badge goes DISC, reconnects after 3s automatically
