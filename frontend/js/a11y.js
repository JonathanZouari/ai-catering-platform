// Accessibility toolbar (Israeli standard IS 5568 / regulation 35): a button on every page that opens
// a panel with display adjustments. Choices are kept in localStorage and applied as classes on <html>.
// Self-contained: no dependencies, so it works on every page, including before the app boots.
const KEY = "yummai-a11y";
const SIZES = [100, 115, 130, 150]; // percent of the browser's base font size

const TOGGLES = [
  ["contrast", "ניגודיות גבוהה"],
  ["light", "ניגודיות בהירה"],
  ["gray", "גווני אפור"],
  ["links", "הדגשת קישורים"],
  ["font", "גופן קריא"],
  ["spacing", "ריווח טקסט"],
  ["motion", "עצירת אנימציות"],
  ["cursor", "סמן גדול"],
];

function load() {
  try {
    return { size: 0, ...JSON.parse(localStorage.getItem(KEY) ?? "{}") };
  } catch {
    return { size: 0 };
  }
}
const state = load();

function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* storage blocked: the choices still apply for this visit */
  }
}

function apply() {
  const root = document.documentElement;
  state.size = Math.min(Math.max(Number(state.size) || 0, 0), SIZES.length - 1);
  root.style.fontSize = state.size ? `${SIZES[state.size]}%` : "";
  for (const [name] of TOGGLES) root.classList.toggle(`a11y-${name}`, Boolean(state[name]));
}

// Apply immediately (before the panel is built) so a saved choice does not flash.
apply();

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  }
  node.append(...children);
  return node;
}

function build() {
  const button = el("button", {
    class: "a11y-btn", type: "button", id: "a11y-btn",
    "aria-expanded": "false", "aria-controls": "a11y-panel", "aria-label": "תפריט נגישות",
  });
  button.innerHTML =
    '<svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true" focusable="false">' +
    '<circle cx="12" cy="4.2" r="2.2" fill="currentColor"/>' +
    '<path d="M4 8.5h16M12 8.5v5.5m0 0-3.5 6.5m3.5-6.5 3.5 6.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';

  const panel = el("section", {
    class: "a11y-panel", id: "a11y-panel", role: "dialog", "aria-label": "תפריט נגישות", hidden: "",
  });
  const title = el("h2", { class: "a11y-title", text: "נגישות" });
  const close = el("button", { class: "a11y-close", type: "button", "aria-label": "סגירת תפריט הנגישות", text: "✕" });
  panel.append(el("div", { class: "a11y-head" }, title, close));

  // Text size
  const sizeLabel = el("span", { class: "a11y-size-label", "aria-live": "polite" });
  const smaller = el("button", { class: "a11y-opt", type: "button", "aria-label": "הקטנת טקסט", text: "א-" });
  const bigger = el("button", { class: "a11y-opt", type: "button", "aria-label": "הגדלת טקסט", text: "א+" });
  const updateSize = () => {
    sizeLabel.textContent = `גודל טקסט: ${SIZES[state.size]}%`;
    smaller.disabled = state.size <= 0;
    bigger.disabled = state.size >= SIZES.length - 1;
  };
  smaller.addEventListener("click", () => { state.size -= 1; commit(); });
  bigger.addEventListener("click", () => { state.size += 1; commit(); });
  panel.append(el("div", { class: "a11y-row" }, smaller, sizeLabel, bigger));

  // Toggles
  const toggles = new Map();
  const group = el("div", { class: "a11y-grid" });
  for (const [name, label] of TOGGLES) {
    const b = el("button", { class: "a11y-opt a11y-toggle", type: "button", "aria-pressed": "false", text: label });
    b.addEventListener("click", () => {
      state[name] = !state[name];
      // The two contrast modes exclude each other.
      if (state[name] && name === "contrast") state.light = false;
      if (state[name] && name === "light") state.contrast = false;
      commit();
    });
    toggles.set(name, b);
    group.append(b);
  }
  panel.append(group);

  const reset = el("button", { class: "a11y-opt a11y-reset", type: "button", text: "איפוס הגדרות" });
  reset.addEventListener("click", () => {
    state.size = 0;
    for (const [name] of TOGGLES) state[name] = false;
    commit();
  });
  panel.append(reset, el("a", { class: "a11y-statement", href: "/accessibility/", text: "הצהרת נגישות" }));

  function commit() {
    apply();
    save();
    updateSize();
    for (const [name, b] of toggles) b.setAttribute("aria-pressed", String(Boolean(state[name])));
  }

  function setOpen(open) {
    panel.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    if (open) {
      title.setAttribute("tabindex", "-1");
      title.focus();
    } else {
      button.focus();
    }
  }
  button.addEventListener("click", () => setOpen(panel.hidden));
  close.addEventListener("click", () => setOpen(false));
  panel.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setOpen(false);
  });

  commit();
  document.body.append(button, panel);
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
else build();
