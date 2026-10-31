// Original, illustrative SVG kitchen scenes (not footage of real food).
// Each scene has three layers — prep, cook, plate — shown one at a time by
// kitchen-preview.js. Motion lives in customer.css under `.layer.is-active`.

const steam = (xs, y, cls = "") =>
  xs
    .map(
      (x, i) =>
        `<path class="anim-steam ${cls}" style="--d:${(i * 0.5).toFixed(1)}s" d="M${x} ${y} c -7 -10 7 -18 0 -28 c -7 -10 7 -18 0 -28" />`,
    )
    .join("");

const flames = (xs, y) =>
  xs
    .map(
      (x, i) =>
        `<path class="anim-flame" style="--d:${(i * 0.13).toFixed(2)}s" d="M${x - 5} ${y} q 5 -18 10 0 z" fill="${i % 2 ? "#f6b13b" : "#ee7a22"}" />`,
    )
    .join("");

const plate = () => `
  <ellipse cx="160" cy="180" rx="112" ry="16" fill="#000" opacity=".28" />
  <ellipse class="anim-in" cx="160" cy="166" rx="110" ry="40" fill="#f4efe6" />
  <ellipse class="anim-in" cx="160" cy="164" rx="82" ry="28" fill="#fffdf8" stroke="#e3dccf" stroke-width="2" />`;

const board = () => `
  <rect x="26" y="150" width="268" height="42" rx="12" fill="#b9875a" />
  <rect x="26" y="182" width="268" height="10" rx="5" fill="#94683f" />`;

// ---- Fried (the complete reference example) ----
function friedPiece(cx, cy, shape, attrs) {
  return shape === "ball"
    ? `<circle cx="${cx}" cy="${cy}" r="12" ${attrs} />`
    : `<ellipse cx="${cx}" cy="${cy}" rx="21" ry="11" ${attrs} />`;
}

function friedSvg(shape) {
  const raw = shape === "ball" ? "#9fb46a" : "#efc3ac"; // raw falafel mix / raw cutlet
  const crumbs = (cx, cy) =>
    [-9, 0, 8]
      .map((dx, i) => `<circle cx="${cx + dx}" cy="${cy + (i % 2 ? 3 : -2)}" r="1.6" fill="#8f5a1d" />`)
      .join("");
  const prepPieces = [
    [70, 166, 178],
    [112, 171, 136],
    [154, 164, 94],
  ]
    .map(([x, y, dx], i) =>
      friedPiece(x, y, shape, `class="anim-dip" style="--dx:${dx}px;--d:${i * 0.3}s;--raw:${raw}" fill="${raw}"`),
    )
    .join("");
  const cookPieces = [
    [108, 157],
    [152, 166],
    [196, 154],
  ]
    .map(([x, y], i) => friedPiece(x, y, shape, `class="anim-fry" style="--d:${i * 0.12}s"`))
    .join("");
  const bubbles = [
    [92, 166, 3],
    [124, 150, 2.5],
    [140, 172, 2],
    [170, 156, 3],
    [182, 171, 2.2],
    [214, 162, 2.6],
    [228, 150, 2],
  ]
    .map(([x, y, r], i) => `<circle class="anim-bubble" style="--d:${(i * 0.17).toFixed(2)}s" cx="${x}" cy="${y}" r="${r}" />`)
    .join("");
  const platedPieces = [
    [132, 160],
    [166, 168],
    [198, 157],
  ]
    .map(
      ([x, y], i) =>
        `<g class="anim-in anim-drop" style="--d:${0.15 + i * 0.15}s">${friedPiece(x, y, shape, 'fill="#c98a2e"')}${crumbs(x, y)}</g>`,
    )
    .join("");

  return `
  <g class="layer l-prep" transform="translate(0 -24)">
    ${board()}
    <path d="M196 150 a52 30 0 0 0 104 0 z" fill="#d8d0c3" />
    <ellipse cx="248" cy="150" rx="52" ry="9" fill="#e0b45c" />
    ${crumbs(236, 149)}${crumbs(262, 151)}
    ${prepPieces}
  </g>
  <g class="layer l-cook">
    ${flames([96, 124, 152, 180, 208], 214)}
    <rect x="256" y="150" width="60" height="13" rx="6" fill="#3d3935" />
    <ellipse cx="150" cy="162" rx="112" ry="38" fill="#55504b" />
    <ellipse cx="150" cy="157" rx="112" ry="36" fill="none" stroke="#8f8983" stroke-width="4" />
    <ellipse cx="150" cy="158" rx="100" ry="29" fill="#8f6420" opacity=".92" />
    <ellipse class="anim-shimmer" cx="128" cy="150" rx="40" ry="6" fill="#f3cf72" opacity=".35" />
    ${cookPieces}
    ${bubbles}
    ${steam([116, 152, 190], 128)}
  </g>
  <g class="layer l-plate">
    ${plate()}
    ${platedPieces}
    <path class="anim-in anim-drop" style="--d:.6s" d="M222 170 a17 11 0 0 1 34 0 z" fill="#f4d34a" stroke="#dcb22a" stroke-width="2" />
    <g class="anim-in anim-drop" style="--d:.75s" fill="#4f8a3a">
      <circle cx="110" cy="172" r="4" /><circle cx="117" cy="167" r="3.5" /><circle cx="104" cy="166" r="3" />
    </g>
    ${steam([140, 178], 136, "steam-soft")}
  </g>`;
}

