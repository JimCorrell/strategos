// ============================================================
// ApiClient — all HTTP calls, one method per endpoint
// ============================================================
class ApiClient {
    async _fetch(path, { method = 'GET', body } = {}) {
        const opts = { method, headers: { 'Content-Type': 'application/json' } };
        if (body !== undefined) opts.body = JSON.stringify(body);
        const r = await fetch(path, opts);
        if (!r.ok) throw new Error(`${method} ${path} → ${r.status} ${r.statusText}`);
        return r.json();
    }

    getStatus()         { return this._fetch('/status'); }
    getEntities()       { return this._fetch('/entities'); }
    getEntity(id)       { return this._fetch(`/entities/${id}`); }
    getEngagements()    { return this._fetch('/engagements'); }
    createEntity(body)  { return this._fetch('/entities', { method: 'POST', body }); }
    start()             { return this._fetch('/start',      { method: 'POST' }); }
    stop()              { return this._fetch('/stop',       { method: 'POST' }); }
    pause()             { return this._fetch('/pause',      { method: 'POST' }); }
    resume()            { return this._fetch('/resume',     { method: 'POST' }); }
    setTimeScale(s)     { return this._fetch('/time-scale', { method: 'POST', body: { scale: s } }); }
    seek(t)             { return this._fetch('/seek',       { method: 'POST', body: { target_time: t } }); }
    createMarker(label) { return this._fetch('/marker',     { method: 'POST', body: { label } }); }
}

// ============================================================
// WebSocketClient — connection, auto-reconnect, typed dispatch
// ============================================================
class WebSocketClient {
    constructor(url) {
        this._url = url;
        this._handlers = {};
    }

    connect() {
        const ws = new WebSocket(this._url);
        ws.onopen    = () => this._emit('_connected', null);
        ws.onclose   = () => { this._emit('_disconnected', null); setTimeout(() => this.connect(), 3000); };
        ws.onerror   = (e) => console.warn('WS error', e);
        ws.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data);
                this._emit(msg.event_type, msg);
                this._emit('*', msg);
            } catch(err) { console.warn('WS parse error', err); }
        };
    }

    on(type, fn) {
        (this._handlers[type] = this._handlers[type] || []).push(fn);
    }

    _emit(type, payload) {
        for (const fn of (this._handlers[type] || [])) {
            try { fn(payload); } catch(e) { console.error('handler error', e); }
        }
    }
}

// ============================================================
// EntityStore — in-memory entity state + client-side interpolation
// ============================================================
const FACTION_COLORS = {
    blue: '#3b82f6',
    red:  '#ef4444',
};

const TYPE_COLORS = {
    infantry: '#22c55e',
    tank:     '#f59e0b',
    aircraft: '#06b6d4',
    ship:     '#818cf8',
    artillery:'#fb923c',
};

function entityColor(entity) {
    if (entity.faction && FACTION_COLORS[entity.faction]) return FACTION_COLORS[entity.faction];
    return TYPE_COLORS[entity.type] || '#94a3b8';
}

function healthColor(pct) {
    if (pct > 0.6) return '#22c55e';
    if (pct > 0.3) return '#f59e0b';
    return '#ef4444';
}

class EntityStore {
    constructor() {
        this.entities = new Map();  // entity_id (str) → entity data
    }

    loadSnapshot(list) {
        this.entities.clear();
        for (const e of list) this.entities.set(e.entity_id, e);
    }

    onEntityCreated(event) {
        const d = event.data || {};
        if (!d.entity_id) return;
        this.entities.set(d.entity_id, {
            entity_id:        d.entity_id,
            type:             d.type || 'unknown',
            position:         d.position || [0, 0, 0],
            velocity:         [0, 0, 0],
            heading:          0,
            speed:            0,
            max_speed:        d.max_speed || 0,
            metadata:         d.metadata || {},
            last_update_time: event.simulation_time || 0,
            // Phase 3: combat
            faction:          d.faction || 'neutral',
            health:           d.health ?? 100,
            max_health:       d.max_health ?? 100,
            firepower:        d.firepower ?? 0,
            armor:            d.armor ?? 0,
            engagement_range: d.engagement_range ?? 0,
            morale:           d.morale ?? 75,
        });
    }

