// Top-down illustrated plates, drawn as SVG so the demo needs no photos.
// Seeded randomness keeps every render of a dish identical.

let uid = 0;

function rng(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function inDisk(rand, rMax, cx = 200, cy = 200) {
  const r = rMax * Math.sqrt(rand());
  const a = rand() * Math.PI * 2;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a), a];
}

const pick = (rand, list) => list[Math.floor(rand() * list.length)];
const deg = (rand, span = 360) => Math.round(rand() * span);
const f = (n) => n.toFixed(1);

function specks(rand, n, rMax, colors, size = [1.5, 3]) {
  let out = "";
  for (let i = 0; i < n; i++) {
    const [x, y] = inDisk(rand, rMax);
    out += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(size[0] + rand() * (size[1] - size[0]))}" fill="${pick(rand, colors)}"/>`;
  }
  return out;
}

function leaves(rand, n, rMax, colors, rx = 9, ry = 4) {
  let out = "";
  for (let i = 0; i < n; i++) {
    const [x, y] = inDisk(rand, rMax);
    out += `<ellipse cx="${f(x)}" cy="${f(y)}" rx="${f(rx * (0.7 + rand() * 0.6))}" ry="${f(ry)}" fill="${pick(rand, colors)}" transform="rotate(${deg(rand)} ${f(x)} ${f(y)})"/>`;
  }
  return out;
}

