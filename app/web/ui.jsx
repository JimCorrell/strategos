// ============================================================
// Strategos — UI panels (sidebar, right rail, topbar, timeline, palette)
// ============================================================
const { useEffect, useRef, useState, useMemo, useCallback } = React;

const FAC_COLORS = { blue: '#4ea3ff', red: '#ff5b5b', neutral: '#9aa3b2' };

function fmtTime(t) {
  const s = Math.max(0, t);
  const m = Math.floor(s / 60);
  const sec = (s - m * 60).toFixed(1);
  return `${m.toString().padStart(2, '0')}:${sec.padStart(4, '0')}`;
}

// ============================================================
// TopBar
// ============================================================
function TopBar({ status, audioOn, onAudioToggle, onPalette }) {
  const totalHp = (status.blueHp || 0) + (status.redHp || 0);
  const bluePct = totalHp ? (status.blueHp / totalHp) * 100 : 50;
  const redPct  = totalHp ? (status.redHp  / totalHp) * 100 : 50;

  return (
    <header className="topbar" data-screen-label="01 Topbar">
      <div className="brand">
        <div className="brand-mark"><span /></div>
        <div className="brand-text">
          <div className="brand-name">STRATEGOS</div>
          <div className="brand-sub">C2 · OP. NIGHTHAWK</div>
        </div>
      </div>

      <div className="force-balance">
        <div className="fb-side">
          <span>Blue Force</span>
          <span className="pct">{bluePct.toFixed(0)}%</span>
        </div>
        <div className="fb-bar">
          <div className="fb-fill-blue" style={{ width: `${bluePct}%` }} />
          <div className="fb-fill-red"  style={{ width: `${redPct}%` }} />
          <div className="fb-divider" style={{ left: `${bluePct}%` }} />
        </div>
        <div className="fb-side right">
          <span>Red Force</span>
          <span className="pct">{redPct.toFixed(0)}%</span>
        </div>
      </div>

      <div className="topbar-right">
        <div className="meta-cell">
          <div className="label">Op Clock</div>
          <div className="value amber">{fmtTime(status.time)}</div>
        </div>
        <div className="meta-cell">
          <div className="label">Net Status</div>
          <div className="value live">SECURE</div>
        </div>
        <div className="kbd-hint" onClick={onPalette} title="Command palette">
          <span>cmd</span><kbd>⌘K</kbd>
        </div>
        <div className={'audio-toggle' + (audioOn ? ' on' : '')} onClick={onAudioToggle} title="Audio FX">
          {audioOn ? '♪' : '×'}
        </div>
      </div>
    </header>
  );
}