    onEntityMoved(event) {
        const d = event.data || {};
        const e = this.entities.get(d.entity_id);
        if (!e) return;
        if (d.position)         e.position         = d.position;
        if (d.velocity)         e.velocity         = d.velocity;
        if (d.heading != null)  e.heading          = d.heading;
        if (d.speed   != null)  e.speed            = d.speed;
        e.last_update_time = d.last_update_time ?? (event.simulation_time || 0);
    }

    onEntityDamaged(event) {
        const d = event.data || {};
        const e = this.entities.get(d.entity_id);
        if (e) e.health = d.health_after ?? e.health;
    }

    onEntityDestroyed(event) {
        const d = event.data || {};
        if (d.entity_id) this.entities.delete(d.entity_id);
    }

    // pos = last_pos + vel * dt
    getInterpolatedPosition(entity, simTime) {
        const vel = entity.velocity;
        if (!vel) return entity.position;
        const dt = (simTime || 0) - (entity.last_update_time || 0);
        if (dt <= 0 || (vel[0] === 0 && vel[1] === 0 && vel[2] === 0)) return entity.position;
        return [
            entity.position[0] + vel[0] * dt,
            entity.position[1] + vel[1] * dt,
            entity.position[2] + vel[2] * dt,
        ];
    }
}

// ============================================================
// CanvasRenderer — RAF loop, zoom/pan, entity drawing
// ============================================================
class CanvasRenderer {
    constructor(canvas, store) {
        this._canvas = canvas;
        this._ctx    = canvas.getContext('2d');
        this._store  = store;
        this._zoom   = 1.0;   // pixels per world unit
        this._viewX  = 0;     // world X at screen center
        this._viewY  = 0;     // world Y at screen center
        this._selectedId  = null;
        this.simTime      = 0;
        this.onEntitySelect = null;  // callback(id | null)

        this._dragging  = false;
        this._hasDragged = false;
        this._dragStart  = null;
        this._viewAtDrag = null;
        this.engagements = [];  // Phase 3: [{entity_a, entity_b, started_at}]

        this._setupResize();
        this._setupEvents();
    }

    _setupResize() {
        new ResizeObserver(() => this._resize()).observe(this._canvas.parentElement);
        this._resize();
    }

    _resize() {
        const p = this._canvas.parentElement;
        this._canvas.width  = p.clientWidth;
        this._canvas.height = p.clientHeight;
    }

    start() { this._raf(); }
    _raf()  { requestAnimationFrame(() => { this._draw(); this._raf(); }); }

    // ---- coordinate transforms ----
    _w2s(wx, wy) {
        const cx = this._canvas.width  / 2;
        const cy = this._canvas.height / 2;
        return [
            (wx - this._viewX) * this._zoom + cx,
            -(wy - this._viewY) * this._zoom + cy,
        ];
    }

    _s2w(sx, sy) {
        const cx = this._canvas.width  / 2;
        const cy = this._canvas.height / 2;
        return [
            (sx - cx) / this._zoom + this._viewX,
            -((sy - cy) / this._zoom) + this._viewY,
        ];
    }

    // ---- grid ----
    _niceStep(raw) {
        if (raw <= 0) return 1;
        const mag = Math.pow(10, Math.floor(Math.log10(raw)));
        const n   = raw / mag;
        const nice = n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10;
        return nice * mag;
    }

