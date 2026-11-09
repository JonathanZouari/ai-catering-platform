// Accessibility menu: a small fixed button that opens a panel with display settings and a link to the
// accessibility statement. Settings live as classes on <html> (CSS in a11y.css) and persist per browser.
// The site is accessible without this menu; it only adds personal display preferences.
import { h } from "./dom.js";

const KEY = "yumm.a11y.v1";
const TEXT_STEPS = [100, 112.5, 125, 137.5, 150]; // percent of the browser's own font size; CSS is rem-based
const TOGGLES = [
  { id: "contrast", cls: "a11y-contrast", label: "ניגודיות גבוהה" },
  { id: "motion", cls: "a11y-no-motion", label: "עצירת אנימציות" },
  { id: "links", cls: "a11y-underline", label: "הדגשת קישורים" },
];

function load() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY)) ?? {};
    // Whitelist: only known keys and value types survive, whatever is stored.
    const text = Number.isInteger(s.text) && s.text >= 0 && s.text < TEXT_STEPS.length ? s.text : 0;
    return { text, ...Object.fromEntries(TOGGLES.map((t) => [t.id, s[t.id] === true])) };
  } catch {
    return { text: 0, contrast: false, motion: false, links: false };
  }
}

function save(s) {
  try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* private mode: settings last for this page only */ }
}

let settings = load();

function apply() {
  const root = document.documentElement;
  root.style.fontSize = settings.text ? `${TEXT_STEPS[settings.text]}%` : "";
  root.classList.toggle("a11y-text-lg", settings.text > 0); // lets tight rows (e.g. the stepper) wrap
  for (const t of TOGGLES) root.classList.toggle(t.cls, settings[t.id]);
}
apply();

// Polite live region of our own, so the menu works on pages without #announce.
const live = h("p", { class: "visually-hidden", role: "status", "aria-live": "polite" });
let liveTimer;
function say(msg) {
  live.textContent = "";
  clearTimeout(liveTimer);
  liveTimer = setTimeout(() => (live.textContent = msg), 50);
}

function svgIcon() {
  // Universal-access figure. Built with createElementNS because h() makes HTML elements.
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  for (const [tag, attrs] of [
    ["circle", { cx: 12, cy: 12, r: 10.5 }],
    ["circle", { cx: 12, cy: 6.6, r: 1.6, class: "fill" }],
    ["path", { d: "M6.5 9.4 12 10.6l5.5-1.2M12 10.6v3.6m0 0-2.6 5m2.6-5 2.6 5" }],
  ]) {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    svg.append(el);
  }
  return svg;
}

function build() {
  const panelId = "a11y-panel";
  const sizeLabel = h("span", { class: "a11y-size-value" });
  const toggles = new Map();

  const panel = h("div", { id: panelId, class: "a11y-panel", role: "group", "aria-labelledby": "a11y-title", hidden: true },
    h("h2", { id: "a11y-title", class: "a11y-title", text: "תפריט נגישות" }),
    h("div", { class: "a11y-row", role: "group", "aria-label": "גודל טקסט" },
      h("span", { class: "a11y-row-label", "aria-hidden": "true", text: "גודל טקסט" }),
      h("button", { type: "button", class: "a11y-btn", "aria-label": "הקטנת טקסט", onclick: () => setText(settings.text - 1) }, "א-"),
      sizeLabel,
      h("button", { type: "button", class: "a11y-btn", "aria-label": "הגדלת טקסט", onclick: () => setText(settings.text + 1) }, "א+"),
    ),
    TOGGLES.map((t) => {
      const b = h("button", { type: "button", class: "a11y-btn a11y-toggle", "aria-pressed": "false", onclick: () => toggle(t) }, t.label);
      toggles.set(t.id, b);
      return b;
    }),
    h("button", { type: "button", class: "a11y-btn a11y-reset", onclick: reset }, "איפוס הגדרות"),
    h("a", { class: "a11y-link", href: "/accessibility/" }, "הצהרת נגישות"),
  );

  const fab = h("button", {
    type: "button", class: "a11y-fab", "aria-label": "תפריט נגישות", "aria-expanded": "false", "aria-controls": panelId,
    onclick: () => (panel.hidden ? open() : close(true)),
  }, svgIcon());

  const wrap = h("div", { class: "a11y-menu" }, panel, fab, live);

  function render() {
    sizeLabel.textContent = `${TEXT_STEPS[settings.text]}%`;
    for (const t of TOGGLES) toggles.get(t.id).setAttribute("aria-pressed", String(settings[t.id]));
  }
  function commit(msg) { apply(); save(settings); render(); say(msg); }
  function setText(i) {
    const next = Math.max(0, Math.min(TEXT_STEPS.length - 1, i));
    if (next === settings.text) return say(next === 0 ? "גודל הטקסט מינימלי" : "גודל הטקסט מקסימלי");
    settings = { ...settings, text: next };
    commit(`גודל טקסט ${TEXT_STEPS[next]}%`);
  }
  function toggle(t) {
    settings = { ...settings, [t.id]: !settings[t.id] };
    commit(`${t.label} ${settings[t.id] ? "פעיל" : "כבוי"}`);
  }
  function reset() {
    settings = { text: 0, contrast: false, motion: false, links: false };
    commit("ההגדרות אופסו");
  }
  function open() {
    panel.hidden = false;
    fab.setAttribute("aria-expanded", "true");
    panel.querySelector("button").focus();
  }
  function close(returnFocus) {
    if (panel.hidden) return;
    panel.hidden = true;
    fab.setAttribute("aria-expanded", "false");
    if (returnFocus) fab.focus();
  }

  wrap.addEventListener("keydown", (e) => { if (e.key === "Escape") close(true); });
  document.addEventListener("click", (e) => { if (!wrap.contains(e.target)) close(false); });
  // Closing when focus leaves keeps the panel from covering content a keyboard user tabs to.
  wrap.addEventListener("focusout", (e) => { if (e.relatedTarget && !wrap.contains(e.relatedTarget)) close(false); });

  render();
  document.body.append(wrap);
}

build();