// ============================================================
// LeftRail — transport, time, spawn, markers
// ============================================================
function LeftRail({ sim, status, spawn, setSpawn, onSpawn, markers, onAddMarker, onRemoveMarker, audio }) {
  const [scale, setScale] = useState(status.timeScale);
  const [pending, setPending] = useState(false);
  const [markerLabel, setMarkerLabel] = useState('');

  useEffect(() => {
    if (!pending) setScale(status.timeScale);
  }, [status.timeScale, pending]);

  const applyScale = () => {
    sim.setTimeScale(scale);
    setPending(false);
    audio && audio.click();
  };

  const run = (fn) => { fn(); audio && audio.click(); };

  const stateCls = status.state === 'running' ? 'running' : status.state === 'paused' ? 'paused' : '';

  return (
    <aside className="rail left" data-screen-label="02 Left rail">
      {/* SIM section */}
      <div className="rail-section">
        <div className="section-head no-x" style={{ paddingLeft: 0, marginBottom: 10 }}>
          <span className="dot" />
          <span>SIMULATION</span>
          <span className="spacer" />
          <span className={'state-pill ' + stateCls}>
            <span className="d" />
            {status.state}
          </span>
        </div>

        <div className="clock-readout">
          <span className="time">{fmtTime(status.time)}</span>
          <span className="scale">SCALE <strong>{status.timeScale.toFixed(1)}×</strong></span>
        </div>

        <div className="transport">
          <button className={'t-btn' + (status.state === 'stopped' ? '' : '')}
                  disabled={status.state === 'running'}
                  onClick={() => run(() => sim.start())}>
            <span className="icon">▶</span> START
          </button>
          <button className="t-btn"
                  disabled={status.state !== 'running'}
                  onClick={() => run(() => sim.pause())}>
            <span className="icon">⏸</span> PAUSE
          </button>
          <button className="t-btn"
                  disabled={status.state !== 'paused'}
                  onClick={() => run(() => sim.resume())}>
            <span className="icon">⏵</span> RESUME
          </button>
          <button className="t-btn danger"
                  disabled={status.state === 'stopped'}
                  onClick={() => run(() => sim.stop())}>
            <span className="icon">■</span> STOP
          </button>
        </div>

        <div className="stat-grid">
          <div className="stat-cell"><div className="k">UNITS</div><div className="v">{status.entities}</div></div>
          <div className="stat-cell"><div className="k">EVENTS</div><div className="v">{status.events}</div></div>
          <div className="stat-cell"><div className="k">ENG.</div><div className="v">{status.engagements}</div></div>
        </div>
      </div>

      {/* TIME SCALE */}
      <div className="rail-section">
        <div className="section-head no-x" style={{ paddingLeft: 0 }}>
          <span className="dot" />
          <span>TIME SCALE</span>
          {pending && <span className="pending-tag">PENDING</span>}
        </div>
        <div className="slider-row">
          <input type="range" min="0.1" max="10" step="0.1" value={scale}
                 onChange={(e) => { setScale(parseFloat(e.target.value)); setPending(true); }} />
          <span className="val">{scale.toFixed(1)}×</span>
        </div>
        <button className="primary-btn" style={{ marginTop: 8 }} onClick={applyScale}>Apply</button>
      </div>

      {/* SPAWN */}
      <div className="rail-section">
        <div className="section-head no-x" style={{ paddingLeft: 0 }}>
          <span className="dot" />
          <span>SPAWN UNIT</span>
        </div>

        <div className="field">
          <div className="field-label">Faction</div>
          <div className="seg">
            <button className={'blue' + (spawn.faction === 'blue' ? ' active blue' : '')}
                    onClick={() => setSpawn({ ...spawn, faction: 'blue' })}>BLUE</button>
            <button className={'red' + (spawn.faction === 'red' ? ' active red' : '')}
                    onClick={() => setSpawn({ ...spawn, faction: 'red' })}>RED</button>
            <button className={'amber' + (spawn.faction === 'neutral' ? ' active amber' : '')}
                    onClick={() => setSpawn({ ...spawn, faction: 'neutral' })}>NTR</button>
          </div>
        </div>

        <div className="field">
          <div className="field-label">Type</div>
          <select className="select" value={spawn.type}
                  onChange={(e) => setSpawn({ ...spawn, type: e.target.value })}>
            <option value="infantry">Infantry — INF</option>
            <option value="tank">Tank — TNK</option>
            <option value="aircraft">Aircraft — AIR</option>
            <option value="artillery">Artillery — ART</option>
          </select>
        </div>

        <div className="field-row">
          <div className="field">
            <div className="field-label">X</div>
            <input className="input" type="number" step="10" value={Math.round(spawn.x)}
                   onChange={(e) => setSpawn({ ...spawn, x: parseFloat(e.target.value) || 0 })} />
          </div>
          <div className="field">
            <div className="field-label">Y</div>
            <input className="input" type="number" step="10" value={Math.round(spawn.y)}
                   onChange={(e) => setSpawn({ ...spawn, y: parseFloat(e.target.value) || 0 })} />
          </div>
        </div>

        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text-2)',
                      letterSpacing: '0.10em', marginBottom: 8, fontStyle: 'italic' }}>
          Click map to set position
        </div>

        <button className="primary-btn" onClick={onSpawn}>+ DEPLOY</button>
      </div>

      {/* MARKERS */}
      <div className="rail-section">
        <div className="section-head no-x" style={{ paddingLeft: 0 }}>
          <span className="dot" />
          <span>MARKERS</span>
          <span className="spacer" />
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-2)' }}>{markers.length}</span>
        </div>
        <div className="marker-add">
          <input className="input" placeholder="Label…" value={markerLabel}
                 onChange={(e) => setMarkerLabel(e.target.value)}
                 onKeyDown={(e) => {
                   if (e.key === 'Enter' && markerLabel.trim()) {
                     onAddMarker(markerLabel.trim());
                     setMarkerLabel('');
                   }
                 }} />
          <button className="t-btn" style={{ minWidth: 36 }}
                  onClick={() => {
                    if (markerLabel.trim()) {
                      onAddMarker(markerLabel.trim()); setMarkerLabel('');
                    }
                  }}>+</button>
        </div>
        <ul className="markers">
          {markers.map((m) => (
            <li key={m.id}>
              <span className="t">{fmtTime(m.time)}</span>
              <span>{m.label}</span>
              <span className="x" onClick={() => onRemoveMarker(m.id)}>×</span>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

// ============================================================
// RightRail — entities + inspector + engagements
// ============================================================
function MiniSpark({ data, color }) {
  if (!data || data.length < 2) {
    return <svg width="100%" height="22" />;
  }
  const W = 100, H = 22;
  const step = W / (data.length - 1);
  const pts = data.map((v, i) => `${(i * step).toFixed(1)},${(H - v * H).toFixed(1)}`).join(' ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: '100%', height: 22 }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.2" />
      <polyline points={`${pts} ${W},${H} 0,${H}`} fill={color + '20'} stroke="none" />
    </svg>
  );
}

function EntityListRow({ ent, selected, onSelect }) {
  const facCls = ent.faction === 'blue' ? '' : ent.faction === 'red' ? 'red' : 'amber';
  const pct = Math.max(0, Math.min(1, ent.hp / ent.max_hp));
  const hpColor = pct > 0.6 ? '#5fd07d' : pct > 0.3 ? '#f0a23a' : '#ff5b5b';
  return (
    <div className={'entity-row' + (selected ? ' selected' : '') + (ent.destroyed ? ' dead' : '')}
         onClick={onSelect}>
      <div className={'er-icon ' + facCls}>
        {ent.type === 'infantry'  && <UnitIcon type="infantry"  color={FAC_COLORS[ent.faction]} />}
        {ent.type === 'tank'      && <UnitIcon type="tank"      color={FAC_COLORS[ent.faction]} />}
        {ent.type === 'aircraft'  && <UnitIcon type="aircraft"  color={FAC_COLORS[ent.faction]} />}
        {ent.type === 'artillery' && <UnitIcon type="artillery" color={FAC_COLORS[ent.faction]} />}
      </div>
      <div className="er-label">{ent.id}</div>
      <div className="er-type">{ent.spec?.label || ent.type.substring(0, 3).toUpperCase()}</div>
      <div className="er-hp">
        <div className="fill" style={{ width: (pct * 100) + '%', background: hpColor }} />
      </div>
    </div>
  );
}

function UnitIcon({ type, color, size = 12 }) {
  const s = size;
  if (type === 'infantry') {
    return (
      <svg width={s} height={s} viewBox="0 0 12 12">
        <rect x="1" y="2.5" width="10" height="7" fill="none" stroke={color} strokeWidth="1.2" />
        <line x1="1" y1="2.5" x2="11" y2="9.5" stroke={color} strokeWidth="1" />
        <line x1="11" y1="2.5" x2="1" y2="9.5" stroke={color} strokeWidth="1" />
      </svg>
    );
  }
  if (type === 'tank') {
    return (
      <svg width={s} height={s} viewBox="0 0 12 12">
        <rect x="1" y="2.5" width="10" height="7" fill="none" stroke={color} strokeWidth="1.2" />
        <ellipse cx="6" cy="6" rx="4" ry="2.5" fill="none" stroke={color} strokeWidth="1" />
      </svg>
    );
  }
  if (type === 'aircraft') {
    return (
      <svg width={s} height={s} viewBox="0 0 12 12">
        <path d="M 1 6 L 11 2 L 7 6 L 11 10 Z" fill={color} stroke={color} strokeWidth="0.5" />
      </svg>
    );
  }
  if (type === 'artillery') {
    return (
      <svg width={s} height={s} viewBox="0 0 12 12">
        <rect x="1" y="2.5" width="10" height="7" fill="none" stroke={color} strokeWidth="1.2" />
        <circle cx="6" cy="6" r="2" fill={color} />
      </svg>
    );
  }
  return null;
}

function RightRail({ sim, status, selectedId, onSelect, threatLevel }) {
  const [filter, setFilter] = useState('all');
  const entities = useMemo(() => Array.from(sim.entities.values()), [sim, status.time, status.entities]);
  const filtered = entities.filter(e => filter === 'all' ? true : e.faction === filter);
  const selected = selectedId ? sim.entities.get(selectedId) : null;

  const blueN = entities.filter(e => e.faction === 'blue' && !e.destroyed).length;
  const redN  = entities.filter(e => e.faction === 'red' && !e.destroyed).length;

  return (
    <aside className="rail right" data-screen-label="03 Right rail">
      {/* Entities */}
      <div className="section-titlebar">
        <div className="crumb">
          <span className={filter === 'all'  ? 'active' : ''} onClick={() => setFilter('all')} style={{ cursor: 'pointer' }}>ALL</span>
          <span className="sep">/</span>
          <span className={filter === 'blue' ? 'active' : ''} onClick={() => setFilter('blue')} style={{ cursor: 'pointer' }}>BLUE·{blueN}</span>
          <span className="sep">/</span>
          <span className={filter === 'red'  ? 'active' : ''} onClick={() => setFilter('red')} style={{ cursor: 'pointer' }}>RED·{redN}</span>
        </div>
        <span className="count">{filtered.filter(e => !e.destroyed).length}</span>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {filtered.length === 0 && <div className="insp-empty">No units on field</div>}
        {filtered.map((e) => (
          <EntityListRow key={e.id} ent={e}
                         selected={e.id === selectedId}
                         onSelect={() => onSelect(e.id)} />
        ))}
      </div>

      {/* Inspector */}
      <div className="rail-section" style={{ padding: 0, flexShrink: 0 }}>
        <div className="section-head" style={{ padding: '10px 16px 8px' }}>
          <span className="dot" />
          <span>INSPECTOR</span>
          {selected && <span className="badge amber" style={{ marginLeft: 'auto' }}>
            {selected.spec?.label || selected.type.substring(0,3).toUpperCase()}
          </span>}
        </div>
        {!selected && <div className="insp-empty">SELECT A UNIT</div>}
        {selected && <Inspector ent={selected} status={status} threatLevel={threatLevel} />}
      </div>

      {/* Engagements */}
      <div className="rail-section" style={{ padding: 0, flexShrink: 0 }}>
        <div className="section-head" style={{ padding: '10px 16px 8px' }}>
          <span className="dot" style={{ background: 'var(--red)', boxShadow: '0 0 6px var(--red)' }} />
          <span>ENGAGEMENTS</span>
          <span className="badge red" style={{ marginLeft: 'auto' }}>{status.engagements} ACTIVE</span>
        </div>
        <div style={{ maxHeight: 130, overflowY: 'auto' }}>
          {status.engagements === 0 && <div className="eng-empty">— NO CONTACT —</div>}
          {sim.engagements.map((e, i) => {
            const a = sim.entities.get(e.a), b = sim.entities.get(e.b);
            if (!a || !b) return null;
            return (
              <div key={i} className="eng-row">
                <span className={a.faction === 'blue' ? 'eng-a' : 'eng-b'} style={{ color: FAC_COLORS[a.faction] }}>
                  {a.id}
                </span>
                <span className="eng-vs">⨯</span>
                <span style={{ color: FAC_COLORS[b.faction] }}>{b.id}</span>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}

function Inspector({ ent, status, threatLevel }) {
  const pct = Math.max(0, Math.min(1, ent.hp / ent.max_hp));
  const hpColor = pct > 0.6 ? '#5fd07d' : pct > 0.3 ? '#f0a23a' : '#ff5b5b';
  const facCls = ent.faction;
  const dist = ent.target ? Math.hypot(ent.target.x - ent.x, ent.target.y - ent.y) : null;

  return (
    <div className="insp">
      <div className="insp-id-row">
        <span className="insp-id">{ent.id}</span>
        <span className={'insp-fac ' + facCls}>{ent.faction}</span>
      </div>

      <div className="insp-hp-bar">
        <div className="insp-hp-fill" style={{ width: (pct * 100) + '%', background: hpColor, color: hpColor }} />
      </div>
      <div className="insp-hp-label">
        <span>INTEGRITY</span>
        <span><span className="v">{ent.hp.toFixed(0)}</span> / {ent.max_hp.toFixed(0)}</span>
      </div>

      <div className="insp-grid">
        <div className="insp-cell"><div className="k">TYPE</div><div className="v">{ent.spec?.label || ent.type}</div></div>
        <div className="insp-cell"><div className="k">SPEED</div><div className="v">{ent.speed.toFixed(1)}</div></div>
        <div className="insp-cell"><div className="k">FIREPWR</div><div className="v">{ent.firepower}</div></div>
        <div className="insp-cell"><div className="k">ARMOR</div><div className="v">{ent.armor}</div></div>
        <div className="insp-cell"><div className="k">RANGE</div><div className="v">{ent.range}</div></div>
        <div className="insp-cell"><div className="k">MORALE</div><div className="v">{ent.morale.toFixed(0)}</div></div>
        <div className="insp-cell"><div className="k">POS X</div><div className="v">{ent.x.toFixed(0)}</div></div>
        <div className="insp-cell"><div className="k">POS Y</div><div className="v">{ent.y.toFixed(0)}</div></div>
      </div>

      <div className="insp-cell" style={{ marginBottom: 6 }}>
        <div className="k">HP TRAJECTORY</div>
        <div className="hc-spark"><MiniSpark data={ent.hpHistory} color={hpColor} /></div>
      </div>

      {dist !== null && (
        <div className="insp-cell">
          <div className="k">TARGET · {ent.target.id}</div>
          <div className="v" style={{ fontSize: 11 }}>
            {dist.toFixed(0)}m · {dist <= ent.range ? <span style={{ color: 'var(--green)' }}>IN RANGE</span> : <span style={{ color: 'var(--text-2)' }}>CLOSING</span>}
          </div>
        </div>
      )}

      {threatLevel > 0 && (
        <div className="insp-threat">
          <span style={{ fontSize: 13 }}>⚠</span>
          UNIT UNDER FIRE · {threatLevel} HOSTILE{threatLevel > 1 ? 'S' : ''}
        </div>
      )}
    </div>
  );
}

// ============================================================
// Hover card (free-floating)
// ============================================================
function HoverCard({ ent, pos }) {
  if (!ent || !pos) return null;
  const pct = Math.max(0, Math.min(1, ent.hp / ent.max_hp));
  const hpColor = pct > 0.6 ? '#5fd07d' : pct > 0.3 ? '#f0a23a' : '#ff5b5b';
  return (
    <div className="hover-card" style={{ left: pos.x + 16, top: pos.y - 50 }}>
      <div className="hc-head">
        <span className="hc-id">{ent.id}</span>
        <span className="hc-type">{ent.spec?.label || ent.type}</span>
      </div>
      <div className="hc-row"><span>FACTION</span><span className="v" style={{ color: FAC_COLORS[ent.faction] }}>{ent.faction.toUpperCase()}</span></div>
      <div className="hc-row"><span>HP</span><span className="v" style={{ color: hpColor }}>{ent.hp.toFixed(0)}/{ent.max_hp}</span></div>
      <div className="hc-row"><span>SPD</span><span className="v">{ent.speed.toFixed(1)}</span></div>
      <div className="hc-row"><span>RNG</span><span className="v">{ent.range}</span></div>
      <div className="hc-spark"><MiniSpark data={ent.hpHistory} color={hpColor} /></div>
    </div>
  );
}

// ============================================================
// Event ticker (over map)
// ============================================================
function EventTicker({ events }) {
  const recent = events.slice(-5).reverse();
  return (
    <div className="event-ticker">
      {recent.map((e) => {
        const cls = e.type === 'entity.destroyed' ? 'red'
                  : e.type === 'engagement.fire' ? 'red'
                  : e.type === 'entity.created' ? 'blue'
                  : e.type === 'marker.added' ? 'amber'
                  : '';
        let label;
        if (e.type === 'engagement.fire') label = `${e.data.shooter} fires`;
        else if (e.type === 'entity.destroyed') label = `${e.data.id} destroyed`;
        else if (e.type === 'entity.created') label = `${e.data.id} deployed`;
        else if (e.type === 'entity.damaged') label = `${e.data.id} took ${e.data.dmg} dmg`;
        else if (e.type === 'marker.added') label = `marker · "${e.data.label}"`;
        else if (e.type === 'simulation.started') label = 'simulation started';
        else if (e.type === 'simulation.paused') label = 'simulation paused';
        else if (e.type === 'simulation.resumed') label = 'simulation resumed';
        else if (e.type === 'simulation.stopped') label = 'simulation stopped';
        else if (e.type === 'time.scaled') label = `time scale → ${e.data.scale.toFixed(1)}×`;
        else return null;
        return (
          <div key={e.id} className={'ticker-row ' + cls}>
            <span className="t">{fmtTime(e.time)}</span>
            <span className="label">{label}</span>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================
// Timeline
// ============================================================
function Timeline({ sim, status, markers }) {
  const ref = useRef(null);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ro = new ResizeObserver(() => draw());
    ro.observe(c.parentElement);
    draw();
    return () => ro.disconnect();
  }, [sim, status, markers]);

  useEffect(() => {
    let raf;
    const loop = () => { draw(); raf = requestAnimationFrame(loop); };
    loop();
    return () => cancelAnimationFrame(raf);
  }, []);

  function draw() {
    const c = ref.current;
    if (!c) return;
    const W = c.clientWidth, H = c.clientHeight;
    c.width = W; c.height = H;
    const ctx = c.getContext('2d');
    ctx.clearRect(0, 0, W, H);

    const WINDOW = 90; // seconds visible
    const t = status.time;
    const t0 = Math.max(0, t - WINDOW * 0.75);
    const t1 = t0 + WINDOW;
    const x = (tt) => ((tt - t0) / WINDOW) * W;

    // bg gradient
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, 'rgba(11,18,32,0.4)');
    g.addColorStop(1, 'rgba(4,7,13,0.7)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

    // tick marks (every 5s)
    ctx.strokeStyle = 'rgba(245,185,66,0.10)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    const startTick = Math.ceil(t0 / 5) * 5;
    for (let s = startTick; s <= t1; s += 5) {
      const xx = x(s);
      ctx.moveTo(xx, 0); ctx.lineTo(xx, H);
    }
    ctx.stroke();
    ctx.fillStyle = 'rgba(245,185,66,0.45)';
    ctx.font = '9px JetBrains Mono, monospace';
    for (let s = startTick; s <= t1; s += 10) {
      const xx = x(s);
      ctx.fillText(fmtTime(s), xx + 3, 11);
    }

    // events strip — quantize into bins and stack
    // Y zones: top zone (12-30) = spawn/destroy, mid (30-48) = fire density, bottom (48-66) = markers
    // 1. fire density histogram
    const bins = 80;
    const binW = W / bins;
    const fireCounts = new Array(bins).fill(0);
    const otherEvents = [];
    for (const e of sim.events) {
      if (e.time < t0 || e.time > t1) continue;
      const bi = Math.min(bins - 1, Math.floor((e.time - t0) / WINDOW * bins));
      if (e.type === 'engagement.fire') fireCounts[bi] += 1;
      else if (e.type === 'entity.destroyed' || e.type === 'entity.created' || e.type === 'marker.added') {
        otherEvents.push(e);
      }
    }
    const maxFire = Math.max(1, ...fireCounts);
    for (let i = 0; i < bins; i++) {
      if (!fireCounts[i]) continue;
      const xx = i * binW;
      const h = (fireCounts[i] / maxFire) * (H - 30);
      ctx.fillStyle = 'rgba(255,91,91,0.45)';
      ctx.fillRect(xx + 1, H - h - 6, binW - 1, h);
    }
    // event dots
    for (const e of otherEvents) {
      const xx = x(e.time);
      let yy = H - 10, color = '#888';
      if (e.type === 'entity.created') { color = '#4ea3ff'; yy = 16; }
      if (e.type === 'entity.destroyed') { color = '#f5b942'; yy = 22; }
      if (e.type === 'marker.added') { color = '#ece7d6'; yy = H - 10; }
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(xx, yy, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = color + '88';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(xx, yy); ctx.lineTo(xx, H - 6);
      ctx.stroke();
    }
    // markers labels at bottom
    for (const m of markers) {
      if (m.time < t0 || m.time > t1) continue;
      const xx = x(m.time);
      ctx.fillStyle = 'rgba(236,231,214,0.85)';
      ctx.font = '9px JetBrains Mono, monospace';
      ctx.fillText(m.label, xx + 4, H - 14);
    }

    // current time cursor
    const cx = x(t);
    ctx.strokeStyle = '#f5b942';
    ctx.lineWidth = 1.2;
    ctx.shadowColor = 'rgba(245,185,66,0.8)';
    ctx.shadowBlur = 6;
    ctx.beginPath();
    ctx.moveTo(cx, 0); ctx.lineTo(cx, H);
    ctx.stroke();
    ctx.shadowBlur = 0;
  }

  return (
    <section className="timeline" data-screen-label="04 Timeline">
      <div className="timeline-head">
        <span className="dot" />
        <span>EVENT TIMELINE</span>
        <span style={{ marginLeft: 8, color: 'var(--text-1)' }}>
          last 90s · {sim.events.length} events
        </span>
        <span className="spacer" />
        <span className="leg"><span className="sq spawn" /> SPAWN</span>
        <span className="leg"><span className="sq destroy" /> DESTROY</span>
        <span className="leg"><span className="sq eng" /> FIRE DENSITY</span>
        <span className="leg"><span className="sq marker" /> MARKER</span>
      </div>
      <div className="timeline-body">
        <canvas ref={ref} className="timeline-canvas" />
      </div>
    </section>
  );
}

// ============================================================
// Command palette
// ============================================================
function CommandPalette({ open, onClose, commands }) {
  const [q, setQ] = useState('');
  const [i, setI] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setQ(''); setI(0);
      setTimeout(() => inputRef.current && inputRef.current.focus(), 30);
    }
  }, [open]);

  const filtered = useMemo(() => {
    if (!q.trim()) return commands;
    const qq = q.toLowerCase();
    return commands
      .map((c) => ({ c, score: c.label.toLowerCase().includes(qq) ? 1 : (c.keywords || []).some(k => k.toLowerCase().includes(qq)) ? 0.5 : 0 }))
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .map((x) => x.c);
  }, [q, commands]);

  if (!open) return null;

  const run = (cmd) => { cmd && cmd.fn(); onClose(); };

  return (
    <div className="palette-backdrop" onClick={onClose}>
      <div className="palette" onClick={(e) => e.stopPropagation()}>
        <input ref={inputRef} className="palette-input"
               placeholder="Type a command or unit ID…"
               value={q}
               onChange={(e) => { setQ(e.target.value); setI(0); }}
               onKeyDown={(e) => {
                 if (e.key === 'Escape') onClose();
                 else if (e.key === 'ArrowDown') { setI((x) => Math.min(filtered.length - 1, x + 1)); e.preventDefault(); }
                 else if (e.key === 'ArrowUp') { setI((x) => Math.max(0, x - 1)); e.preventDefault(); }
                 else if (e.key === 'Enter') run(filtered[i]);
               }} />
        <div className="palette-list">
          {filtered.length === 0 && (
            <div className="palette-section">NO MATCHES</div>
          )}
          {filtered.map((c, idx) => (
            <div key={c.id} className={'palette-item' + (idx === i ? ' active' : '')}
                 onMouseEnter={() => setI(idx)} onClick={() => run(c)}>
              <span className="ico">{c.icon || '›'}</span>
              <span>{c.label}</span>
              {c.kbd && <span className="kbd">{c.kbd}</span>}
            </div>
          ))}
        </div>
        <div className="palette-foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> nav · <kbd>↵</kbd> run · <kbd>esc</kbd> close</span>
          <span>{filtered.length} commands</span>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// MapToolbar — floating top center of map
// ============================================================
function MapToolbar({ zoom, onZoomIn, onZoomOut, onFit,
                     fog, onFogToggle, heat, onHeatToggle, radar, onRadarToggle }) {
  return (
    <div className="map-toolbar">
      <button onClick={onZoomOut} title="Zoom out">−</button>
      <span className="zoom-label">{zoom}%</span>
      <button onClick={onZoomIn} title="Zoom in">+</button>
      <div className="sep" />
      <button onClick={onFit} title="Fit to forces" style={{ width: 42, fontSize: 9, letterSpacing: '.12em' }}>FIT</button>
      <div className="sep" />
      <button className={'toggle' + (fog   ? ' on' : '')} onClick={onFogToggle}   title="Fog of war">FOG</button>
      <button className={'toggle' + (heat  ? ' on' : '')} onClick={onHeatToggle}  title="Heat overlay">HEAT</button>
      <button className={'toggle' + (radar ? ' on' : '')} onClick={onRadarToggle} title="Radar sweep">RDR</button>
    </div>
  );
}

Object.assign(window, {
  TopBar, LeftRail, RightRail, HoverCard, EventTicker, Timeline, CommandPalette, MapToolbar,
  UnitIcon, MiniSpark, FAC_COLORS, fmtTime,
});