    _drawGrid(ctx) {
        const w = this._canvas.width, h = this._canvas.height;
        const step = this._niceStep(w / this._zoom / 12);

        const [wx0, wy0] = this._s2w(0,  h);
        const [wx1, wy1] = this._s2w(w,  0);
        const [, oy]     = this._w2s(0, 0);
        const [ox]       = this._w2s(0, 0);

        ctx.strokeStyle = 'rgba(255,255,255,0.06)';
        ctx.lineWidth = 1;
        ctx.beginPath();

        for (let wx = Math.floor(wx0 / step) * step; wx <= wx1 + step; wx += step) {
            const [sx] = this._w2s(wx, 0);
            ctx.moveTo(sx, 0); ctx.lineTo(sx, h);
        }
        for (let wy = Math.floor(wy0 / step) * step; wy <= wy1 + step; wy += step) {
            const [, sy] = this._w2s(0, wy);
            ctx.moveTo(0, sy); ctx.lineTo(w, sy);
        }
        ctx.stroke();

        // axes
        ctx.strokeStyle = 'rgba(255,255,255,0.18)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(ox, 0); ctx.lineTo(ox, h);
        ctx.moveTo(0, oy); ctx.lineTo(w, oy);
        ctx.stroke();

        // scale labels along axes
        ctx.fillStyle = 'rgba(148,163,184,0.6)';
        ctx.font = '9px Monaco, monospace';
        const labelOy = Math.max(12, Math.min(h - 4, oy));
        const labelOx = Math.max(4,  Math.min(w - 30, ox));
        for (let wx = Math.floor(wx0 / step) * step; wx <= wx1 + step; wx += step) {
            if (Math.abs(wx) < step * 0.1) continue;
            const [sx] = this._w2s(wx, 0);
            if (sx > 4 && sx < w - 4) ctx.fillText(this._fmt(wx), sx + 2, labelOy - 2);
        }
        for (let wy = Math.floor(wy0 / step) * step; wy <= wy1 + step; wy += step) {
            if (Math.abs(wy) < step * 0.1) continue;
            const [, sy] = this._w2s(0, wy);
            if (sy > 12 && sy < h - 4) ctx.fillText(this._fmt(wy), labelOx + 2, sy - 2);
        }
    }

    _fmt(n) {
        if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + 'k';
        return Number.isInteger(n) ? n.toString() : n.toFixed(1);
    }

    // ---- Phase 3: engagement lines ----
    _drawEngagements(ctx) {
        if (!this.engagements.length) return;
        ctx.save();
        ctx.strokeStyle = 'rgba(239,68,68,0.45)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 3]);
        for (const eng of this.engagements) {
            const ea = this._store.entities.get(eng.entity_a);
            const eb = this._store.entities.get(eng.entity_b);
            if (!ea || !eb) continue;
            const pa = this._store.getInterpolatedPosition(ea, this.simTime);
            const pb = this._store.getInterpolatedPosition(eb, this.simTime);
            const [ax, ay] = this._w2s(pa[0], pa[1]);
            const [bx, by] = this._w2s(pb[0], pb[1]);
            ctx.beginPath();
            ctx.moveTo(ax, ay);
            ctx.lineTo(bx, by);
            ctx.stroke();
        }
        ctx.setLineDash([]);
        ctx.restore();
    }

    // ---- entity shape drawing ----
    // heading 0 = east on canvas (matches existing heading-line convention)
    _drawEntityShape(ctx, type, sx, sy, r, heading) {
        if (type === 'aircraft') {
            // Chevron that rotates with heading — save/restore preserves the
            // path in device coords so fill/stroke work after restore
            ctx.save();
            ctx.translate(sx, sy);
            ctx.rotate(-heading);
            ctx.beginPath();
            ctx.moveTo(r * 1.8, 0);           // nose
            ctx.lineTo(-r * 0.5, -r * 1.3);   // left wing tip
            ctx.lineTo(-r * 0.1, 0);           // center notch
            ctx.lineTo(-r * 0.5,  r * 1.3);   // right wing tip
            ctx.closePath();
            ctx.restore();
            return;
        }

        ctx.beginPath();
        switch (type) {
            case 'infantry':
                // Upward-pointing triangle
                ctx.moveTo(sx,           sy - r * 1.5);
                ctx.lineTo(sx + r * 1.3, sy + r * 0.9);
                ctx.lineTo(sx - r * 1.3, sy + r * 0.9);
                ctx.closePath();
                break;
            case 'tank':
                // Rounded rectangle hull (turret drawn separately)
                ctx.roundRect(sx - r * 1.4, sy - r * 0.9, r * 2.8, r * 1.8, 2);
                break;
            case 'artillery':
                // Diamond
                ctx.moveTo(sx,            sy - r * 1.5);
                ctx.lineTo(sx + r * 1.15, sy);
                ctx.lineTo(sx,            sy + r * 1.5);
                ctx.lineTo(sx - r * 1.15, sy);
                ctx.closePath();
                break;
            case 'ship':
                // Wide flat rectangle
                ctx.roundRect(sx - r * 2.0, sy - r * 0.65, r * 4.0, r * 1.3, 2);
                break;
            default:
                ctx.arc(sx, sy, r, 0, Math.PI * 2);
        }
    }

