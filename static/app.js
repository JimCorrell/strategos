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
const TYPE_COLORS = {
    infantry: '#22c55e',
    tank:     '#f59e0b',
    aircraft: '#06b6d4',
    ship:     '#818cf8',
    artillery:'#fb923c',
};

function entityColor(entity) {
    return TYPE_COLORS[entity.type] || '#94a3b8';
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
            entity_id:       d.entity_id,
            type:            d.type || 'unknown',
            position:        d.position || [0, 0, 0],
            velocity:        [0, 0, 0],
            heading:         0,
            speed:           0,
            max_speed:       d.max_speed || 0,
            metadata:        d.metadata || {},
            last_update_time: event.simulation_time || 0,
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

    // ---- entities ----
    _drawEntities(ctx) {
        const showLabels = this._zoom > 0.3;

        for (const entity of this._store.entities.values()) {
            const pos = this._store.getInterpolatedPosition(entity, this.simTime);
            const [sx, sy] = this._w2s(pos[0], pos[1]);
            const isSelected = entity.entity_id === this._selectedId;
            const color = entityColor(entity);

            if (isSelected) {
                ctx.beginPath();
                ctx.arc(sx, sy, 10, 0, Math.PI * 2);
                ctx.strokeStyle = 'rgba(255,255,255,0.85)';
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }

            ctx.beginPath();
            ctx.arc(sx, sy, isSelected ? 7 : 5, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();

            // heading line when moving
            if (entity.speed > 0.001) {
                const h = entity.heading || 0;
                const len = 14;
                ctx.beginPath();
                ctx.moveTo(sx, sy);
                ctx.lineTo(sx + Math.cos(h) * len, sy - Math.sin(h) * len);
                ctx.strokeStyle = color;
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }

            if (showLabels) {
                ctx.fillStyle = 'rgba(241,245,249,0.65)';
                ctx.font = '9px Monaco, monospace';
                ctx.fillText(entity.entity_id.substring(0, 8), sx + 8, sy - 4);
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
            header:    document.getElementById('entity-list-header'),
            list:      document.getElementById('entity-list'),
            inspector: document.getElementById('inspector-content'),
            events:    document.getElementById('event-list'),
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
        const pos = entity.position || [0, 0, 0];
        const vel = entity.velocity || [0, 0, 0];
        const deg = ((entity.heading || 0) * 180 / Math.PI).toFixed(1);
        const rows = [
            ['id',      entity.entity_id.substring(0, 8) + '…'],
            ['type',    entity.type],
            ['x',       pos[0].toFixed(2)],
            ['y',       pos[1].toFixed(2)],
            ['z',       pos[2].toFixed(2)],
            ['heading', deg + '°'],
            ['speed',   (entity.speed || 0).toFixed(2)],
            ['max_spd', (entity.max_speed || 0).toFixed(2)],
            ['vel x',   vel[0].toFixed(3)],
            ['vel y',   vel[1].toFixed(3)],
        ];
        this._el.inspector.innerHTML = rows
            .map(([k, v]) => `<div class="insp-row"><span>${k}</span><span class="insp-val">${v}</span></div>`)
            .join('');
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

        // Initial status
        try {
            const s = await this._api.getStatus();
            this._sidebar.updateStatus(s);
            this._canvas.simTime = s.current_time || 0;
        } catch(e) {}

        // Cross-wire canvas ↔ right panel selection
        this._canvas.onEntitySelect = (id) => { this._right.selectEntity(id); };
        this._right.onEntitySelect  = (id) => { this._canvas.selectEntity(id); };

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
        this._ws.on('entity.destroyed', (e) => {
            this._right.deselectEntity(e.data?.entity_id);
            this._store.onEntityDestroyed(e);
            this._right.refreshEntityList();
        });

        // Sim lifecycle events → immediate status refresh
        for (const t of ['simulation.started', 'simulation.paused', 'simulation.resumed', 'simulation.stopped', 'time.scaled']) {
            this._ws.on(t, () => this._fetchStatus());
        }

        // All events → event strip
        this._ws.on('*', (e) => this._right.appendEvent(e));

        this._ws.connect();

        // Status poll every 2s
        setInterval(() => this._fetchStatus(), 2000);

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
}

document.addEventListener('DOMContentLoaded', () => {
    const app = new StrategosApp();
    app.init().catch(console.error);
    window._app = app;  // useful for debugging in console
});