// ---- Wok (sample) ----
function wokSvg() {
  const veg = (x, y, i) => {
    const shapes = [
      `<rect x="${x}" y="${y}" width="14" height="5" rx="2" fill="#d9562f" />`,
      `<circle cx="${x + 5}" cy="${y + 3}" r="5" fill="#ee8a2a" />`,
      `<rect x="${x}" y="${y}" width="10" height="4" rx="2" fill="#5d9b46" />`,
    ];
    return shapes[i % 3];
  };
  const prepVeg = [70, 92, 114, 136, 158, 180]
    .map((x, i) => `<g class="anim-pop" style="--d:${(i * 0.22).toFixed(2)}s">${veg(x, 160 + (i % 2) * 8, i)}</g>`)
    .join("");
  const noodles = (dy, cls = "") =>
    [0, 1, 2, 3]
      .map(
        (i) =>
          `<path class="${cls}" d="M${92 + i * 10} ${150 + dy + i * 3} q 18 -10 36 0 t 36 0 t 36 0" fill="none" stroke="#e2b25c" stroke-width="4" stroke-linecap="round" />`,
      )
      .join("");
  const mixVeg = [
    [110, 146],
    [150, 156],
    [190, 144],
    [132, 162],
    [204, 160],
  ]
    .map(([x, y], i) => veg(x, y, i))
    .join("");
  return `
  <g class="layer l-prep">
    ${board()}
    <g class="anim-chop">
      <rect x="204" y="112" width="12" height="40" rx="3" fill="#cfd3d6" />
      <rect x="203" y="96" width="14" height="20" rx="4" fill="#3d3935" />
    </g>
    ${prepVeg}
  </g>
  <g class="layer l-cook">
    ${flames([110, 135, 160, 185, 210], 214)}
    <rect x="270" y="132" width="44" height="12" rx="6" fill="#3d3935" />
    <path d="M40 138 Q160 236 280 138 Z" fill="#3f3b37" />
    <path d="M40 138 L280 138" stroke="#8f8983" stroke-width="4" stroke-linecap="round" />
    <g class="anim-toss">${noodles(-10)}${mixVeg}</g>
    ${steam([120, 160, 200], 118)}
  </g>
  <g class="layer l-plate">
    ${plate()}
    <g class="anim-in anim-drop" style="--d:.15s">${noodles(0)}</g>
    <g class="anim-in anim-drop" style="--d:.35s">${mixVeg}</g>
    ${steam([146, 182], 132, "steam-soft")}
  </g>`;
}