    // ---- entities ----
    _drawEntities(ctx) {
        const showLabels = this._zoom > 0.3;

        for (const entity of this._store.entities.values()) {
            const pos     = this._store.getInterpolatedPosition(entity, this.simTime);
            const [sx, sy] = this._w2s(pos[0], pos[1]);
            const isSelected = entity.entity_id === this._selectedId;
            const color   = entityColor(entity);
            const r       = isSelected ? 7 : 5;
            const heading = entity.heading || 0;

            // Selection ring
            if (isSelected) {
                ctx.beginPath();
                ctx.arc(sx, sy, r + 5, 0, Math.PI * 2);
                ctx.strokeStyle = 'rgba(255,255,255,0.85)';
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }

            // Unit shape
            this._drawEntityShape(ctx, entity.type, sx, sy, r, heading);
            ctx.fillStyle = color;
            ctx.strokeStyle = 'rgba(255,255,255,0.55)';
            ctx.lineWidth = 1;
            ctx.fill();
            ctx.stroke();

            // Tank turret overlay
            if (entity.type === 'tank') {
                ctx.beginPath();
                ctx.arc(sx, sy, r * 0.55, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(0,0,0,0.45)';
                ctx.fill();
            }

            // Heading line for ground units (aircraft shape already shows direction)
            if (entity.speed > 0.001 && entity.type !== 'aircraft') {
                ctx.beginPath();
                ctx.moveTo(sx, sy);
                ctx.lineTo(sx + Math.cos(heading) * 14, sy - Math.sin(heading) * 14);
                ctx.strokeStyle = color;
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }

            // Health bar
            const maxHp = entity.max_health || 100;
            const hp    = entity.health ?? maxHp;
            const pct   = Math.max(0, Math.min(1, hp / maxHp));
            const barW  = 14, barH = 3;
            const barX  = sx - barW / 2;
            const barY  = sy + r + 6;
            ctx.fillStyle = 'rgba(0,0,0,0.5)';
            ctx.fillRect(barX, barY, barW, barH);
            ctx.fillStyle = healthColor(pct);
            ctx.fillRect(barX, barY, barW * pct, barH);

            // Label
            if (showLabels) {
                ctx.fillStyle = 'rgba(241,245,249,0.65)';
                ctx.font = '9px Monaco, monospace';
                ctx.fillText(entity.entity_id.substring(0, 8), sx + r + 5, sy - 4);
            }
        }
    }

    _draw() {
        const ctx = this._ctx;
        const w = this._canvas.width, h = this._canvas.height;
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = '#0a1628';
        ctx.fillRect(0, 0, w, h);
        this._drawGrid(ctx);
        this._drawEngagements(ctx);
        this._drawEntities(ctx);
    }

    // ---- zoom / pan / fit ----
    zoomIn()  { this._zoom = Math.min(this._zoom * 1.25, 500); }
    zoomOut() { this._zoom = Math.max(this._zoom / 1.25, 0.005); }

    fitToEntities() {
        const all = Array.from(this._store.entities.values());
        if (!all.length) { this._viewX = 0; this._viewY = 0; this._zoom = 1; return; }

        let minX =  Infinity, maxX = -Infinity;
        let minY =  Infinity, maxY = -Infinity;
        for (const e of all) {
            const p = this._store.getInterpolatedPosition(e, this.simTime);
            minX = Math.min(minX, p[0]); maxX = Math.max(maxX, p[0]);
            minY = Math.min(minY, p[1]); maxY = Math.max(maxY, p[1]);
        }

        this._viewX = (minX + maxX) / 2;
        this._viewY = (minY + maxY) / 2;
        const pad   = 1.5;
        const rangeX = (maxX - minX) * pad || 200;
        const rangeY = (maxY - minY) * pad || 200;
        this._zoom = Math.min(
            this._canvas.width  / rangeX,
            this._canvas.height / rangeY,
            50
        );
    }

    getZoomPercent() { return Math.round(this._zoom * 100); }

    selectEntity(id) { this._selectedId = id; }

    // ---- mouse input ----
    _setupEvents() {
        const canvas = this._canvas;

        // Wheel zoom — cursor-anchored
        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;
            const [wx, wy] = this._s2w(mx, my);
            const factor   = e.deltaY < 0 ? 1.15 : 1 / 1.15;
            this._zoom = Math.max(0.005, Math.min(500, this._zoom * factor));
            const cx = canvas.width / 2, cy = canvas.height / 2;
            this._viewX = wx - (mx - cx) / this._zoom;
            this._viewY = wy + (my - cy) / this._zoom;
        }, { passive: false });

