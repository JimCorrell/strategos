// ============================================================
// Strategos — built-in autonomous sim engine
// ============================================================

const UNIT_TYPES = {
  infantry:  { speed: 22,  hp: 60,  firepower: 5,  armor: 2,  range: 70,  cooldown: 0.7, accel: 16, projSpeed: 220, label: 'INF' },
  tank:      { speed: 18,  hp: 220, firepower: 18, armor: 16, range: 120, cooldown: 1.4, accel: 10, projSpeed: 320, label: 'TNK' },
  aircraft:  { speed: 80,  hp: 80,  firepower: 14, armor: 4,  range: 100, cooldown: 1.1, accel: 60, projSpeed: 500, label: 'AIR' },
  artillery: { speed: 9,   hp: 110, firepower: 30, armor: 5,  range: 280, cooldown: 3.2, accel: 6,  projSpeed: 180, label: 'ART' },
};

let _id = 0;
const nextId = (prefix) => {
  _id += 1;
  return `${prefix}-${_id.toString(16).toUpperCase().padStart(4, '0')}`;
};

function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
function len(x, y) { return Math.hypot(x, y); }

class Sim {
  constructor() {
    this.entities = new Map();      // id → entity
    this.engagements = [];          // [{a, b}]
    this.projectiles = [];          // animated tracers (visual + damage)
    this.explosions = [];           // ephemeral fx
    this.events = [];               // event log
    this.markers = [];              // user-placed time markers
    this.time = 0;
    this.timeScale = 1.0;
    this.state = 'stopped';
    this.entityCount = 0;
    this.eventCount = 0;

    this.listeners = new Set();
    this._lastReinforce = 0;
    this._lastTick = null;
    this._raf = null;
  }

