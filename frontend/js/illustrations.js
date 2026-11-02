// Hand-drawn line illustrations on a 64x64 grid. pathLength=1 lets CSS draw each stroke in (see .motion .ill in base.css).
// A path given as [d, className] gets a looping detail animation (steam, flame).
const ILL = {
  basket: ["M10 28h44l-5 24H15z", "M20 28c0-11 24-11 24 0", "M18 37h28M20 45h24", "M27 28c-3-7 0-13 7-16-1 7-3 12-7 16z", "M39 28l7-13M45 14l5-4M47 17l5 0"],
  pot: ["M14 30h36v15a9 9 0 0 1-9 9H23a9 9 0 0 1-9-9z", "M9 30h46", "M28 25h8", ["M24 19c-3-4 3-6 0-10", "steam"], ["M32 17c-3-4 3-6 0-10", "steam"], ["M40 19c-3-4 3-6 0-10", "steam"]],
  grill: ["M6 42L58 16", "M15 38a5 5 0 1 0 10-5 5 5 0 1 0-10 5z", "M27 32a5 5 0 1 0 10-5 5 5 0 1 0-10 5z", "M39 26a5 5 0 1 0 10-5 5 5 0 1 0-10 5z", ["M20 58c-5-6 2-9 0-15 7 4 9 9 4 15", "flame"], ["M38 58c-5-6 2-9 0-15 7 4 9 9 4 15", "flame"]],
  glass: ["M38 8h14c0 11-2 18-7 18s-7-7-7-18z", "M45 26v20M39 46h12", "M4 48a17 5 0 1 0 34 0 17 5 0 1 0-34 0z", "M14 22v14M11 22v6a3 3 0 0 0 6 0v-6"],
  lemon: ["M12 36c0-13 11-22 24-22 9 0 15 6 15 15 0 13-11 22-24 22-9 0-15-6-15-15z", "M51 22l5-4", "M51 22c2-7 8-9 11-7-2 5-7 8-11 7z", "M22 38c4-8 12-14 20-15"],
  olive: ["M4 54C20 42 38 26 60 10", "M16 45c-3-7 1-12 7-14 0 6-2 11-7 14z", "M26 37c6-3 12-1 14 4-6 1-11 0-14-4z", "M32 30c-3-7 1-12 7-14 0 6-2 11-7 14z", "M42 22c6-3 12-1 14 4-6 1-11 0-14-4z", "M17 50a4 3 0 1 0 8 0 4 3 0 1 0-8 0z"],
  calendar: ["M12 16h40v38H12z", "M12 26h40", "M22 10v10M42 10v10", "M22 36h4M30 36h4M38 36h4M22 44h4M30 44h4"],
  plate: ["M16 32a16 16 0 1 0 32 0 16 16 0 1 0-32 0z", "M23 32a9 9 0 1 0 18 0 9 9 0 1 0-18 0z", "M8 12v40M5 12v9a3 3 0 0 0 6 0v-9", "M57 12c-5 5-5 15 0 18v22"],
  sign: ["M16 8h24l10 10v38H16z", "M40 8v10h10", "M23 36l6 6 12-14", "M22 50c4-3 6 2 9-1s5-2 8 0"],
  arrow: ["M4 28C16 8 40 4 58 18", "M50 11l8 7-10 3"],
};

export function illustration(name) {
  const paths = ILL[name].map((p, i) => {
    const [d, cls] = [].concat(p);
    return `<path pathLength="1" d="${d}"${cls ? ` class="${cls}"` : ""} style="--p:${i}"/>`;
  });
  return `<svg class="ill" viewBox="0 0 64 64" aria-hidden="true">${paths.join("")}</svg>`;
}

// Replace every <i data-ill="name"></i> placeholder under root with its SVG.
export function hydrateIllustrations(root = document) {
  root.querySelectorAll("i[data-ill]").forEach((el) => (el.outerHTML = illustration(el.dataset.ill)));
}