        // Drag pan + click select
        canvas.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            this._dragging   = true;
            this._hasDragged = false;
            this._dragStart  = [e.clientX, e.clientY];
            this._viewAtDrag = [this._viewX, this._viewY];
        });

        window.addEventListener('mousemove', (e) => {
            if (!this._dragging) return;
            const dx = e.clientX - this._dragStart[0];
            const dy = e.clientY - this._dragStart[1];
            if (Math.abs(dx) + Math.abs(dy) > 3) this._hasDragged = true;
            this._viewX = this._viewAtDrag[0] - dx / this._zoom;
            this._viewY = this._viewAtDrag[1] + dy / this._zoom;
        });

        window.addEventListener('mouseup', (e) => {
            if (!this._dragging) return;
            this._dragging = false;
            if (!this._hasDragged) {
                const rect = canvas.getBoundingClientRect();
                this._handleClick(e.clientX - rect.left, e.clientY - rect.top);
            }
        });
    }

    _handleClick(sx, sy) {
        const THRESH = 12;
        let bestId = null, bestDist = Infinity;

        for (const entity of this._store.entities.values()) {
            const pos = this._store.getInterpolatedPosition(entity, this.simTime);
            const [esx, esy] = this._w2s(pos[0], pos[1]);
            const dist = Math.hypot(sx - esx, sy - esy);
            if (dist < THRESH && dist < bestDist) {
                bestDist = dist;
                bestId   = entity.entity_id;
            }
        }

        this._selectedId = bestId;
        if (this.onEntitySelect) this.onEntitySelect(bestId);

        // If click didn't hit an entity, treat it as a spawn position pick
        if (!bestId && this.onMapClick) {
            const [wx, wy] = this._s2w(sx, sy);
            this.onMapClick(wx, wy);
        }
    }
}

// ============================================================
// SidebarController — left sidebar DOM bindings
// ============================================================
class SidebarController {
    constructor(api) {
        this._api = api;
        this._scalePending = false;
        this._el = {
            wsBadge:      document.getElementById('ws-badge'),
            stateBadge:   document.getElementById('state-badge'),
            simTime:      document.getElementById('sim-time'),
            statEntities: document.getElementById('stat-entities'),
            statEvents:   document.getElementById('stat-events'),
            statScale:    document.getElementById('stat-scale'),
            scaleSlider:  document.getElementById('scale-slider'),
            scaleValue:   document.getElementById('scale-value'),
            pendingBadge: document.getElementById('pending-badge'),
            seekInput:    document.getElementById('seek-input'),
            markerInput:  document.getElementById('marker-input'),
            markerList:   document.getElementById('marker-list'),
        };
        this._wire();
    }

    setWsConnected(ok) {
        this._el.wsBadge.textContent = ok ? 'WS' : 'DISC';
        this._el.wsBadge.className   = 'ws-badge' + (ok ? ' connected' : '');
    }

    updateStatus(s) {
        const state = s.clock_state || 'stopped';
        this._el.stateBadge.textContent = state;
        this._el.stateBadge.className   = 'state-badge ' + state;
        this._el.simTime.textContent     = parseFloat(s.current_time).toFixed(2) + 's';
        this._el.statEntities.textContent = s.entity_count ?? 0;
        this._el.statEvents.textContent   = s.event_count  ?? 0;
        this._el.statScale.textContent    = (s.time_scale ?? 1) + 'x';

        if (!this._scalePending) {
            this._el.scaleSlider.value      = s.time_scale ?? 1;
            this._el.scaleValue.textContent = (s.time_scale ?? 1) + 'x';
        }
    }

    addMarker(time, label) {
        const li = document.createElement('li');
        li.textContent = `[${parseFloat(time).toFixed(2)}s] ${label}`;
        this._el.markerList.prepend(li);
    }

