// Synthesized (Web Audio) cooking sounds — no audio files, no recordings.
// The AudioContext is created only from a user gesture (prime()), and
// stop() tears down every source and timer so nothing keeps playing.

const PROFILES = {
  // filter: continuous sizzle bed; crackles per second; crackle loudness
  fried: { type: "highpass", freq: 1800, bed: 0.05, rate: 14, pop: 0.22 },
  wok: { type: "highpass", freq: 1100, bed: 0.07, rate: 6, pop: 0.16 },
  oven: { type: "lowpass", freq: 380, bed: 0.09, rate: 1, pop: 0.05 },
};

let ctx = null;
let noise = null;
let master = null;
let sources = [];
let crackleTimer = 0;

// Call synchronously inside a click/keypress handler.
export function prime() {
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return false;
  if (!ctx) {
    ctx = new AC();
    const length = ctx.sampleRate * 2;
    noise = ctx.createBuffer(1, length, ctx.sampleRate);
    const data = noise.getChannelData(0);
    for (let i = 0; i < length; i++) data[i] = Math.random() * 2 - 1;
  }
  if (ctx.state === "suspended") ctx.resume();
  return true;
}

export function start(profileName) {
  if (!ctx) return;
  stop();
  const p = PROFILES[profileName] ?? PROFILES.fried;
  const now = ctx.currentTime;

  master = ctx.createGain();
  master.gain.setValueAtTime(0, now);
  master.gain.linearRampToValueAtTime(1, now + 0.4);
  master.connect(ctx.destination);

  const bed = ctx.createBufferSource();
  bed.buffer = noise;
  bed.loop = true;
  const filter = ctx.createBiquadFilter();
  filter.type = p.type;
  filter.frequency.value = p.freq;
  const bedGain = ctx.createGain();
  bedGain.gain.value = p.bed;
  bed.connect(filter).connect(bedGain).connect(master);
  bed.start();
  sources.push(bed);

  const crackle = () => {
    if (!master) return;
    const t = ctx.currentTime;
    const src = ctx.createBufferSource();
    src.buffer = noise;
    const band = ctx.createBiquadFilter();
    band.type = "bandpass";
    band.frequency.value = 2500 + Math.random() * 4500;
    const g = ctx.createGain();
    const len = 0.012 + Math.random() * 0.03;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(p.pop * (0.4 + Math.random() * 0.6), t + 0.003);
    g.gain.exponentialRampToValueAtTime(0.0001, t + len);
    src.connect(band).connect(g).connect(master);
    src.start(t, Math.random() * 1.5, len + 0.01);
    crackleTimer = setTimeout(crackle, (1000 / p.rate) * (0.3 + Math.random() * 1.4));
  };
  crackle();
}

// Fade out over `fade` seconds, then stop every node.
export function stop(fade = 0.08) {
  clearTimeout(crackleTimer);
  crackleTimer = 0;
  if (!ctx || !master) return;
  const end = ctx.currentTime + fade;
  master.gain.cancelScheduledValues(ctx.currentTime);
  master.gain.setValueAtTime(master.gain.value, ctx.currentTime);
  master.gain.linearRampToValueAtTime(0, end);
  for (const s of sources) s.stop(end + 0.02);
  const old = master;
  setTimeout(() => old.disconnect(), (fade + 0.1) * 1000);
  sources = [];
  master = null;
}
