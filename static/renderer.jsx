// ============================================================
// Strategos — Canvas Map Renderer
// ============================================================
const { useEffect, useRef, useState, useCallback, useMemo } = React;

// Generate procedural satellite-style terrain (cached, drawn once)
function buildTerrainCanvas(seed = 1337) {
  const W = 1024, H = 768;
  // World region this represents
  const worldW = 2400, worldH = 1800;
  const c = document.createElement('canvas');
  c.width = W; c.height = H;
  const ctx = c.getContext('2d');

  // -- value-noise field (octaved) --
  const grid = 24;          // coarse cells
  const grandom = (x, y) => {
    let h = (x * 374761393 + y * 668265263 + seed * 2147483647) | 0;
    h = (h ^ (h >>> 13)) * 1274126177;
    h = h ^ (h >>> 16);
    return ((h & 0x7fffffff) / 0x7fffffff);
  };
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (t) => t * t * (3 - 2 * t);
  const valNoise = (x, y) => {
    const x0 = Math.floor(x), y0 = Math.floor(y);
    const fx = smooth(x - x0), fy = smooth(y - y0);
    const a = grandom(x0,     y0);
    const b = grandom(x0 + 1, y0);
    const cN= grandom(x0,     y0 + 1);
    const d = grandom(x0 + 1, y0 + 1);
    return lerp(lerp(a, b, fx), lerp(cN, d, fx), fy);
  };
  const fbm = (x, y) => {
    let v = 0, amp = 0.55, freq = 1;
    for (let i = 0; i < 5; i++) {
      v += valNoise(x * freq, y * freq) * amp;
      freq *= 2.05;
      amp *= 0.5;
    }
    return v;
  };

  const img = ctx.createImageData(W, H);
  const px = img.data;

  // Color stops by elevation
  const stops = [
    { e: 0.00, c: [16, 26, 42] },     // deep water
    { e: 0.30, c: [26, 42, 60] },     // shallow water
    { e: 0.42, c: [62, 56, 38] },     // beach
    { e: 0.50, c: [52, 60, 36] },     // marsh
    { e: 0.62, c: [60, 70, 40] },     // grass
    { e: 0.75, c: [74, 76, 50] },     // dry grass
    { e: 0.86, c: [96, 84, 60] },     // highland tan
    { e: 1.00, c: [124, 108, 80] },   // ridge
  ];
  function sample(e) {
    for (let i = 1; i < stops.length; i++) {
      if (e <= stops[i].e) {
        const a = stops[i - 1], b = stops[i];
        const t = (e - a.e) / Math.max(0.0001, (b.e - a.e));
        return [
          Math.round(a.c[0] + (b.c[0] - a.c[0]) * t),
          Math.round(a.c[1] + (b.c[1] - a.c[1]) * t),
          Math.round(a.c[2] + (b.c[2] - a.c[2]) * t),
        ];
      }
    }
    return stops[stops.length - 1].c;
  }

  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const nx = x / W * grid, ny = y / H * grid * 0.75;
      let e = fbm(nx, ny);
      // bias toward terrain (less ocean)
      e = Math.pow(e, 0.78);
      // soft contour darkening near level steps
      const contour = (Math.abs((e * 24) % 1 - 0.5) < 0.06) ? 0.86 : 1.0;
      // grain
      const grain = 1 + (grandom(x, y) - 0.5) * 0.06;

      const c0 = sample(e);
      const r = Math.max(0, Math.min(255, c0[0] * contour * grain));
      const g = Math.max(0, Math.min(255, c0[1] * contour * grain));
      const b = Math.max(0, Math.min(255, c0[2] * contour * grain));

      const i = (y * W + x) * 4;
      px[i]     = r;
      px[i + 1] = g;
      px[i + 2] = b;
      px[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);

  // vignette
  const grad = ctx.createRadialGradient(W/2, H/2, W*0.3, W/2, H/2, W*0.65);
  grad.addColorStop(0, 'rgba(0,0,0,0)');
  grad.addColorStop(1, 'rgba(0,0,0,0.45)');
  ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H);

  // big subtle features: a couple of roads/rivers
  ctx.strokeStyle = 'rgba(200,170,120,0.35)';
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(0, H * 0.46);
  for (let x = 0; x <= W; x += 24) {
    const y = H * 0.46 + Math.sin(x * 0.015) * 30 + Math.cos(x * 0.04) * 14;
    ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.beginPath();
  ctx.strokeStyle = 'rgba(70,110,150,0.55)';
  ctx.lineWidth = 2.5;
  ctx.moveTo(W * 0.62, 0);
  for (let y = 0; y <= H; y += 20) {
    const x = W * 0.62 + Math.sin(y * 0.018) * 90;
    ctx.lineTo(x, y);
  }
  ctx.stroke();

  return { canvas: c, worldW, worldH };
}