    _wire() {
        const { api } = { api: this._api };
        const q = (id) => document.getElementById(id);
        q('btn-start') .addEventListener('click', () => api.start() .catch(console.warn));
        q('btn-pause') .addEventListener('click', () => api.pause() .catch(console.warn));
        q('btn-resume').addEventListener('click', () => api.resume().catch(console.warn));
        q('btn-stop')  .addEventListener('click', () => api.stop()  .catch(console.warn));

        this._el.scaleSlider.addEventListener('input', (e) => {
            this._el.scaleValue.textContent = parseFloat(e.target.value).toFixed(1) + 'x';
            this._scalePending = true;
            this._el.pendingBadge.classList.add('visible');
        });

        q('btn-apply-scale').addEventListener('click', async () => {
            const scale = parseFloat(this._el.scaleSlider.value);
            await api.setTimeScale(scale).catch(console.warn);
            this._scalePending = false;
            this._el.pendingBadge.classList.remove('visible');
        });

        q('btn-seek').addEventListener('click',    () => this._doSeek());
        this._el.seekInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') this._doSeek(); });

        q('btn-add-marker').addEventListener('click', () => this._doMarker());
        this._el.markerInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') this._doMarker(); });
    }

    async _doSeek() {
        const t = parseFloat(this._el.seekInput.value);
        if (!isNaN(t)) await this._api.seek(t).catch(console.warn);
    }

    async _doMarker() {
        const label = this._el.markerInput.value.trim();
        if (!label) return;
        const result = await this._api.createMarker(label).catch(console.warn);
        if (result) {
            this.addMarker(result.simulation_time, label);
            this._el.markerInput.value = '';
        }
    }
}

// ============================================================
// RightPanelController — entity list, inspector, event strip
// ============================================================
class RightPanelController {
    constructor(store) {
        this._store = store;
        this._selectedId = null;
        this.onEntitySelect = null;  // callback(id | null)
        this._el = {
            header:          document.getElementById('entity-list-header'),
            list:            document.getElementById('entity-list'),
            inspector:       document.getElementById('inspector-content'),
            events:          document.getElementById('event-list'),
            engagementCount: document.getElementById('engagement-count'),
            engagementList:  document.getElementById('engagement-list'),
        };
    }

    refreshEntityList() {
        const all = Array.from(this._store.entities.values());
        this._el.header.textContent = `Entities (${all.length})`;
        this._el.list.innerHTML = '';

        for (const e of all) {
            const row = document.createElement('div');
            row.className = 'entity-row' + (e.entity_id === this._selectedId ? ' selected' : '');
            row.dataset.id = e.entity_id;

            const dot = document.createElement('div');
            dot.className = 'entity-dot';
            dot.style.background = entityColor(e);

            const lbl  = document.createElement('div');
            lbl.className = 'entity-label';
            lbl.textContent = e.entity_id.substring(0, 8);

            const typ  = document.createElement('div');
            typ.className = 'entity-type';
            typ.textContent = e.type;

            row.append(dot, lbl, typ);
            row.addEventListener('click', () => {
                this._selectedId = e.entity_id;
                this.selectEntity(e.entity_id);
                if (this.onEntitySelect) this.onEntitySelect(e.entity_id);
            });
            this._el.list.appendChild(row);
        }
    }

    selectEntity(id) {
        this._selectedId = id;
        for (const row of this._el.list.querySelectorAll('.entity-row')) {
            row.classList.toggle('selected', row.dataset.id === id);
        }
        this._renderInspector(id ? this._store.entities.get(id) : null);
    }

    deselectEntity(id) {
        if (this._selectedId === id) { this._selectedId = null; this.selectEntity(null); }
    }

