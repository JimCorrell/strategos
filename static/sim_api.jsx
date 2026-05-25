// ============================================================
// Strategos — API-backed simulation adapter
// Implements the same interface as sim.jsx but drives the
// FastAPI backend instead of running an in-browser simulation.
// ============================================================

const UNIT_TYPES = {
  infantry:  { speed: 22,  hp: 100, firepower: 5,  armor: 2,  range: 50,  cooldown: 0.7, accel: 16, projSpeed: 220, label: 'INF' },
  tank:      { speed: 15,  hp: 300, firepower: 25, armor: 7,  range: 200, cooldown: 1.4, accel: 10, projSpeed: 320, label: 'TNK' },
  aircraft:  { speed: 40,  hp: 150, firepower: 20, armor: 2,  range: 300, cooldown: 1.1, accel: 60, projSpeed: 500, label: 'AIR' },
  artillery: { speed: 9,   hp: 110, firepower: 30, armor: 5,  range: 280, cooldown: 3.2, accel: 6,  projSpeed: 180, label: 'ART' },
};

function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
function len(x, y) { return Math.hypot(x, y); }

// ============================================================
// SimApiClient — wraps FastAPI + WebSocket
// ============================================================
class SimApiClient {
  constructor() {
    this.entities    = new Map();
    this.engagements = [];
    this.projectiles = [];
    this.explosions  = [];
    this.events      = [];
    this.markers     = [];
    this.time        = 0;
    this.timeScale   = 1.0;
    this.state       = 'stopped';
    this.entityCount = 0;
    this.eventCount  = 0;

    this.listeners   = new Set();
    this._ws         = null;
    this._pollId     = null;
    this._loopActive = false;
    this._lastLoopAt = null;
    this._lastReinforceAt = -99;
  }