// ---- Oven (sample) ----
function ovenSvg() {
  const chunks = (cls, offsetY = 0) =>
    [
      [96, "#e07b2e"],
      [124, "#9c2f4a"],
      [152, "#f0a541"],
      [180, "#e07b2e"],
      [208, "#9c2f4a"],
    ]
      .map(
        ([x, c], i) =>
          `<rect class="${cls}" style="--d:${(i * 0.2).toFixed(1)}s" x="${x}" y="${150 + offsetY + (i % 2) * 6}" width="20" height="14" rx="5" fill="${c}" />`,
      )
      .join("");
  return `
  <g class="layer l-prep">
    <rect x="70" y="160" width="180" height="22" rx="4" fill="#6b6560" />
    <rect x="76" y="156" width="168" height="8" rx="3" fill="#8d8781" />
    ${chunks("anim-drop anim-in", -4)}
    <path class="anim-drizzle" d="M100 120 q 60 18 120 0" fill="none" stroke="#c9b347" stroke-width="3" stroke-linecap="round" stroke-dasharray="140" />
  </g>
  <g class="layer l-cook">
    <rect x="50" y="56" width="220" height="150" rx="14" fill="#4a4440" />
    <circle cx="90" cy="76" r="8" fill="#8f8983" /><circle cx="118" cy="76" r="8" fill="#8f8983" />
    <rect x="70" y="96" width="180" height="96" rx="8" fill="#241c18" />
    <rect class="anim-glow" x="70" y="96" width="180" height="96" rx="8" fill="#f08a24" />
    <rect x="86" y="160" width="148" height="10" rx="3" fill="#6b6560" />
    ${chunks("anim-roast", -6)}
  </g>
  <g class="layer l-plate">
    ${plate()}
    <g transform="translate(16 8) scale(.9)"><g class="anim-in anim-drop" style="--d:.15s">${chunks("", 0)}</g></g>
    <g class="anim-in anim-drop" style="--d:.5s" stroke="#4f7f37" stroke-width="2.5" stroke-linecap="round">
      <path d="M112 176 l 16 -8" /><path d="M200 176 l 16 -6" />
    </g>
    ${steam([150, 186], 134, "steam-soft")}
  </g>`;
}

export const SCENES = {
  fried: {
    label: "טיגון",
    sound: "fried",
    stages: ["ציפוי בפירורי לחם", "טיגון עמוק עד הזהבה", "הגשה עם לימון ופטרוזיליה"],
    svg: (prep) => friedSvg(prep.shape),
  },
  wok: {
    label: "הקפצה",
    sound: "wok",
    stages: ["חיתוך ירקות", "הקפצה בווק על אש גבוהה", "הגשה בקן אטריות"],
    svg: () => wokSvg(),
  },
  oven: {
    label: "אפייה",
    sound: "oven",
    stages: ["סידור בתבנית ושמן זית", "צלייה בתנור", "הגשה עם רוזמרין"],
    svg: () => ovenSvg(),
  },
};

// Small static plated illustration for dish cards.
export function thumbSvg(colors) {
  const [a, b, c] = colors;
  return `<svg viewBox="0 0 200 130" aria-hidden="true" focusable="false">
    <ellipse cx="100" cy="98" rx="84" ry="14" fill="#000" opacity=".18" />
    <ellipse cx="100" cy="86" rx="82" ry="32" fill="#f4efe6" />
    <ellipse cx="100" cy="84" rx="60" ry="22" fill="#fffdf8" stroke="#e3dccf" stroke-width="2" />
    <ellipse cx="80" cy="82" rx="18" ry="10" fill="${a}" />
    <ellipse cx="106" cy="88" rx="18" ry="10" fill="${b}" />
    <ellipse cx="128" cy="78" rx="12" ry="8" fill="${c}" />
  </svg>`;
}