  // -------- pub/sub ----------
  subscribe(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  _emit(type) {
    for (const fn of this.listeners) fn(type, this);
  }

  // -------- events log -------
  _logEvent(type, data, opts = {}) {
    const ev = {
      id: ++this.eventCount,
      time: this.time,
      type,
      data,
      severity: opts.severity || 'info',
    };
    this.events.push(ev);
    if (this.events.length > 400) this.events.shift();
    return ev;
  }

  // -------- transport --------
  start() {
    if (this.state === 'running') return;
    if (this.state === 'stopped') {
      this.time = 0;
      this.entities.clear();
      this.engagements = [];
      this.projectiles = [];
      this.explosions = [];
      this.events = [];
      this.markers = [];
      this._lastReinforce = -3;
      this._spawnInitialForces();
    }
    this.state = 'running';
    this._lastTick = performance.now();
    this._logEvent('simulation.started', {});
    this._startLoop();
    this._emit('state');
  }

  pause() {
    if (this.state !== 'running') return;
    this.state = 'paused';
    this._stopLoop();
    this._logEvent('simulation.paused', {});
    this._emit('state');
  }

  resume() {
    if (this.state !== 'paused') return;
    this.state = 'running';
    this._lastTick = performance.now();
    this._logEvent('simulation.resumed', {});
    this._startLoop();
    this._emit('state');
  }

  stop() {
    this.state = 'stopped';
    this._stopLoop();
    this._logEvent('simulation.stopped', {});
    this._emit('state');
  }

  setTimeScale(s) {
    this.timeScale = clamp(s, 0.1, 10);
    this._logEvent('time.scaled', { scale: this.timeScale });
    this._emit('scale');
  }

  seek(t) {
    // soft seek — clamp
    this.time = Math.max(0, t);
    this._emit('time');
  }

  addMarker(label) {
    const m = { time: this.time, label, id: nextId('M') };
    this.markers.unshift(m);
    this._logEvent('marker.added', { label, time: this.time }, { severity: 'note' });
    this._emit('markers');
    return m;
  }
  removeMarker(id) {
    this.markers = this.markers.filter((m) => m.id !== id);
    this._emit('markers');
  }

  // -------- spawning --------
  spawnUnit({ type, faction, x, y, suppressEvent = false }) {
    const spec = UNIT_TYPES[type] || UNIT_TYPES.infantry;
    const id = nextId(faction === 'blue' ? 'B' : faction === 'red' ? 'R' : 'N');
    const ent = {
      id,
      type,
      faction,
      x, y,
      vx: 0, vy: 0,
      heading: faction === 'blue' ? 0 : Math.PI,
      speed: 0,
      max_speed: spec.speed,
      hp: spec.hp,
      max_hp: spec.hp,
      firepower: spec.firepower,
      armor: spec.armor,
      range: spec.range,
      cooldown: spec.cooldown,
      accel: spec.accel,
      projSpeed: spec.projSpeed,
      morale: 70 + Math.random() * 30,
      target: null,
      lastFire: -10,
      lastHit: -10,
      hpHistory: [],          // for sparkline
      destroyed: false,
      bornAt: this.time,
      spec,
    };
    this.entities.set(id, ent);
    this.entityCount += 1;
    if (!suppressEvent) {
      this._logEvent('entity.created', { id, type, faction, x, y });
    }
    return ent;
  }

  // initial scenario: small skirmish around two bases
  _spawnInitialForces() {
    // Bases positioned so default zoom shows both sides
    const blueBase = [-260, 60];
    const redBase  = [ 260, -40];

    const blueComp = [
      ['tank', 2], ['infantry', 4], ['artillery', 1], ['aircraft', 1],
    ];
    const redComp = [
      ['tank', 2], ['infantry', 4], ['artillery', 1], ['aircraft', 1],
    ];

    for (const [type, n] of blueComp) {
      for (let i = 0; i < n; i++) {
        const a = (i / n) * Math.PI - Math.PI / 2;
        const r = 40 + Math.random() * 30;
        this.spawnUnit({
          type, faction: 'blue',
          x: blueBase[0] + Math.cos(a) * r,
          y: blueBase[1] + Math.sin(a) * r * 0.7,
        });
      }
    }
    for (const [type, n] of redComp) {
      for (let i = 0; i < n; i++) {
        const a = (i / n) * Math.PI + Math.PI / 2;
        const r = 40 + Math.random() * 30;
        this.spawnUnit({
          type, faction: 'red',
          x: redBase[0] + Math.cos(a) * r,
          y: redBase[1] + Math.sin(a) * r * 0.7,
        });
      }
    }
  }

  _reinforce() {
    // Periodic reinforcements every ~12-18s of sim time
    if (this.time - this._lastReinforce < 12 + Math.random() * 6) return;
    this._lastReinforce = this.time;
    const factions = ['blue', 'red'];
    for (const faction of factions) {
      const alive = Array.from(this.entities.values()).filter(
        (e) => e.faction === faction && !e.destroyed
      );
      if (alive.length > 14) continue;
      const types = ['infantry', 'tank', 'aircraft', 'artillery'];
      const t = types[Math.floor(Math.random() * types.length)];
      const base = faction === 'blue' ? [-300, 60] : [300, -40];
      this.spawnUnit({
        type: t, faction,
        x: base[0] + (Math.random() - 0.5) * 60,
        y: base[1] + (Math.random() - 0.5) * 80,
      });
    }
  }

  // -------- AI / tick --------
  _findTarget(ent) {
    let best = null, bestD = Infinity;
    for (const o of this.entities.values()) {
      if (o.destroyed) continue;
      if (o.faction === ent.faction) continue;
      if (o.faction === 'neutral') continue;
      const d = len(o.x - ent.x, o.y - ent.y);
      if (d < bestD) { bestD = d; best = o; }
    }
    return best;
  }

  _tickEntity(ent, dt) {
    if (ent.destroyed) return;

    // Track HP history (1 sample per ~0.5s)
    if (!ent._lastHpSample || this.time - ent._lastHpSample > 0.5) {
      ent.hpHistory.push(ent.hp / ent.max_hp);
      if (ent.hpHistory.length > 40) ent.hpHistory.shift();
      ent._lastHpSample = this.time;
    }

    // Pick target
    if (!ent.target || ent.target.destroyed || !this.entities.has(ent.target.id)) {
      ent.target = this._findTarget(ent);
    }
    const t = ent.target;

    let desiredVX = 0, desiredVY = 0;
    if (t) {
      const dx = t.x - ent.x, dy = t.y - ent.y;
      const d = len(dx, dy) || 1;
      const inRange = d <= ent.range * 0.95;
      // Artillery keeps distance; infantry/tank/aircraft close in
      const standoff =
        ent.type === 'artillery' ? ent.range * 0.85 :
        ent.type === 'aircraft'  ? ent.range * 0.6  :
        ent.range * 0.7;

      if (d > standoff) {
        desiredVX = (dx / d) * ent.max_speed;
        desiredVY = (dy / d) * ent.max_speed;
      } else if (d < ent.range * 0.4 && ent.type !== 'tank') {
        // back off a bit
        desiredVX = -(dx / d) * ent.max_speed * 0.4;
        desiredVY = -(dy / d) * ent.max_speed * 0.4;
      }

      // Fire?
      if (inRange && this.time - ent.lastFire >= ent.cooldown) {
        this._fire(ent, t);
      }

      // heading toward target
      const targetHeading = Math.atan2(dy, dx);
      const dh = ((targetHeading - ent.heading + Math.PI * 3) % (Math.PI * 2)) - Math.PI;
      ent.heading += dh * Math.min(1, dt * 4);
    }

    // smooth accel toward desired vel
    const accelStep = ent.accel * dt;
    const dvx = desiredVX - ent.vx, dvy = desiredVY - ent.vy;
    const dvm = len(dvx, dvy);
    if (dvm > accelStep) {
      ent.vx += (dvx / dvm) * accelStep;
      ent.vy += (dvy / dvm) * accelStep;
    } else {
      ent.vx = desiredVX;
      ent.vy = desiredVY;
    }
    ent.x += ent.vx * dt;
    ent.y += ent.vy * dt;
    ent.speed = len(ent.vx, ent.vy);

    // World bounds (gentle)
    if (Math.abs(ent.x) > 900) ent.x = Math.sign(ent.x) * 900;
    if (Math.abs(ent.y) > 600) ent.y = Math.sign(ent.y) * 600;
  }

  _fire(ent, target) {
    ent.lastFire = this.time;
    // Predict where target will be when projectile arrives
    const dx = target.x - ent.x, dy = target.y - ent.y;
    const d = len(dx, dy);
    const tof = d / ent.projSpeed;
    const px = target.x + target.vx * tof + (Math.random() - 0.5) * 12;
    const py = target.y + target.vy * tof + (Math.random() - 0.5) * 12;

    this.projectiles.push({
      id: ++this.eventCount,
      shooter: ent.id,
      target: target.id,
      faction: ent.faction,
      type: ent.type,
      x: ent.x, y: ent.y,
      sx: ent.x, sy: ent.y,
      tx: px, ty: py,
      birth: this.time,
      ttl: tof,
      damage: Math.max(1, ent.firepower - target.armor * 0.4) + Math.random() * 3,
      arc: ent.type === 'artillery',
    });

    this._logEvent('engagement.fire', {
      shooter: ent.id, target: target.id,
      type: ent.type, faction: ent.faction,
    });

    // Track engagement
    const existing = this.engagements.find(
      (e) => (e.a === ent.id && e.b === target.id) || (e.a === target.id && e.b === ent.id)
    );
    if (!existing) {
      this.engagements.push({
        a: ent.id, b: target.id,
        startedAt: this.time,
        lastFire: this.time,
      });
    } else {
      existing.lastFire = this.time;
    }
  }

  _tickProjectiles(dt) {
    const survive = [];
    for (const p of this.projectiles) {
      const age = this.time - p.birth;
      const u = clamp(age / p.ttl, 0, 1);
      // arc projectiles get a parabolic Y bump (visual only — applied in renderer)
      p.x = p.sx + (p.tx - p.sx) * u;
      p.y = p.sy + (p.ty - p.sy) * u;
      if (u >= 1) {
        // impact: try to find a target near impact (the original or any nearby)
        let victim = this.entities.get(p.target);
        if (!victim || victim.destroyed) {
          // collateral search
          for (const o of this.entities.values()) {
            if (o.destroyed) continue;
            if (o.faction === p.faction) continue;
            if (len(o.x - p.x, o.y - p.y) < 18) { victim = o; break; }
          }
        }
        if (victim && !victim.destroyed) {
          victim.hp -= p.damage;
          victim.lastHit = this.time;
          this._logEvent('entity.damaged', {
            id: victim.id, dmg: +p.damage.toFixed(1), hp_after: victim.hp,
          });
          if (victim.hp <= 0) this._destroyEntity(victim, p.shooter);
        }
        // small explosion fx
        this.explosions.push({
          x: p.x, y: p.y,
          birth: this.time,
          ttl: p.arc ? 0.6 : 0.35,
          big: p.arc,
        });
        continue;
      }
      survive.push(p);
    }
    this.projectiles = survive;

    // clean explosions
    this.explosions = this.explosions.filter((e) => this.time - e.birth < e.ttl);
  }

  _destroyEntity(ent, by) {
    ent.destroyed = true;
    this._logEvent('entity.destroyed', { id: ent.id, by });
    // grace before removal so we can fade in render
    ent._destroyedAt = this.time;
    // clean engagements involving this
    this.engagements = this.engagements.filter(
      (e) => e.a !== ent.id && e.b !== ent.id
    );
  }

  _cleanDestroyed() {
    for (const [id, ent] of this.entities) {
      if (ent.destroyed && this.time - ent._destroyedAt > 1.4) {
        this.entities.delete(id);
      }
    }
  }

  _cleanEngagements() {
    this.engagements = this.engagements.filter((e) => {
      const a = this.entities.get(e.a), b = this.entities.get(e.b);
      if (!a || !b || a.destroyed || b.destroyed) return false;
      // expire engagements that haven't fired in 3 seconds
      return this.time - e.lastFire < 3;
    });
  }

  // -------- main loop --------
  _loop() {
    if (this.state !== 'running') return;
    const now = performance.now();
    const realDt = (now - this._lastTick) / 1000;
    this._lastTick = now;
    // Sub-step so heavy iframe throttling doesn't break physics.
    // Cap total step at 1s of sim time per call.
    const dt = Math.min(1.0, realDt * this.timeScale);
    const STEP = 0.04;
    let remaining = dt;
    while (remaining > 0) {
      const step = Math.min(STEP, remaining);
      this.time += step;
      for (const ent of this.entities.values()) {
        this._tickEntity(ent, step);
      }
      this._tickProjectiles(step);
      remaining -= step;
    }
    this._cleanEngagements();
    this._cleanDestroyed();
    this._reinforce();

    this._emit('tick');
  }

  _startLoop() {
    // Loop is driven by renderer's RAF for reliability across iframe throttling.
    // Keep a setTimeout fallback so paused renderer doesn't completely freeze sim.
    if (this._loopActive) return;
    this._loopActive = true;
    const fallback = () => {
      if (!this._loopActive) return;
      this._loop();
      this._timeoutId = setTimeout(fallback, 250);
    };
    this._timeoutId = setTimeout(fallback, 250);
  }
  _stopLoop() {
    this._loopActive = false;
    if (this._timeoutId) { clearTimeout(this._timeoutId); this._timeoutId = null; }
    if (this._intervalId) { clearInterval(this._intervalId); this._intervalId = null; }
  }

  // -------- snapshots --------
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

// expose
window.Sim = Sim;
window.UNIT_TYPES = UNIT_TYPES;