const foods = {
  hummus(rand, id) {
    let spiral = "M200 200";
    for (let t = 0; t <= 1; t += 0.01) {
      const r = 18 + 98 * t, a = t * Math.PI * 7;
      spiral += ` L${f(200 + r * Math.cos(a))} ${f(200 + r * Math.sin(a))}`;
    }
    let peas = "";
    for (let i = 0; i < 11; i++) {
      const [x, y] = inDisk(rand, 34);
      peas += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(8 + rand() * 3)}" fill="#ecca8c" stroke="#c39a57" stroke-width="1.5"/>`;
    }
    return `
      <defs><radialGradient id="h${id}"><stop offset="0" stop-color="#f1dcb1"/><stop offset="1" stop-color="#d9b47a"/></radialGradient></defs>
      <circle cx="200" cy="200" r="128" fill="url(#h${id})"/>
      <path d="${spiral}" fill="none" stroke="#c9a062" stroke-width="9" stroke-linecap="round" opacity=".5"/>
      <ellipse cx="200" cy="200" rx="50" ry="42" fill="#c9a32f" opacity=".5"/>
      ${peas}
      ${specks(rand, 46, 62, ["#b5381f", "#c4502a"])}
      ${leaves(rand, 14, 96, ["#4f7a2a", "#6b9a3a"], 6, 3)}`;
  },

  salad(rand) {
    let chunks = "";
    const colors = ["#e07b39", "#c8412d", "#7fa34b", "#5b3a5e", "#f2b84b", "#e9894f"];
    for (let i = 0; i < 38; i++) {
      const [x, y] = inDisk(rand, 108);
      const s = 18 + rand() * 12, c = pick(rand, colors);
      chunks += `<rect x="${f(x - s / 2)}" y="${f(y - s / 2)}" width="${f(s)}" height="${f(s * 0.8)}" rx="6" fill="${c}" transform="rotate(${deg(rand)} ${f(x)} ${f(y)})"/>`;
      if (c === "#7fa34b") chunks += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(s / 4)}" fill="#dbe5a8"/>`;
    }
    return `
      <circle cx="200" cy="200" r="126" fill="#6a9440" opacity=".25"/>
      ${leaves(rand, 26, 112, ["#5f8a35", "#86ae4f", "#4c7428"], 24, 10)}
      ${chunks}
      ${leaves(rand, 40, 110, ["#f3e7c9"], 2.5, 1.3)}`;
  },

  meatballs(rand, id) {
    let balls = "";
    const spots = [[200, 200], ...Array.from({ length: 6 }, (_, i) => {
      const a = (i / 6) * Math.PI * 2 + 0.3;
      return [200 + 66 * Math.cos(a), 200 + 66 * Math.sin(a)];
    })];
    for (const [x, y] of spots) {
      balls += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(31 + rand() * 5)}" fill="url(#m${id})"/>`;
    }
    return `
      <defs>
        <radialGradient id="s${id}"><stop offset="0" stop-color="#d4572f"/><stop offset="1" stop-color="#9c321d"/></radialGradient>
        <radialGradient id="m${id}" cx=".35" cy=".35"><stop offset="0" stop-color="#a8673d"/><stop offset=".7" stop-color="#6e3a1f"/><stop offset="1" stop-color="#4e2614"/></radialGradient>
      </defs>
      <circle cx="200" cy="200" r="130" fill="url(#s${id})"/>
      ${specks(rand, 30, 124, ["#e8703f", "#c24425"], 4, 9)}
      ${balls}
      ${specks(rand, 60, 118, ["#3f6b22", "#5b8a2f"], 1.5, 3)}`;
  },

  majadra(rand, id) {
    let grains = "", onions = "";
    for (let i = 0; i < 280; i++) {
      const [x, y] = inDisk(rand, 122);
      grains += `<ellipse cx="${f(x)}" cy="${f(y)}" rx="4.2" ry="1.7" fill="${pick(rand, ["#ead6ae", "#c9a272", "#dcc092"])}" transform="rotate(${deg(rand)} ${f(x)} ${f(y)})"/>`;
    }
    for (let i = 0; i < 30; i++) {
      const [x, y] = inDisk(rand, 58);
      const r = 10 + rand() * 12, a = rand() * Math.PI * 2;
      onions += `<path d="M${f(x)} ${f(y)} a${f(r)} ${f(r)} 0 0 1 ${f(r * Math.cos(a))} ${f(r * Math.sin(a))}" fill="none" stroke="${pick(rand, ["#8c4a1c", "#b0642a", "#6e3412"])}" stroke-width="3.5" stroke-linecap="round"/>`;
    }
    return `
      <defs><radialGradient id="r${id}"><stop offset="0" stop-color="#d8b886"/><stop offset="1" stop-color="#bf9862"/></radialGradient></defs>
      <circle cx="200" cy="200" r="128" fill="url(#r${id})"/>
      ${grains}
      ${specks(rand, 130, 122, ["#4e3b2a", "#6a5038"], 2, 2.8)}
      ${onions}`;
  },

  salmon(rand, id) {
    let potatoes = "";
    for (let i = 0; i < 7; i++) {
      const a = Math.PI * (0.55 + i * 0.16);
      const x = 200 + 92 * Math.cos(a), y = 200 + 92 * Math.sin(a);
      potatoes += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(18 + rand() * 5)}" fill="url(#p${id})"/>`;
    }
    let stripes = "";
    for (let i = 0; i < 6; i++) stripes += `<line x1="${135 + i * 24}" y1="150" x2="${115 + i * 24}" y2="245" stroke="#fff3ea" stroke-width="5" opacity=".55" stroke-linecap="round"/>`;
    let lemon = "";
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      lemon += `<line x1="282" y1="138" x2="${f(282 + 24 * Math.cos(a))}" y2="${f(138 + 24 * Math.sin(a))}" stroke="#fff6c8" stroke-width="2"/>`;
    }
    return `
      <defs>
        <linearGradient id="f${id}" x1="0" x2="1"><stop offset="0" stop-color="#f6a173"/><stop offset="1" stop-color="#e06a3a"/></linearGradient>
        <radialGradient id="p${id}" cx=".4" cy=".35"><stop offset="0" stop-color="#f6dc85"/><stop offset="1" stop-color="#d7a83f"/></radialGradient>
      </defs>
      ${potatoes}
      <g transform="rotate(-18 200 200)">
        <rect x="110" y="145" width="190" height="105" rx="34" fill="url(#f${id})"/>
        <clipPath id="c${id}"><rect x="110" y="145" width="190" height="105" rx="34"/></clipPath>
        <g clip-path="url(#c${id})">${stripes}</g>
      </g>
      ${leaves(rand, 22, 50, ["#3f6b22", "#5b8a2f"], 7, 1.6)}
      <circle cx="282" cy="138" r="30" fill="#f7d84a" stroke="#fff6c8" stroke-width="4"/>
      ${lemon}`;
  },
};

export function plateSVG(kind, seed = 7) {
  const id = ++uid;
  const rand = rng(seed);
  return `<svg viewBox="0 0 400 400" aria-hidden="true">
    <defs>
      <radialGradient id="rim${id}"><stop offset=".78" stop-color="#f7f6f2"/><stop offset=".92" stop-color="#e7e4dd"/><stop offset="1" stop-color="#d6d2ca"/></radialGradient>
    </defs>
    <circle cx="200" cy="200" r="196" fill="url(#rim${id})"/>
    <circle cx="200" cy="200" r="152" fill="#f4f2ee" stroke="#e4e0d8" stroke-width="2"/>
    ${foods[kind](rand, id)}
  </svg>`;
}