  // -------- pub/sub --------
  subscribe(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  _emit(type) { for (const fn of this.listeners) fn(type, this); }

  // -------- REST helpers --------
  async _api(path, opts = {}) {
    const method = opts.method || 'GET';
    const init = { method, headers: { 'Content-Type': 'application/json' } };
    if (opts.body !== undefined) init.body = JSON.stringify(opts.body);
    const r = await fetch(path, init);
    if (!r.ok) {
      const text = await r.text().catch(() => r.statusText);
      throw new Error(`${method} ${path} → ${r.status}: ${text}`);
    }
    return r.json();
  }

  // -------- WebSocket --------
  _connectWS() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${location.host}/ws/events`;
    const ws = new WebSocket(url);
    this._ws = ws;

    ws.onopen = () => console.log('[sim_api] WS connected');
    ws.onclose = () => {
      console.warn('[sim_api] WS closed, reconnecting in 2s');
      setTimeout(() => this._connectWS(), 2000);
    };
    ws.onerror = (e) => console.warn('[sim_api] WS error', e);
    ws.onmessage = (e) => {
      try { this._handleWsEvent(JSON.parse(e.data)); }
      catch (err) { console.warn('[sim_api] WS parse error', err); }
    };
  }

  _handleWsEvent(msg) {
    const type = msg.event_type;
    const data = msg.data || {};
    const simTime = msg.simulation_time || this.time;

    const ev = {
      id: ++this.eventCount,
      time: simTime,
      type,
      data,
      severity: 'info',
    };
    this.events.push(ev);
    if (this.events.length > 400) this.events.shift();

    if (type === 'entity.moved') {
      const ent = this.entities.get(data.id);
      if (ent) {
        ent.x = data.position?.[0] ?? ent.x;
        ent.y = data.position?.[1] ?? ent.y;
        ent.vx = data.velocity?.[0] ?? ent.vx;
        ent.vy = data.velocity?.[1] ?? ent.vy;
        ent.heading = data.heading ?? ent.heading;
        ent.speed = len(ent.vx, ent.vy);
      }
    } else if (type === 'entity.damaged') {
      const ent = this.entities.get(data.entity_id);
      if (ent) {
        ent.hp = data.health_after ?? data.new_health ?? ent.hp;
        ent.lastHit = simTime;
        ent.hpHistory.push(ent.hp / ent.max_hp);
        if (ent.hpHistory.length > 40) ent.hpHistory.shift();
        // explosion at entity position
        this.explosions.push({ x: ent.x, y: ent.y, birth: simTime, ttl: 0.35, big: false });
      }
    } else if (type === 'unit.destroyed' || type === 'entity.destroyed') {
      const id = data.entity_id || data.id;
      const ent = this.entities.get(id);
      if (ent) {
        ent.destroyed = true;
        ent._destroyedAt = simTime;
        this.explosions.push({ x: ent.x, y: ent.y, birth: simTime, ttl: 0.6, big: true });
        this.engagements = this.engagements.filter(e => e.a !== id && e.b !== id);
      }
    } else if (type === 'entity.created') {
      // The poll will pick it up; nothing needed here
    } else if (type === 'engagement.started') {
      const existing = this.engagements.find(
        e => (e.a === data.entity_a && e.b === data.entity_b) ||
             (e.a === data.entity_b && e.b === data.entity_a)
      );
      if (!existing) {
        this.engagements.push({
          a: data.entity_a,
          b: data.entity_b,
          startedAt: data.started_at || simTime,
          lastFire: simTime,
        });
      }
    } else if (type === 'engagement.ended') {
      this.engagements = this.engagements.filter(
        e => !(e.a === data.entity_a && e.b === data.entity_b) &&
             !(e.a === data.entity_b && e.b === data.entity_a)
      );
    } else if (type === 'engagement.fire') {
      const shooter = this.entities.get(data.shooter || data.entity_a);
      const target  = this.entities.get(data.target  || data.entity_b);
      if (shooter && target) this._synthesizeProjectile(shooter, target);
      // mark engagement lastFire
      const eng = this.engagements.find(
        e => (e.a === (data.shooter || data.entity_a) && e.b === (data.target || data.entity_b)) ||
             (e.b === (data.shooter || data.entity_a) && e.a === (data.target || data.entity_b))
      );
      if (eng) eng.lastFire = simTime;
    }

    this._emit('ws');
  }

  // -------- Polling --------
  _startPoll() {
    if (this._pollId) return;
    this._pollId = setInterval(() => this._poll(), 500);
    this._poll();
  }

  _stopPoll() {
    if (this._pollId) { clearInterval(this._pollId); this._pollId = null; }
  }

  async _poll() {
    try {
      const [statusRes, entitiesRes, engagementsRes] = await Promise.all([
        this._api('/status'),
        this._api('/entities'),
        this._api('/engagements'),
      ]);

      this.time      = statusRes.current_time ?? this.time;
      this.timeScale = statusRes.time_scale ?? this.timeScale;
      this.state     = statusRes.is_running
        ? 'running'
        : (statusRes.clock_state === 'paused' ? 'paused' : 'stopped');

      // Merge entities
      const incoming = new Set();
      for (const apiEnt of (entitiesRes.entities || [])) {
        const norm = this._normalizeEntity(apiEnt);
        incoming.add(norm.id);
        const existing = this.entities.get(norm.id);
        if (existing) {
          // Preserve visual-only and AI fields; update authoritative fields
          Object.assign(existing, {
            x: norm.x, y: norm.y,
            vx: norm.vx, vy: norm.vy,
            heading: norm.heading, speed: norm.speed,
            hp: norm.hp, max_hp: norm.max_hp,
            firepower: norm.firepower, armor: norm.armor,
            range: norm.range, morale: norm.morale,
            faction: norm.faction, type: norm.type,
          });
        } else {
          this.entities.set(norm.id, norm);
          this.entityCount += 1;
        }
      }
      // Mark entities not returned as destroyed (they may have been removed)
      for (const [id, ent] of this.entities) {
        if (!incoming.has(id) && !ent.destroyed) {
          ent.destroyed = true;
          ent._destroyedAt = this.time;
        }
      }

      // Merge engagements (keep lastFire from WS, fill gaps from poll)
      const pollEngMap = new Map();
      for (const apiEng of (engagementsRes || [])) {
        const key = [apiEng.entity_a, apiEng.entity_b].sort().join(':');
        pollEngMap.set(key, {
          a: apiEng.entity_a,
          b: apiEng.entity_b,
          startedAt: apiEng.started_at,
          lastFire: apiEng.started_at,
        });
      }
      // Preserve WS-enriched engagements, add any new from poll
      const kept = [];
      for (const eng of this.engagements) {
        const key = [eng.a, eng.b].sort().join(':');
        if (pollEngMap.has(key)) { kept.push(eng); pollEngMap.delete(key); }
      }
      for (const eng of pollEngMap.values()) kept.push(eng);
      this.engagements = kept;

      this._emit('tick');
    } catch (err) {
      console.warn('[sim_api] poll error', err);
    }
  }

  // -------- Entity normalization --------
  _normalizeEntity(apiEnt) {
    const spec = UNIT_TYPES[apiEnt.type] || UNIT_TYPES.infantry;
    const existing = this.entities.get(apiEnt.entity_id);
    return {
      id:         apiEnt.entity_id,
      type:       apiEnt.type,
      faction:    apiEnt.faction || 'neutral',
      x:          apiEnt.position?.[0] ?? 0,
      y:          apiEnt.position?.[1] ?? 0,
      vx:         apiEnt.velocity?.[0] ?? 0,
      vy:         apiEnt.velocity?.[1] ?? 0,
      heading:    apiEnt.heading ?? 0,
      speed:      apiEnt.speed ?? 0,
      max_speed:  apiEnt.max_speed ?? spec.speed,
      hp:         apiEnt.health ?? spec.hp,
      max_hp:     apiEnt.max_health ?? spec.hp,
      firepower:  apiEnt.firepower ?? spec.firepower,
      armor:      apiEnt.armor ?? spec.armor,
      range:      apiEnt.engagement_range ?? spec.range,
      morale:     apiEnt.morale ?? 75,
      // AI / visual fields (preserve from existing entity if already tracked)
      target:     existing?.target ?? null,
      lastFire:   existing?.lastFire ?? -10,
      lastHit:    existing?.lastHit ?? -10,
      hpHistory:  existing?.hpHistory ?? [],
      destroyed:  apiEnt.destroyed_at != null,
      _destroyedAt: apiEnt.destroyed_at != null ? (existing?._destroyedAt ?? this.time) : undefined,
      bornAt:     apiEnt.created_at ?? 0,
      spec,
      accel:      spec.accel,
      projSpeed:  spec.projSpeed,
      cooldown:   spec.cooldown,
    };
  }

  // -------- Synthetic visual effects --------
  _synthesizeProjectile(shooter, target) {
    const dx = target.x - shooter.x, dy = target.y - shooter.y;
    const d = len(dx, dy) || 1;
    const tof = d / (shooter.projSpeed || 300);
    const px = target.x + (target.vx || 0) * tof + (Math.random() - 0.5) * 12;
    const py = target.y + (target.vy || 0) * tof + (Math.random() - 0.5) * 12;

    this.projectiles.push({
      id: ++this.eventCount,
      shooter: shooter.id,
      target: target.id,
      faction: shooter.faction,
      type: shooter.type,
      x: shooter.x, y: shooter.y,
      sx: shooter.x, sy: shooter.y,
      tx: px, ty: py,
      birth: this.time,
      ttl: tof,
      damage: 0,
      arc: shooter.type === 'artillery',
    });
  }

  _tickProjectiles(dt) {
    const survive = [];
    for (const p of this.projectiles) {
      const age = this.time - p.birth;
      const u = clamp(age / (p.ttl || 0.5), 0, 1);
      p.x = p.sx + (p.tx - p.sx) * u;
      p.y = p.sy + (p.ty - p.sy) * u;
      if (u < 1) survive.push(p);
    }
    this.projectiles = survive;
    this.explosions = this.explosions.filter(e => this.time - e.birth < e.ttl);
  }

  // -------- Client-side AI (bridge until Phase 4) --------
  // Runs the same target-seek/fire logic as sim.jsx but issues velocity
  // commands to the backend instead of mutating positions directly.
  _findTarget(ent) {
    let best = null, bestD = Infinity;
    for (const o of this.entities.values()) {
      if (o.destroyed) continue;
      if (o.faction === ent.faction || o.faction === 'neutral') continue;
      const d = len(o.x - ent.x, o.y - ent.y);
      if (d < bestD) { bestD = d; best = o; }
    }
    return best;
  }

  async _tickAI(dt) {
    const velUpdates = [];

    for (const ent of this.entities.values()) {
      if (ent.destroyed) continue;

      if (!ent.target || ent.target.destroyed || !this.entities.has(ent.target.id)) {
        ent.target = this._findTarget(ent);
      }
      const t = ent.target;
      if (!t) continue;

      const dx = t.x - ent.x, dy = t.y - ent.y;
      const d = len(dx, dy) || 1;
      const standoff =
        ent.type === 'artillery' ? ent.range * 0.85 :
        ent.type === 'aircraft'  ? ent.range * 0.6  :
        ent.range * 0.7;

      let desiredVX = 0, desiredVY = 0;
      if (d > standoff) {
        desiredVX = (dx / d) * ent.max_speed;
        desiredVY = (dy / d) * ent.max_speed;
      } else if (d < ent.range * 0.4 && ent.type !== 'tank') {
        desiredVX = -(dx / d) * ent.max_speed * 0.4;
        desiredVY = -(dy / d) * ent.max_speed * 0.4;
      }

      // heading
      const targetHeading = Math.atan2(dy, dx);
      const dh = ((targetHeading - ent.heading + Math.PI * 3) % (Math.PI * 2)) - Math.PI;
      ent.heading += dh * Math.min(1, dt * 4);

      // Only push a velocity update if it changed meaningfully
      const dvx = desiredVX - ent.vx, dvy = desiredVY - ent.vy;
      if (len(dvx, dvy) > 0.5) {
        ent.vx = desiredVX;
        ent.vy = desiredVY;
        velUpdates.push({ id: ent.id, velocity: [desiredVX, desiredVY, 0] });
      }

      ent.x += ent.vx * dt;
      ent.y += ent.vy * dt;
      ent.speed = len(ent.vx, ent.vy);
    }

    // Fire velocity updates to backend in parallel (best-effort)
    if (velUpdates.length > 0) {
      await Promise.allSettled(
        velUpdates.map(u =>
          this._api(`/entities/${u.id}/velocity`, { method: 'POST', body: { velocity: u.velocity } })
        )
      );
    }
  }

  // -------- Client-side reinforce --------
  _reinforce() {
    if (this.time - this._lastReinforceAt < 14) return;
    this._lastReinforceAt = this.time;
    for (const faction of ['blue', 'red']) {
      const alive = Array.from(this.entities.values()).filter(e => e.faction === faction && !e.destroyed);
      if (alive.length > 14) continue;
      const types = ['infantry', 'tank', 'aircraft', 'artillery'];
      const type = types[Math.floor(Math.random() * types.length)];
      const base = faction === 'blue' ? [-300, 60] : [300, -40];
      this.spawnUnit({
        type, faction,
        x: base[0] + (Math.random() - 0.5) * 60,
        y: base[1] + (Math.random() - 0.5) * 80,
      }).catch(() => {});
    }
  }

  // -------- RAF-driven loop (called by renderer) --------
  _loop() {
    if (this.state !== 'running') return;
    const now = performance.now();
    if (!this._lastLoopAt) this._lastLoopAt = now;
    const realDt = Math.min(0.1, (now - this._lastLoopAt) / 1000);
    this._lastLoopAt = now;
    const dt = realDt * this.timeScale;

    this.time += dt;
    this._tickProjectiles(dt);

    // Run AI at 4Hz max to avoid flooding backend with velocity API calls
    if (!this._lastAIAt || now - this._lastAIAt >= 250) {
      this._lastAIAt = now;
      this._tickAI(dt).catch(() => {});
    }

    if (this.time > 0) this._reinforce();
  }

  // -------- Transport --------
  async start() {
    if (this.state === 'running') return;
    await this._api('/start', { method: 'POST' });
    this.state = 'running';
    this._lastLoopAt = null;
    this._connectWS();
    this._startPoll();
    await this._spawnInitialForces();
    this._emit('state');
  }

  async pause() {
    if (this.state !== 'running') return;
    await this._api('/pause', { method: 'POST' });
    this.state = 'paused';
    this._emit('state');
  }

  async resume() {
    if (this.state !== 'paused') return;
    await this._api('/resume', { method: 'POST' });
    this.state = 'running';
    this._lastLoopAt = null;
    this._emit('state');
  }

  async stop() {
    await this._api('/stop', { method: 'POST' });
    this.state = 'stopped';
    this._stopPoll();
    this.entities.clear();
    this.engagements = [];
    this.projectiles = [];
    this.explosions = [];
    this.events = [];
    this.markers = [];
    this.time = 0;
    this.entityCount = 0;
    this.eventCount = 0;
    this._lastReinforceAt = -99;
    this._emit('state');
  }

  async setTimeScale(s) {
    this.timeScale = clamp(s, 0.1, 10);
    await this._api('/time-scale', { method: 'POST', body: { scale: this.timeScale } });
    this._emit('scale');
  }

  seek(t) {
    this._api('/seek', { method: 'POST', body: { target_time: Math.max(0, t) } })
      .then(() => this._emit('time'))
      .catch(() => {});
  }

  addMarker(label) {
    const m = { time: this.time, label, id: `M-${Date.now()}` };
    this.markers.unshift(m);
    this._api('/marker', { method: 'POST', body: { label } }).catch(() => {});
    this._emit('markers');
    return m;
  }

  removeMarker(id) {
    this.markers = this.markers.filter(m => m.id !== id);
    this._emit('markers');
  }

  async spawnUnit({ type, faction, x, y }) {
    const spec = UNIT_TYPES[type] || UNIT_TYPES.infantry;
    const apiEnt = await this._api('/entities', {
      method: 'POST',
      body: {
        type,
        faction,
        position: [x, y, 0],
        max_speed: spec.speed,
        health:           spec.hp,
        max_health:       spec.hp,
        firepower:        spec.firepower,
        armor:            spec.armor,
        engagement_range: spec.range,
        morale:           70 + Math.random() * 30,
      },
    });
    const norm = this._normalizeEntity(apiEnt);
    this.entities.set(norm.id, norm);
    this.entityCount += 1;
    this._emit('spawn');
    return norm;
  }

  // -------- Initial forces (mirrors sim.jsx _spawnInitialForces) --------
  async _spawnInitialForces() {
    const blueBase = [-260, 60], redBase = [260, -40];
    const blueComp = [['tank',2],['infantry',4],['artillery',1],['aircraft',1]];
    const redComp  = [['tank',2],['infantry',4],['artillery',1],['aircraft',1]];

    const spawns = [];
    for (const [type, n] of blueComp) {
      for (let i = 0; i < n; i++) {
        const a = (i / n) * Math.PI - Math.PI / 2;
        const r = 40 + Math.random() * 30;
        spawns.push({ type, faction: 'blue',
          x: blueBase[0] + Math.cos(a) * r,
          y: blueBase[1] + Math.sin(a) * r * 0.7 });
      }
    }
    for (const [type, n] of redComp) {
      for (let i = 0; i < n; i++) {
        const a = (i / n) * Math.PI + Math.PI / 2;
        const r = 40 + Math.random() * 30;
        spawns.push({ type, faction: 'red',
          x: redBase[0] + Math.cos(a) * r,
          y: redBase[1] + Math.sin(a) * r * 0.7 });
      }
    }

    // Sequential spawns to avoid hammering the backend
    for (const s of spawns) {
      await this.spawnUnit(s).catch(() => {});
    }
  }

  // -------- Status snapshot (same shape as sim.jsx) --------
  status() {
    let blueHp = 0, redHp = 0, blueN = 0, redN = 0;
    for (const e of this.entities.values()) {
      if (e.destroyed) continue;
      if (e.faction === 'blue') { blueHp += e.hp; blueN += 1; }
      else if (e.faction === 'red') { redHp += e.hp; redN += 1; }
    }
    return {
      time: this.time,
      state: this.state,
      timeScale: this.timeScale,
      entities: this.entities.size,
      events: this.eventCount,
      engagements: this.engagements.length,
      blueHp, redHp, blueN, redN,
    };
  }
}

window.Sim = SimApiClient;
window.UNIT_TYPES = UNIT_TYPES;