// ============================================================
// MapView — React wrapper around imperative canvas
// ============================================================
function MapView({
  sim, simTickSignal, selectedId, onSelectEntity, onHoverEntity,
  spawnPos, onMapClick, fogOfWar, showHeat, showRadar, audio,
}) {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);
  const terrainRef = useRef(null);
  const stateRef = useRef({
    zoom: 1.05,
    viewX: 0, viewY: 0,
    shakeX: 0, shakeY: 0,
    radarAngle: 0,
    hoverEntityId: null,
    lastFireTimes: {},
    lastTickAt: performance.now(),
  });

  // Build terrain once
  useEffect(() => {
    terrainRef.current = buildTerrainCanvas();
  }, []);

  // Resize
  useEffect(() => {
    const c = canvasRef.current;
    const w = wrapRef.current;
    const ro = new ResizeObserver(() => {
      c.width = w.clientWidth;
      c.height = w.clientHeight;
    });
    ro.observe(w);
    c.width = w.clientWidth; c.height = w.clientHeight;
    return () => ro.disconnect();
  }, []);

  // Coordinate transforms
  const w2s = (wx, wy) => {
    const c = canvasRef.current;
    const s = stateRef.current;
    const cx = c.width / 2 + s.shakeX, cy = c.height / 2 + s.shakeY;
    return [
      (wx - s.viewX) * s.zoom + cx,
      -(wy - s.viewY) * s.zoom + cy,
    ];
  };
  const s2w = (sx, sy) => {
    const c = canvasRef.current;
    const s = stateRef.current;
    const cx = c.width / 2, cy = c.height / 2;
    return [
      (sx - cx) / s.zoom + s.viewX,
      -((sy - cy) / s.zoom) + s.viewY,
    ];
  };

  // Audio hooks: detect new fires/destroys
  useEffect(() => {
    if (!sim || !audio) return;
    const unsub = sim.subscribe((type) => {
      if (type === 'tick') {
        // fire detection — last event(s)
        const recent = sim.events.slice(-6);
        for (const e of recent) {
          if (e._heard) continue;
          e._heard = true;
          if (e.type === 'engagement.fire') {
            audio.fire(e.data.type);
          } else if (e.type === 'entity.destroyed') {
            audio.boom();
            // screen shake near selected
            stateRef.current.shakeX = (Math.random() - 0.5) * 8;
            stateRef.current.shakeY = (Math.random() - 0.5) * 8;
          } else if (e.type === 'entity.damaged') {
            audio.hit();
          }
        }
      }
    });
    return unsub;
  }, [sim, audio]);

  // RAF render loop — also drives sim ticks for reliability.
  // setTimeout fallback ensures canvas still repaints when iframe is throttled.
  useEffect(() => {
    if (!sim) return;
    let raf;
    let timer;
    let alive = true;
    const tickAndDraw = () => {
      if (!alive) return;
      if (sim.state === 'running') sim._loop();
      drawFrame();
    };
    const rafLoop = () => {
      if (!alive) return;
      tickAndDraw();
      raf = requestAnimationFrame(rafLoop);
    };
    const timerLoop = () => {
      if (!alive) return;
      tickAndDraw();
      timer = setTimeout(timerLoop, 80);
    };
    rafLoop();
    timer = setTimeout(timerLoop, 80);
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      clearTimeout(timer);
    };
  }, [sim, selectedId, fogOfWar, showHeat, showRadar]);

  function drawFrame() {
    const canvas = canvasRef.current;
    if (!canvas || !sim) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const s = stateRef.current;
    // decay shake
    s.shakeX *= 0.82;
    s.shakeY *= 0.82;
    // radar angle progress (independent of sim pause)
    const now = performance.now();
    const dt = Math.min(0.1, (now - s.lastTickAt) / 1000);
    s.lastTickAt = now;
    s.radarAngle = (s.radarAngle + dt * 0.6) % (Math.PI * 2);

    // -- background --
    ctx.save();
    ctx.fillStyle = '#04070d';
    ctx.fillRect(0, 0, W, H);

    drawTerrain(ctx, W, H);
    drawGrid(ctx, W, H);
    if (showHeat) drawHeat(ctx);
    if (showRadar) drawRadar(ctx, W, H);
    drawEngagements(ctx);
    drawEntities(ctx);
    drawProjectiles(ctx);
    drawExplosions(ctx);
    if (fogOfWar) drawFog(ctx, W, H);
    drawSpawnGhost(ctx);
    drawScalebar(ctx, W, H);
    drawCompass(ctx, W, H);
    ctx.restore();
  }

  function drawTerrain(ctx, W, H) {
    const terrain = terrainRef.current;
    if (!terrain) return;
    const s = stateRef.current;
    // worldRect → src rect on terrain canvas
    const [wx0, wy1] = s2w(0, 0);
    const [wx1, wy0] = s2w(W, H);
    const tW = terrain.canvas.width, tH = terrain.canvas.height;
    const wW = terrain.worldW, wH = terrain.worldH;
    // map world coord to terrain px (terrain covers [-wW/2..wW/2] × [-wH/2..wH/2])
    const wx2px = (wx) => (wx + wW / 2) / wW * tW;
    const wy2py = (wy) => (1 - (wy + wH / 2) / wH) * tH;
    const sx0 = wx2px(wx0), sx1 = wx2px(wx1);
    const sy0 = wy2py(wy0), sy1 = wy2py(wy1);
    ctx.save();
    ctx.globalAlpha = 0.92;
    // out-of-bounds: fill behind first
    ctx.fillStyle = '#0a1018';
    ctx.fillRect(0, 0, W, H);
    try {
      ctx.drawImage(
        terrain.canvas,
        sx0, sy0, (sx1 - sx0), (sy1 - sy0),
        0, 0, W, H
      );
    } catch (e) {}
    ctx.restore();

    // subtle scanline-style tint
    ctx.fillStyle = 'rgba(0,4,12,0.20)';
    ctx.fillRect(0, 0, W, H);
  }

  function drawGrid(ctx, W, H) {
    const s = stateRef.current;
    const baseStep = 100;
    let step = baseStep;
    while (step * s.zoom < 60)  step *= 2;
    while (step * s.zoom > 220) step /= 2;
    if (step < 10) step = 10;

    const [wx0, wy0] = s2w(0, H);
    const [wx1, wy1] = s2w(W, 0);

    ctx.save();
    ctx.lineWidth = 1;

    // minor grid
    ctx.strokeStyle = 'rgba(245,185,66,0.05)';
    ctx.beginPath();
    for (let wx = Math.floor(wx0 / step) * step; wx <= wx1 + step; wx += step) {
      const [sx] = w2s(wx, 0);
      ctx.moveTo(sx, 0); ctx.lineTo(sx, H);
    }
    for (let wy = Math.floor(wy0 / step) * step; wy <= wy1 + step; wy += step) {
      const [, sy] = w2s(0, wy);
      ctx.moveTo(0, sy); ctx.lineTo(W, sy);
    }
    ctx.stroke();

    // major grid every 5*step
    const major = step * 5;
    ctx.strokeStyle = 'rgba(245,185,66,0.14)';
    ctx.beginPath();
    for (let wx = Math.floor(wx0 / major) * major; wx <= wx1 + major; wx += major) {
      const [sx] = w2s(wx, 0);
      ctx.moveTo(sx, 0); ctx.lineTo(sx, H);
    }
    for (let wy = Math.floor(wy0 / major) * major; wy <= wy1 + major; wy += major) {
      const [, sy] = w2s(0, wy);
      ctx.moveTo(0, sy); ctx.lineTo(W, sy);
    }
    ctx.stroke();

    // origin axes
    const [ox, oy] = w2s(0, 0);
    ctx.strokeStyle = 'rgba(245,185,66,0.28)';
    ctx.beginPath();
    ctx.moveTo(ox, 0); ctx.lineTo(ox, H);
    ctx.moveTo(0, oy); ctx.lineTo(W, oy);
    ctx.stroke();

    // labels along major
    ctx.fillStyle = 'rgba(245,185,66,0.55)';
    ctx.font = '9.5px JetBrains Mono, monospace';
    for (let wx = Math.floor(wx0 / major) * major; wx <= wx1 + major; wx += major) {
      const [sx] = w2s(wx, 0);
      if (Math.abs(wx) < 0.5) continue;
      const tag = (wx >= 0 ? 'E' : 'W') + Math.abs(wx).toFixed(0);
      ctx.fillText(tag, sx + 3, 12);
    }
    for (let wy = Math.floor(wy0 / major) * major; wy <= wy1 + major; wy += major) {
      const [, sy] = w2s(0, wy);
      if (Math.abs(wy) < 0.5) continue;
      const tag = (wy >= 0 ? 'N' : 'S') + Math.abs(wy).toFixed(0);
      ctx.fillText(tag, 4, sy - 3);
    }
    ctx.restore();
  }

  function drawHeat(ctx) {
    // soft red blobs at recent engagement positions
    ctx.save();
    ctx.globalCompositeOperation = 'screen';
    for (const eng of sim.engagements) {
      const a = sim.entities.get(eng.a), b = sim.entities.get(eng.b);
      if (!a || !b) continue;
      for (const u of [a, b]) {
        const [sx, sy] = w2s(u.x, u.y);
        const r = 40 + 24 * Math.sin(performance.now() / 220);
        const g = ctx.createRadialGradient(sx, sy, 0, sx, sy, r);
        g.addColorStop(0, 'rgba(255,80,80,0.30)');
        g.addColorStop(1, 'rgba(255,80,80,0)');
        ctx.fillStyle = g;
        ctx.fillRect(sx - r, sy - r, r * 2, r * 2);
      }
    }
    ctx.restore();
  }

  function drawRadar(ctx, W, H) {
    const s = stateRef.current;
    const [cx, cy] = w2s(0, 0);
    const r = Math.max(W, H) * 1.1;
    ctx.save();
    // sweep cone
    const a = s.radarAngle;
    const span = Math.PI / 9;
    const grad = ctx.createConicGradient
      ? ctx.createConicGradient(a, cx, cy)
      : null;
    if (grad) {
      grad.addColorStop(0, 'rgba(245,185,66,0.22)');
      grad.addColorStop(0.025, 'rgba(245,185,66,0.0)');
      grad.addColorStop(1, 'rgba(245,185,66,0)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
    } else {
      // fallback wedge
      ctx.fillStyle = 'rgba(245,185,66,0.10)';
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, a - span, a);
      ctx.closePath();
      ctx.fill();
    }
    // sweep beam
    ctx.strokeStyle = 'rgba(245,185,66,0.7)';
    ctx.lineWidth = 1;
    ctx.shadowColor = 'rgba(245,185,66,0.9)';
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
    ctx.stroke();
    ctx.shadowBlur = 0;

    // concentric range rings
    ctx.strokeStyle = 'rgba(245,185,66,0.10)';
    ctx.lineWidth = 1;
    for (const rr of [100, 200, 400, 800]) {
      ctx.beginPath();
      ctx.arc(cx, cy, rr * s.zoom, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawEngagements(ctx) {
    ctx.save();
    for (const eng of sim.engagements) {
      const a = sim.entities.get(eng.a), b = sim.entities.get(eng.b);
      if (!a || !b) continue;
      const [ax, ay] = w2s(a.x, a.y);
      const [bx, by] = w2s(b.x, b.y);
      ctx.strokeStyle = 'rgba(255,91,91,0.30)';
      ctx.setLineDash([5, 4]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(bx, by);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.restore();
  }

  function drawEntityShape(ctx, ent, sx, sy, r, isSel) {
    const color = ent.faction === 'blue' ? '#7fb8ff'
                : ent.faction === 'red'  ? '#ff7676'
                : '#c8c8c8';
    const colorDark = ent.faction === 'blue' ? '#1f6bd9'
                    : ent.faction === 'red'  ? '#c2273a'
                    : '#888';
    const heading = ent.heading;
    ctx.save();
    // selection glow ring
    if (isSel) {
      ctx.beginPath();
      ctx.arc(sx, sy, r + 8 + Math.sin(performance.now() / 200) * 1.6, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(245,185,66,0.95)';
      ctx.lineWidth = 1.4;
      ctx.shadowColor = 'rgba(245,185,66,0.7)';
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.shadowBlur = 0;
      // crosshair ticks
      ctx.strokeStyle = 'rgba(245,185,66,0.7)';
      ctx.lineWidth = 1;
      for (let i = 0; i < 4; i++) {
        const a = (i / 4) * Math.PI * 2;
        const inner = r + 8, outer = r + 13;
        ctx.beginPath();
        ctx.moveTo(sx + Math.cos(a) * inner, sy + Math.sin(a) * inner);
        ctx.lineTo(sx + Math.cos(a) * outer, sy + Math.sin(a) * outer);
        ctx.stroke();
      }
    }

    // NATO-style box behind ground units
    if (ent.type !== 'aircraft') {
      const w = r * 2.4, h = r * 1.7;
      ctx.fillStyle = colorDark + 'cc';
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.rect(sx - w / 2, sy - h / 2, w, h);
      ctx.fill(); ctx.stroke();

      // type glyph inside box
      ctx.fillStyle = color;
      if (ent.type === 'infantry') {
        // crossed X
        ctx.lineWidth = 1.2;
        ctx.strokeStyle = color;
        ctx.beginPath();
        ctx.moveTo(sx - w/2 + 2, sy - h/2 + 2); ctx.lineTo(sx + w/2 - 2, sy + h/2 - 2);
        ctx.moveTo(sx + w/2 - 2, sy - h/2 + 2); ctx.lineTo(sx - w/2 + 2, sy + h/2 - 2);
        ctx.stroke();
      } else if (ent.type === 'tank') {
        // oval tread
        ctx.beginPath();
        ctx.ellipse(sx, sy, w/2 - 2.5, h/2 - 2.5, 0, 0, Math.PI*2);
        ctx.stroke();
      } else if (ent.type === 'artillery') {
        // big dot
        ctx.beginPath();
        ctx.arc(sx, sy, r * 0.5, 0, Math.PI*2);
        ctx.fill();
      }
    } else {
      // aircraft chevron, rotates with heading
      ctx.translate(sx, sy);
      ctx.rotate(-heading);
      ctx.beginPath();
      ctx.moveTo( r * 1.9, 0);
      ctx.lineTo(-r * 0.6, -r * 1.3);
      ctx.lineTo(-r * 0.1, 0);
      ctx.lineTo(-r * 0.6,  r * 1.3);
      ctx.closePath();
      ctx.fillStyle = colorDark + 'dd';
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      ctx.fill(); ctx.stroke();
      ctx.rotate(heading);
      ctx.translate(-sx, -sy);
    }

    // heading line for ground units in motion
    if (ent.type !== 'aircraft' && ent.speed > 0.5) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.1;
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(sx + Math.cos(heading) * 12, sy - Math.sin(heading) * 12);
      ctx.stroke();
    }

    ctx.restore();
  }

  function drawEntities(ctx) {
    const s = stateRef.current;
    const now = sim.time;

    for (const ent of sim.entities.values()) {
      const [sx, sy] = w2s(ent.x, ent.y);
      const isSel = ent.id === selectedId;
      const r = isSel ? 8 : 6;

      // destroyed → fade
      let alpha = 1;
      if (ent.destroyed) {
        const age = now - ent._destroyedAt;
        alpha = Math.max(0, 1 - age / 1.4);
      }
      ctx.save();
      ctx.globalAlpha = alpha;

      drawEntityShape(ctx, ent, sx, sy, r, isSel);

      // damage flash
      const sinceHit = now - ent.lastHit;
      if (sinceHit < 0.45 && !ent.destroyed) {
        const p = sinceHit / 0.45;
        ctx.beginPath();
        ctx.arc(sx, sy, r + 4 + p * 10, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(255,91,91,${(1 - p) * 0.9})`;
        ctx.lineWidth = 1.6;
        ctx.stroke();
      }

      // hp bar
      if (!ent.destroyed) {
        const barW = 18, barH = 3;
        const pct = Math.max(0, Math.min(1, ent.hp / ent.max_hp));
        ctx.fillStyle = 'rgba(0,0,0,0.6)';
        ctx.fillRect(sx - barW/2, sy + r + 5, barW, barH);
        ctx.fillStyle = pct > 0.6 ? '#5fd07d' : pct > 0.3 ? '#f0a23a' : '#ff5b5b';
        ctx.fillRect(sx - barW/2, sy + r + 5, barW * pct, barH);
      }

      // label
      if (s.zoom > 0.55 && !ent.destroyed) {
        ctx.fillStyle = ent.faction === 'blue' ? 'rgba(180,210,255,0.78)' :
                        ent.faction === 'red'  ? 'rgba(255,180,180,0.78)' :
                        'rgba(220,220,220,0.6)';
        ctx.font = '9px JetBrains Mono, monospace';
        const label = ent.id.length > 12 ? ent.id.slice(0, 8) : ent.id;
        ctx.fillText(label, sx + r + 5, sy + 3);
      }

      ctx.restore();
    }
  }

  function drawProjectiles(ctx) {
    ctx.save();
    for (const p of sim.projectiles) {
      const u = Math.max(0, Math.min(1, (sim.time - p.birth) / p.ttl));
      let px = p.x, py = p.y;
      if (p.arc) {
        // parabolic visual arc: lift Y at midpoint
        const lift = 30 * Math.sin(u * Math.PI);
        py += lift;
      }
      const [sx, sy] = w2s(px, py);
      // trail
      const trailLen = p.type === 'aircraft' ? 26 : p.type === 'tank' ? 16 : 10;
      const back = u - 0.06;
      const bx = p.sx + (p.tx - p.sx) * Math.max(0, back);
      const by = p.sy + (p.ty - p.sy) * Math.max(0, back);
      const [tsx, tsy] = w2s(bx, by);
      const color = p.faction === 'blue' ? '#9cc8ff' : p.faction === 'red' ? '#ffb1b1' : '#fff';
      const dim   = p.faction === 'blue' ? 'rgba(78,163,255,0)' : 'rgba(255,91,91,0)';
      const grd = ctx.createLinearGradient(tsx, tsy, sx, sy);
      grd.addColorStop(0, dim);
      grd.addColorStop(1, color);
      ctx.strokeStyle = grd;
      ctx.lineWidth = p.arc ? 1.8 : 1.4;
      ctx.beginPath();
      ctx.moveTo(tsx, tsy);
      ctx.lineTo(sx, sy);
      ctx.stroke();
      // head
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(sx, sy, p.arc ? 2.4 : 1.6, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawExplosions(ctx) {
    ctx.save();
    ctx.globalCompositeOperation = 'screen';
    for (const e of sim.explosions) {
      const u = (sim.time - e.birth) / e.ttl;
      const r = (e.big ? 30 : 16) * (0.4 + u * 1.4);
      const [sx, sy] = w2s(e.x, e.y);
      const a = (1 - u);
      const g = ctx.createRadialGradient(sx, sy, 0, sx, sy, r);
      g.addColorStop(0, `rgba(255,220,140,${0.9 * a})`);
      g.addColorStop(0.4, `rgba(255,120,40,${0.55 * a})`);
      g.addColorStop(1, 'rgba(255,80,0,0)');
      ctx.fillStyle = g;
      ctx.fillRect(sx - r, sy - r, r * 2, r * 2);

      // shockwave ring
      ctx.strokeStyle = `rgba(255,200,120,${0.6 * (1 - u)})`;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.arc(sx, sy, r * 0.85, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawFog(ctx, W, H) {
    // darken everything; then "cut" vision discs around friendlies
    const c = canvasRef.current;
    // build a mask: dark layer with destination-out where vision exists
    const fog = document.createElement('canvas');
    fog.width = W; fog.height = H;
    const fc = fog.getContext('2d');
    fc.fillStyle = 'rgba(2,5,10,0.55)';
    fc.fillRect(0, 0, W, H);
    fc.globalCompositeOperation = 'destination-out';
    for (const ent of sim.entities.values()) {
      if (ent.faction !== 'blue' || ent.destroyed) continue;
      const [sx, sy] = w2s(ent.x, ent.y);
      const vis = (ent.type === 'aircraft' ? 220 : ent.type === 'artillery' ? 200 : 150) * stateRef.current.zoom;
      const g = fc.createRadialGradient(sx, sy, vis * 0.2, sx, sy, vis);
      g.addColorStop(0, 'rgba(0,0,0,1)');
      g.addColorStop(0.7, 'rgba(0,0,0,0.85)');
      g.addColorStop(1, 'rgba(0,0,0,0)');
      fc.fillStyle = g;
      fc.beginPath();
      fc.arc(sx, sy, vis, 0, Math.PI * 2);
      fc.fill();
    }
    ctx.drawImage(fog, 0, 0);
  }

  function drawSpawnGhost(ctx) {
    if (!spawnPos) return;
    const [sx, sy] = w2s(spawnPos.x, spawnPos.y);
    ctx.save();
    ctx.strokeStyle = 'rgba(245,185,66,0.7)';
    ctx.setLineDash([3, 3]);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(sx, sy, 14, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.strokeStyle = 'rgba(245,185,66,0.95)';
    ctx.beginPath();
    ctx.moveTo(sx - 6, sy); ctx.lineTo(sx + 6, sy);
    ctx.moveTo(sx, sy - 6); ctx.lineTo(sx, sy + 6);
    ctx.stroke();
    ctx.fillStyle = 'rgba(245,185,66,0.9)';
    ctx.font = '9px JetBrains Mono, monospace';
    ctx.fillText(`(${spawnPos.x.toFixed(0)}, ${spawnPos.y.toFixed(0)})`, sx + 10, sy - 8);
    ctx.restore();
  }

  function drawScalebar(ctx, W, H) {
    const s = stateRef.current;
    // pick a scale length aiming for ~120 px
    const targetPx = 120;
    const targetWorld = targetPx / s.zoom;
    const mag = Math.pow(10, Math.floor(Math.log10(targetWorld)));
    const n = targetWorld / mag;
    const nice = n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10;
    const worldLen = nice * mag;
    const pxLen = worldLen * s.zoom;
    const x0 = W - pxLen - 24, y0 = H - 42;
    ctx.save();
    ctx.strokeStyle = 'rgba(245,185,66,0.7)';
    ctx.fillStyle = 'rgba(245,185,66,0.9)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x0, y0 - 4); ctx.lineTo(x0, y0 + 4);
    ctx.moveTo(x0 + pxLen, y0 - 4); ctx.lineTo(x0 + pxLen, y0 + 4);
    ctx.moveTo(x0, y0); ctx.lineTo(x0 + pxLen, y0);
    ctx.stroke();
    ctx.font = '10px JetBrains Mono, monospace';
    ctx.fillText(`${worldLen} m`, x0 + pxLen + 6, y0 + 3);
    ctx.restore();
  }

  function drawCompass(ctx, W, H) {
    const cx = 36, cy = H - 42, r = 18;
    ctx.save();
    ctx.strokeStyle = 'rgba(245,185,66,0.65)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(cx, cy, r - 4, 0, Math.PI * 2); ctx.stroke();
    // tick marks
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * (r - 3), cy + Math.sin(a) * (r - 3));
      ctx.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
      ctx.stroke();
    }
    // N needle
    ctx.fillStyle = '#f5b942';
    ctx.beginPath();
    ctx.moveTo(cx, cy - r + 1);
    ctx.lineTo(cx - 3, cy);
    ctx.lineTo(cx + 3, cy);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = '#888';
    ctx.beginPath();
    ctx.moveTo(cx, cy + r - 1);
    ctx.lineTo(cx - 3, cy);
    ctx.lineTo(cx + 3, cy);
    ctx.closePath();
    ctx.fill();
    ctx.font = '8px JetBrains Mono, monospace';
    ctx.fillStyle = '#f5b942';
    ctx.fillText('N', cx - 3, cy - r - 3);
    ctx.restore();
  }

  // -------- Pan/zoom/click handlers --------
  useEffect(() => {
    const c = canvasRef.current;
    let dragging = false, hasDragged = false, dragStart = null, viewAtDrag = null;
    let lastHoverEntityId = null;
    const onWheel = (e) => {
      e.preventDefault();
      const rect = c.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const [wx, wy] = s2w(mx, my);
      const s = stateRef.current;
      const factor = e.deltaY < 0 ? 1.15 : 1/1.15;
      s.zoom = Math.max(0.15, Math.min(8, s.zoom * factor));
      const cx = c.width / 2, cy = c.height / 2;
      s.viewX = wx - (mx - cx) / s.zoom;
      s.viewY = wy + (my - cy) / s.zoom;
    };
    const onDown = (e) => {
      if (e.button !== 0) return;
      dragging = true; hasDragged = false;
      dragStart = [e.clientX, e.clientY];
      viewAtDrag = [stateRef.current.viewX, stateRef.current.viewY];
      c.classList.add('dragging');
    };
    const onMove = (e) => {
      const rect = c.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      if (dragging) {
        const dx = e.clientX - dragStart[0], dy = e.clientY - dragStart[1];
        if (Math.abs(dx) + Math.abs(dy) > 3) hasDragged = true;
        stateRef.current.viewX = viewAtDrag[0] - dx / stateRef.current.zoom;
        stateRef.current.viewY = viewAtDrag[1] + dy / stateRef.current.zoom;
        return;
      }
      // hover detection
      const hit = pickEntity(mx, my);
      const hitId = hit ? hit.id : null;
      if (hitId !== lastHoverEntityId) {
        lastHoverEntityId = hitId;
        onHoverEntity && onHoverEntity(hit, { x: e.clientX, y: e.clientY });
      } else if (hit) {
        // keep position fresh
        onHoverEntity && onHoverEntity(hit, { x: e.clientX, y: e.clientY });
      }
    };
    const onUp = (e) => {
      if (!dragging) return;
      dragging = false;
      c.classList.remove('dragging');
      if (!hasDragged) {
        const rect = c.getBoundingClientRect();
        const mx = e.clientX - rect.left, my = e.clientY - rect.top;
        const hit = pickEntity(mx, my);
        if (hit) {
          onSelectEntity && onSelectEntity(hit.id);
          audio && audio.click();
        } else {
          onSelectEntity && onSelectEntity(null);
          const [wx, wy] = s2w(mx, my);
          onMapClick && onMapClick(wx, wy);
        }
      }
    };
    const onLeave = () => {
      onHoverEntity && onHoverEntity(null, null);
      lastHoverEntityId = null;
    };
    c.addEventListener('wheel', onWheel, { passive: false });
    c.addEventListener('mousedown', onDown);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    c.addEventListener('mouseleave', onLeave);
    return () => {
      c.removeEventListener('wheel', onWheel);
      c.removeEventListener('mousedown', onDown);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      c.removeEventListener('mouseleave', onLeave);
    };
  }, [sim, onSelectEntity, onHoverEntity, onMapClick, audio]);

  function pickEntity(sx, sy) {
    let best = null, bd = 14;
    for (const ent of sim.entities.values()) {
      if (ent.destroyed) continue;
      const [ex, ey] = w2s(ent.x, ent.y);
      const d = Math.hypot(sx - ex, sy - ey);
      if (d < bd) { bd = d; best = ent; }
    }
    return best;
  }

  // -------- Imperative API for toolbar --------
  // Exposed by useImperativeHandle-ish via a window helper
  MapView.zoomIn = () => { stateRef.current.zoom = Math.min(8, stateRef.current.zoom * 1.25); };
  MapView.zoomOut = () => { stateRef.current.zoom = Math.max(0.15, stateRef.current.zoom / 1.25); };
  MapView.fit = () => {
    const all = Array.from(sim.entities.values()).filter(e => !e.destroyed);
    if (!all.length) { stateRef.current.viewX = 0; stateRef.current.viewY = 0; stateRef.current.zoom = 1; return; }
    let mnx=Infinity, mny=Infinity, mxx=-Infinity, mxy=-Infinity;
    for (const e of all) { mnx=Math.min(mnx,e.x); mxx=Math.max(mxx,e.x); mny=Math.min(mny,e.y); mxy=Math.max(mxy,e.y); }
    stateRef.current.viewX = (mnx + mxx) / 2;
    stateRef.current.viewY = (mny + mxy) / 2;
    const rx = (mxx - mnx) * 1.4 || 400;
    const ry = (mxy - mny) * 1.4 || 300;
    const c = canvasRef.current;
    stateRef.current.zoom = Math.max(0.15, Math.min(8,
      Math.min(c.width / rx, c.height / ry)
    ));
  };
  MapView.shake = (mag = 6) => {
    stateRef.current.shakeX = (Math.random() - 0.5) * mag * 2;
    stateRef.current.shakeY = (Math.random() - 0.5) * mag * 2;
  };
  MapView.getZoomPercent = () => Math.round(stateRef.current.zoom * 100);
  MapView.centerOn = (x, y) => {
    stateRef.current.viewX = x;
    stateRef.current.viewY = y;
  };

  return (
    <div ref={wrapRef} style={{ position: 'absolute', inset: 0 }}>
      <canvas id="map-canvas" ref={canvasRef} />
    </div>
  );
}

window.MapView = MapView;
window.buildTerrainCanvas = buildTerrainCanvas;
