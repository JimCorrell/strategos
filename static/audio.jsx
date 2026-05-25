// ============================================================
// Strategos — synthesized audio FX (WebAudio, no assets)
// ============================================================

class AudioFX {
  constructor() {
    this.ctx = null;
    this.master = null;
    this.enabled = false;
    this._lastSound = {};
  }

  _ensure() {
    if (this.ctx) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    this.ctx = new AC();
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.20;
    this.master.connect(this.ctx.destination);
  }

  enable() {
    this._ensure();
    if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume();
    this.enabled = true;
  }
  disable() { this.enabled = false; }
  toggle() {
    if (this.enabled) this.disable();
    else this.enable();
    return this.enabled;
  }

  // throttle to avoid sound spam
  _throttle(key, ms = 50) {
    const now = performance.now();
    if (this._lastSound[key] && now - this._lastSound[key] < ms) return false;
    this._lastSound[key] = now;
    return true;
  }

  click() {
    if (!this.enabled || !this._throttle('click', 30)) return;
    this._ensure(); if (!this.ctx) return;
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = 'square';
    osc.frequency.setValueAtTime(1400, t);
    osc.frequency.exponentialRampToValueAtTime(900, t + 0.04);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.35, t + 0.003);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.05);
    osc.connect(g); g.connect(this.master);
    osc.start(t); osc.stop(t + 0.06);
  }

  fire(type = 'infantry') {
    if (!this.enabled || !this._throttle('fire', 25)) return;
    this._ensure(); if (!this.ctx) return;
    const t = this.ctx.currentTime;
    // noise burst
    const buf = this.ctx.createBuffer(1, 0.12 * this.ctx.sampleRate, this.ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < data.length; i++) {
      const env = Math.exp(-i / (data.length * 0.18));
      data[i] = (Math.random() * 2 - 1) * env;
    }
    const noise = this.ctx.createBufferSource();
    noise.buffer = buf;

    const lp = this.ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = type === 'artillery' ? 380 : type === 'tank' ? 700 : 1500;
    lp.Q.value = 1;

    const g = this.ctx.createGain();
    g.gain.setValueAtTime(type === 'artillery' ? 0.5 : 0.22, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.12);

    noise.connect(lp); lp.connect(g); g.connect(this.master);
    noise.start(t);

    // body pulse
    const osc = this.ctx.createOscillator();
    const og = this.ctx.createGain();
    osc.type = 'sawtooth';
    const baseF = type === 'artillery' ? 70 : type === 'tank' ? 160 : 320;
    osc.frequency.setValueAtTime(baseF * 1.8, t);
    osc.frequency.exponentialRampToValueAtTime(baseF, t + 0.06);
    og.gain.setValueAtTime(0.0001, t);
    og.gain.exponentialRampToValueAtTime(0.15, t + 0.005);
    og.gain.exponentialRampToValueAtTime(0.0001, t + 0.08);
    osc.connect(og); og.connect(this.master);
    osc.start(t); osc.stop(t + 0.1);
  }

  hit() {
    if (!this.enabled || !this._throttle('hit', 60)) return;
    this._ensure(); if (!this.ctx) return;
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(420, t);
    osc.frequency.exponentialRampToValueAtTime(180, t + 0.08);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.22, t + 0.003);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.1);
    osc.connect(g); g.connect(this.master);
    osc.start(t); osc.stop(t + 0.12);
  }

  boom() {
    if (!this.enabled || !this._throttle('boom', 90)) return;
    this._ensure(); if (!this.ctx) return;
    const t = this.ctx.currentTime;
    // sub thump
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(180, t);
    osc.frequency.exponentialRampToValueAtTime(28, t + 0.35);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.55, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.45);
    osc.connect(g); g.connect(this.master);
    osc.start(t); osc.stop(t + 0.5);

    // noise tail
    const buf = this.ctx.createBuffer(1, 0.35 * this.ctx.sampleRate, this.ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < data.length; i++) {
      const env = Math.exp(-i / (data.length * 0.4));
      data[i] = (Math.random() * 2 - 1) * env;
    }
    const noise = this.ctx.createBufferSource();
    noise.buffer = buf;
    const lp = this.ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 500;
    const ng = this.ctx.createGain();
    ng.gain.setValueAtTime(0.35, t);
    ng.gain.exponentialRampToValueAtTime(0.0001, t + 0.35);
    noise.connect(lp); lp.connect(ng); ng.connect(this.master);
    noise.start(t);
  }

  blip() {
    if (!this.enabled || !this._throttle('blip', 80)) return;
    this._ensure(); if (!this.ctx) return;
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, t);
    osc.frequency.exponentialRampToValueAtTime(1320, t + 0.04);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.18, t + 0.005);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.08);
    osc.connect(g); g.connect(this.master);
    osc.start(t); osc.stop(t + 0.1);
  }
}

window.AudioFX = AudioFX;