    _renderInspector(entity) {
        if (!entity) {
            this._el.inspector.innerHTML = '<div class="no-selection">No entity selected</div>';
            return;
        }
        const pos   = entity.position || [0, 0, 0];
        const vel   = entity.velocity || [0, 0, 0];
        const deg   = ((entity.heading || 0) * 180 / Math.PI).toFixed(1);
        const maxHp = entity.max_health || 100;
        const hp    = entity.health ?? maxHp;
        const pct   = Math.max(0, Math.min(1, hp / maxHp));
        const hpColor = healthColor(pct);

        const healthBar = `
            <div class="insp-health">
                <div class="insp-health-bar" style="width:${(pct*100).toFixed(0)}%;background:${hpColor}"></div>
            </div>
            <div class="insp-health-label">${hp.toFixed(0)} / ${maxHp.toFixed(0)}</div>`;

        const rows = [
            ['id',       entity.entity_id.substring(0, 8) + '…'],
            ['type',     entity.type],
            ['faction',  entity.faction || 'neutral'],
            ['x',        pos[0].toFixed(2)],
            ['y',        pos[1].toFixed(2)],
            ['z',        pos[2].toFixed(2)],
            ['heading',  deg + '°'],
            ['speed',    (entity.speed || 0).toFixed(2)],
            ['max_spd',  (entity.max_speed || 0).toFixed(2)],
            ['vel x',    vel[0].toFixed(3)],
            ['vel y',    vel[1].toFixed(3)],
            ['firepower',(entity.firepower || 0).toFixed(1)],
            ['armor',    (entity.armor || 0).toFixed(1)],
            ['range',    (entity.engagement_range || 0).toFixed(0)],
            ['morale',   (entity.morale || 0).toFixed(0)],
        ];
        this._el.inspector.innerHTML =
            healthBar +
            rows.map(([k, v]) => `<div class="insp-row"><span>${k}</span><span class="insp-val">${v}</span></div>`).join('');
    }

    // Phase 3: Combat panel
    updateEngagements(engagements) {
        const n = engagements.length;
        if (this._el.engagementCount) this._el.engagementCount.textContent = `${n} active`;
        if (!this._el.engagementList) return;
        this._el.engagementList.innerHTML = engagements.map(eng => {
            const a = eng.entity_a.substring(0, 6);
            const b = eng.entity_b.substring(0, 6);
            return `<div class="engagement-row">${a}… ⚔ ${b}…</div>`;
        }).join('');
    }

    appendEvent(event) {
        const list = this._el.events;
        const row  = document.createElement('div');
        row.className = 'event-row';
        const t    = parseFloat(event.simulation_time || 0).toFixed(2);
        const type = event.event_type || '';
        const preview = JSON.stringify(event.data || {}).substring(0, 80);
        row.innerHTML = `<span class="evt-time">[${t}s]</span><span class="evt-type">${type}</span>${preview}`;
        list.appendChild(row);
        while (list.children.length > 200) list.removeChild(list.firstChild);
        list.scrollTop = list.scrollHeight;
    }
}

// ============================================================
// SpawnController — entity creation sidebar panel
// ============================================================
class SpawnController {
    constructor(api) {
        this._api = api;
        this._el = {
            type:    document.getElementById('spawn-type'),
            faction: document.getElementById('spawn-faction'),
            x:       document.getElementById('spawn-x'),
            y:       document.getElementById('spawn-y'),
            btn:     document.getElementById('btn-spawn'),
            error:   document.getElementById('spawn-error'),
            hint:    document.getElementById('spawn-hint'),
        };
        this._el.btn.addEventListener('click', () => this._spawn());
    }

    // Called by CanvasRenderer when user clicks on empty canvas space
    setPosition(wx, wy) {
        this._el.x.value = Math.round(wx);
        this._el.y.value = Math.round(wy);
        this._el.hint.textContent = `Position set: (${Math.round(wx)}, ${Math.round(wy)})`;
        setTimeout(() => { this._el.hint.textContent = 'Click map to set position'; }, 2000);
    }

    async _spawn() {
        const type    = this._el.type.value;
        const faction = this._el.faction.value;
        const x = parseFloat(this._el.x.value) || 0;
        const y = parseFloat(this._el.y.value) || 0;

        this._el.error.textContent = '';
        this._el.btn.disabled = true;

        try {
            await this._api.createEntity({ type, faction, position: [x, y, 0] });
            // Nudge default position so next spawn doesn't stack exactly on top
            this._el.x.value = x + 10;
        } catch(e) {
            const msg = e.message || String(e);
            this._el.error.textContent = msg.includes('400')
                ? 'Start simulation first'
                : 'Spawn failed';
        } finally {
            this._el.btn.disabled = false;
        }
    }
}

