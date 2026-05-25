// ============================================================
// Strategos — root app
// ============================================================
const { useEffect, useState, useRef, useMemo, useCallback } = React;

function StrategosApp() {
  const simRef = useRef(null);
  const audioRef = useRef(null);

  if (!simRef.current) {
    simRef.current = new Sim();
    window._sim = simRef.current;
  }
  if (!audioRef.current) audioRef.current = new AudioFX();

  const sim = simRef.current;
  const audio = audioRef.current;

  // Re-render at RAF rate so UI reflects sim state
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let raf;
    let last = 0;
    const update = (t) => {
      if (!last) last = t;
      // throttle to ~20fps to limit react renders
      if (t - last > 50) { last = t; setTick((x) => x + 1); }
      raf = requestAnimationFrame(update);
    };
    raf = requestAnimationFrame(update);
    // Also a setTimeout fallback for iframe throttling
    const id = setInterval(() => setTick((x) => x + 1), 300);
    return () => { cancelAnimationFrame(raf); clearInterval(id); };
  }, []);

  // Auto-start sim on mount + initial fit
  useEffect(() => {
    if (sim.state === 'stopped') sim.start();
    // Fit map to forces shortly after spawn so units are on-screen
    const t1 = setTimeout(() => { window.MapView && window.MapView.fit(); }, 200);
    return () => clearTimeout(t1);
  }, []);

  // Status
  const status = useMemo(() => sim.status(), [tick, sim]);

  // Selection
  const [selectedId, setSelectedId] = useState(null);
  // Auto-deselect when destroyed
  useEffect(() => {
    if (selectedId && !sim.entities.has(selectedId)) setSelectedId(null);
  }, [tick, selectedId]);

  // Threat level for selected
  const threatLevel = useMemo(() => {
    if (!selectedId) return 0;
    let n = 0;
    for (const e of sim.engagements) {
      if (e.a === selectedId || e.b === selectedId) n += 1;
    }
    return n;
  }, [tick, selectedId]);

  // Hover entity
  const [hover, setHover] = useState({ ent: null, pos: null });
  const handleHover = useCallback((ent, pos) => {
    setHover(ent ? { ent, pos } : { ent: null, pos: null });
  }, []);

  // Spawn state
  const [spawn, setSpawn] = useState({ faction: 'blue', type: 'infantry', x: 0, y: 0 });
  const [spawnPosOnMap, setSpawnPosOnMap] = useState(null);

  const handleMapClick = useCallback((wx, wy) => {
    setSpawn((s) => ({ ...s, x: wx, y: wy }));
    setSpawnPosOnMap({ x: wx, y: wy });
  }, []);

  const handleSpawn = useCallback(() => {
    sim.spawnUnit({ type: spawn.type, faction: spawn.faction, x: spawn.x, y: spawn.y });
    setSpawn((s) => ({ ...s, x: s.x + 25 })); // step
    audio.click();
  }, [spawn, sim, audio]);

  // Markers
  const handleAddMarker = useCallback((label) => {
    sim.addMarker(label); audio.blip();
  }, [sim, audio]);
  const handleRemoveMarker = useCallback((id) => sim.removeMarker(id), [sim]);

  // Map toolbar state
  const [fog, setFog] = useState(false);
  const [heat, setHeat] = useState(true);
  const [radar, setRadar] = useState(true);

  const [zoomPct, setZoomPct] = useState(105);
  useEffect(() => {
    const id = setInterval(() => {
      if (window.MapView && window.MapView.getZoomPercent) {
        setZoomPct(window.MapView.getZoomPercent());
      }
    }, 200);
    return () => clearInterval(id);
  }, []);

  // Audio
  const [audioOn, setAudioOn] = useState(false);
  const handleAudioToggle = useCallback(() => {
    setAudioOn(audio.toggle());
  }, [audio]);

  // Command palette
  const [palOpen, setPalOpen] = useState(false);

  // Hotkeys
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPalOpen((x) => !x);
      } else if (e.key === ' ' && !e.target.matches('input, textarea, select')) {
        e.preventDefault();
        if (sim.state === 'running') sim.pause();
        else if (sim.state === 'paused') sim.resume();
        else if (sim.state === 'stopped') sim.start();
        audio.click();
      } else if (e.key === 'f' && !e.target.matches('input, textarea, select')) {
        window.MapView.fit();
      } else if (e.key === 'Escape') {
        setPalOpen(false);
        setSelectedId(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [sim, audio]);

  // Commands
  const commands = useMemo(() => {
    const list = [
      { id: 'start', label: 'Start simulation', icon: '▶', fn: () => sim.start(), keywords: ['run', 'play', 'go'] },
      { id: 'pause', label: 'Pause simulation', icon: '⏸', fn: () => sim.pause(), kbd: 'space' },
      { id: 'resume', label: 'Resume simulation', icon: '⏵', fn: () => sim.resume() },
      { id: 'stop', label: 'Stop & reset', icon: '■', fn: () => sim.stop(), keywords: ['reset'] },
      { id: 'fit', label: 'Fit map to forces', icon: '⛶', fn: () => window.MapView.fit(), kbd: 'f' },
      { id: 'zoomin', label: 'Zoom in', icon: '+', fn: () => window.MapView.zoomIn() },
      { id: 'zoomout', label: 'Zoom out', icon: '−', fn: () => window.MapView.zoomOut() },
      { id: 'fog', label: (fog ? 'Disable' : 'Enable') + ' fog of war', icon: '◐', fn: () => setFog(x => !x), keywords: ['vision', 'fow'] },
      { id: 'heat', label: (heat ? 'Disable' : 'Enable') + ' heat overlay', icon: '⚹', fn: () => setHeat(x => !x), keywords: ['heatmap'] },
      { id: 'radar', label: (radar ? 'Disable' : 'Enable') + ' radar sweep', icon: '◌', fn: () => setRadar(x => !x) },
      { id: 'audio', label: (audioOn ? 'Mute audio' : 'Enable audio FX'), icon: '♪', fn: handleAudioToggle },
      { id: 'spawn-inf-b', label: 'Deploy infantry · blue', icon: '+', fn: () => sim.spawnUnit({ type: 'infantry', faction: 'blue', x: -260 + Math.random()*60, y: 60 + Math.random()*40 }) },
      { id: 'spawn-tk-b',  label: 'Deploy tank · blue',     icon: '+', fn: () => sim.spawnUnit({ type: 'tank',     faction: 'blue', x: -260 + Math.random()*60, y: 60 + Math.random()*40 }) },
      { id: 'spawn-air-b', label: 'Deploy aircraft · blue', icon: '+', fn: () => sim.spawnUnit({ type: 'aircraft', faction: 'blue', x: -260 + Math.random()*60, y: 60 + Math.random()*40 }) },
      { id: 'spawn-art-b', label: 'Deploy artillery · blue',icon: '+', fn: () => sim.spawnUnit({ type: 'artillery',faction: 'blue', x: -260 + Math.random()*60, y: 60 + Math.random()*40 }) },
      { id: 'spawn-inf-r', label: 'Deploy infantry · red',  icon: '+', fn: () => sim.spawnUnit({ type: 'infantry', faction: 'red',  x: 260 - Math.random()*60, y: -40 + Math.random()*40 }) },
      { id: 'spawn-tk-r',  label: 'Deploy tank · red',      icon: '+', fn: () => sim.spawnUnit({ type: 'tank',     faction: 'red',  x: 260 - Math.random()*60, y: -40 + Math.random()*40 }) },
      { id: 'marker', label: 'Mark current time', icon: '⚑', fn: () => sim.addMarker('manual') },
      { id: 'shake', label: 'Trigger screen shake', icon: '≋', fn: () => window.MapView.shake(10) },
    ];
    // unit jump commands
    for (const ent of sim.entities.values()) {
      if (ent.destroyed) continue;
      list.push({
        id: 'jump-' + ent.id,
        label: 'Focus ' + ent.id + ' · ' + ent.spec?.label,
        icon: '◎',
        keywords: [ent.id, ent.type, ent.faction],
        fn: () => {
          setSelectedId(ent.id);
          window.MapView.centerOn(ent.x, ent.y);
        },
      });
    }
    return list;
  }, [sim, fog, heat, radar, audioOn, tick]);

  return (
    <div className="root-grid">
      <TopBar
        status={status}
        audioOn={audioOn}
        onAudioToggle={handleAudioToggle}
        onPalette={() => setPalOpen(true)}
      />

      <LeftRail
        sim={sim}
        status={status}
        spawn={spawn}
        setSpawn={setSpawn}
        onSpawn={handleSpawn}
        markers={sim.markers}
        onAddMarker={handleAddMarker}
        onRemoveMarker={handleRemoveMarker}
        audio={audio}
      />

      <main className="map-wrap" data-screen-label="05 Map">
        <MapView
          sim={sim}
          simTickSignal={tick}
          selectedId={selectedId}
          onSelectEntity={setSelectedId}
          onHoverEntity={handleHover}
          spawnPos={spawnPosOnMap}
          onMapClick={handleMapClick}
          fogOfWar={fog}
          showHeat={heat}
          showRadar={radar}
          audio={audio}
        />

        <MapToolbar
          zoom={zoomPct}
          onZoomIn={() => window.MapView.zoomIn()}
          onZoomOut={() => window.MapView.zoomOut()}
          onFit={() => window.MapView.fit()}
          fog={fog} onFogToggle={() => setFog((x) => !x)}
          heat={heat} onHeatToggle={() => setHeat((x) => !x)}
          radar={radar} onRadarToggle={() => setRadar((x) => !x)}
        />

        {/* corner overlays */}
        <div className="map-overlay map-corner-tl">
          <div className="corner-tag">
            <span className="k">SECTOR</span><span className="v">07-NIGHTHAWK</span>
          </div>
        </div>
        <div className="map-overlay map-corner-tr">
          <div className="corner-tag">
            <span className="k">GRID</span><span className="v">UTM 33T · DECIMETER</span>
          </div>
        </div>
        <div className="map-overlay map-corner-bl" style={{ pointerEvents: 'none' }}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text-2)',
                        letterSpacing: '0.12em' }}>
            CRS · WGS-84 · DTM 30M
          </div>
        </div>

        <EventTicker events={sim.events} />
        <HoverCard ent={hover.ent} pos={hover.pos} />
      </main>

      <RightRail
        sim={sim}
        status={status}
        selectedId={selectedId}
        onSelect={(id) => { setSelectedId(id); if (id) { const e = sim.entities.get(id); if (e) window.MapView.centerOn(e.x, e.y); } audio.click(); }}
        threatLevel={threatLevel}
      />

      <Timeline sim={sim} status={status} markers={sim.markers} />

      <CommandPalette open={palOpen} onClose={() => setPalOpen(false)} commands={commands} />
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<StrategosApp />);