// ============================================================
// StrategosApp — root singleton, wires everything together
// ============================================================
class StrategosApp {
    constructor() {
        this._api     = new ApiClient();
        this._store   = new EntityStore();
        this._ws      = new WebSocketClient(`ws://${window.location.host}/ws/events`);
        this._canvas  = new CanvasRenderer(document.getElementById('map-canvas'), this._store);
        this._sidebar = new SidebarController(this._api);
        this._right   = new RightPanelController(this._store);
        this._spawn   = new SpawnController(this._api);
        this._zoomEl  = document.getElementById('zoom-label');
    }

    async init() {
        // Entity snapshot
        try {
            const snap = await this._api.getEntities();
            this._store.loadSnapshot(snap.entities || []);
            this._right.refreshEntityList();
            this._canvas.fitToEntities();
        } catch(e) { console.warn('entity snapshot failed:', e); }

        // Initial status + engagements
        try {
            const s = await this._api.getStatus();
            this._sidebar.updateStatus(s);
            this._canvas.simTime = s.current_time || 0;
        } catch(e) {}
        await this._fetchEngagements();

        // Cross-wire canvas ↔ right panel selection
        this._canvas.onEntitySelect = (id) => { this._right.selectEntity(id); };
        this._right.onEntitySelect  = (id) => { this._canvas.selectEntity(id); };

        // Canvas click on empty space → set spawn coordinates
        this._canvas.onMapClick = (wx, wy) => { this._spawn.setPosition(wx, wy); };

        // Zoom toolbar
        const updateZoom = (fn) => { fn(); if (this._zoomEl) this._zoomEl.textContent = this._canvas.getZoomPercent() + '%'; };
        document.getElementById('btn-zoom-in') .addEventListener('click', () => updateZoom(() => this._canvas.zoomIn()));
        document.getElementById('btn-zoom-out').addEventListener('click', () => updateZoom(() => this._canvas.zoomOut()));
        document.getElementById('btn-fit')     .addEventListener('click', () => updateZoom(() => this._canvas.fitToEntities()));

        // WebSocket handlers
        this._ws.on('_connected',    () => this._sidebar.setWsConnected(true));
        this._ws.on('_disconnected', () => this._sidebar.setWsConnected(false));

        this._ws.on('entity.created',   (e) => { this._store.onEntityCreated(e);   this._right.refreshEntityList(); });
        this._ws.on('entity.moved',     (e) => { this._store.onEntityMoved(e); });
        this._ws.on('entity.damaged',   (e) => { this._store.onEntityDamaged(e); });
        this._ws.on('entity.destroyed', (e) => {
            this._right.deselectEntity(e.data?.entity_id);
            this._store.onEntityDestroyed(e);
            this._right.refreshEntityList();
        });
        this._ws.on('unit.destroyed',   () => { this._fetchEngagements(); });

        // Phase 3: engagement events → refresh engagement panel + canvas lines
        this._ws.on('engagement.started', () => this._fetchEngagements());
        this._ws.on('engagement.ended',   () => this._fetchEngagements());

        // Sim lifecycle events → immediate status refresh
        for (const t of ['simulation.started', 'simulation.paused', 'simulation.resumed', 'simulation.stopped', 'time.scaled']) {
            this._ws.on(t, () => this._fetchStatus());
        }

        // All events → event strip
        this._ws.on('*', (e) => this._right.appendEvent(e));

        this._ws.connect();

        // Poll status + engagements every 2s
        setInterval(() => { this._fetchStatus(); this._fetchEngagements(); }, 2000);

        // RAF
        this._canvas.start();

        // Keep zoom label in sync with wheel zoom
        setInterval(() => {
            if (this._zoomEl) this._zoomEl.textContent = this._canvas.getZoomPercent() + '%';
        }, 200);
    }

    async _fetchStatus() {
        try {
            const s = await this._api.getStatus();
            this._sidebar.updateStatus(s);
            this._canvas.simTime = s.current_time || 0;
        } catch(e) {}
    }

    async _fetchEngagements() {
        try {
            const list = await this._api.getEngagements();
            this._canvas.engagements = list;
            this._right.updateEngagements(list);
        } catch(e) {}
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const app = new StrategosApp();
    app.init().catch(console.error);
    window._app = app;  // useful for debugging in console
});
