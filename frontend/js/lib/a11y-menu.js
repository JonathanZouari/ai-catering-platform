// Accessibility menu: text size, high contrast, stop animations, underlined links. Built in-house (no third-party
// widget). The choices are saved per visitor in localStorage and applied before first paint by js/a11y-boot.js,
// which reads the same key and class names. Every storage access is guarded: when storage is blocked the
// menu still works for the current page.
import { h } from "./dom.js";

const KEY = "yumm.a11y.v1";
const SIZES = [100, 125, 150]; // percent of the base font size; index is stored as `size`
const DEFAULTS = { size: 0, contrast: false, motion: false, links: false };

const TOGGLES = [
  ["contrast", "ניגודיות גבוהה", "a11y-contrast"],
  ["motion", "עצירת אנימציות", "a11y-no-motion"],
  ["links", "הדגשת קישורים", "a11y-links"],
];

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY));
    if (!saved || typeof saved !== "object") return { ...DEFAULTS };
    return {
      size: saved.size === 1 || saved.size === 2 ? saved.size : 0,
      contrast: saved.contrast === true,
      motion: saved.motion === true,
      links: saved.links === true,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

function save(settings) {
  try {
    const isDefault = JSON.stringify(settings) === JSON.stringify(DEFAULTS);
    if (isDefault) localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, JSON.stringify(settings));
  } catch {
    // Storage blocked: the setting still applies until the page is closed.
  }
}

function apply(settings) {
  const root = document.documentElement;
  root.classList.toggle("a11y-size-1", settings.size === 1);
  root.classList.toggle("a11y-size-2", settings.size === 2);
  for (const [key, , cls] of TOGGLES) root.classList.toggle(cls, settings[key]);
}

/** Wires the "נגישות" button inside `wrap` (an element with data-a11y-menu) to a settings panel. */
export function mountA11yMenu(wrap = document.querySelector("[data-a11y-menu]")) {
  const toggle = wrap?.querySelector(".a11y-toggle");
  if (!toggle) return;

  let settings = load();
  apply(settings);

  const sizeValue = h("output", { class: "a11y-size-value", id: "a11y-size-value", "aria-live": "polite" });
  const smaller = h("button", { class: "btn btn-secondary", type: "button", onclick: () => setSize(settings.size - 1) }, "הקטנת טקסט");
  const larger = h("button", { class: "btn btn-secondary", type: "button", onclick: () => setSize(settings.size + 1) }, "הגדלת טקסט");

  const toggleButtons = new Map(TOGGLES.map(([key, label]) => {
    // The visible on/off word is aria-hidden: aria-pressed already tells screen readers the state, and the word
    // means the state is not shown by colour alone.
    const state = h("span", { class: "a11y-state", "aria-hidden": "true" });
    const btn = h("button", { class: "a11y-option", type: "button", "aria-pressed": "false", onclick: () => {
      settings = { ...settings, [key]: !settings[key] };
      commit();
    } }, h("span", { text: label }), state);
    return [key, { btn, state }];
  }));

  const reset = h("button", { class: "btn btn-ghost", type: "button", onclick: () => { settings = { ...DEFAULTS }; commit(); } }, "איפוס הגדרות");
  const close = h("button", { class: "btn btn-ghost", type: "button", onclick: () => setOpen(false, { returnFocus: true }) }, "סגירה");

  const panel = h("div", { class: "a11y-panel", id: "a11y-panel", role: "group", "aria-labelledby": "a11y-title", hidden: true },
    h("p", { class: "a11y-title", id: "a11y-title", text: "הגדרות נגישות" }),
    h("div", { class: "a11y-row" },
      h("span", { class: "a11y-label", id: "a11y-size-label", text: "גודל טקסט" }),
      h("div", { class: "a11y-size", role: "group", "aria-labelledby": "a11y-size-label" }, smaller, sizeValue, larger),
    ),
    [...toggleButtons.values()].map(({ btn }) => btn),
    h("p", { class: "a11y-note" }, "ההגדרות נשמרות בדפדפן הזה. ",
      h("a", { href: "/accessibility/", text: "הצהרת נגישות" })),
    h("div", { class: "a11y-actions" }, reset, close),
  );
  wrap.append(panel);

  function setSize(next) {
    const clamped = Math.min(SIZES.length - 1, Math.max(0, next));
    if (clamped === settings.size) return;
    settings = { ...settings, size: clamped };
    commit();
  }

  function commit() {
    apply(settings);
    save(settings);
    render();
  }

  function render() {
    sizeValue.textContent = `${SIZES[settings.size]}%`;
    // aria-disabled (not disabled) so a button the visitor is pressing never loses keyboard focus.
    smaller.setAttribute("aria-disabled", String(settings.size === 0));
    larger.setAttribute("aria-disabled", String(settings.size === SIZES.length - 1));
    for (const [key, { btn, state }] of toggleButtons) {
      btn.setAttribute("aria-pressed", String(settings[key]));
      state.textContent = settings[key] ? "פעיל" : "כבוי";
    }
  }

  function setOpen(open, { returnFocus = false } = {}) {
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    if (!open && returnFocus) toggle.focus();
  }

  toggle.addEventListener("click", () => setOpen(panel.hidden));
  wrap.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) {
      e.stopPropagation();
      setOpen(false, { returnFocus: true });
    }
  });
  document.addEventListener("click", (e) => {
    if (!panel.hidden && !wrap.contains(e.target)) setOpen(false);
  });

  render();
  toggle.setAttribute("aria-controls", "a11y-panel");
  document.documentElement.classList.add("a11y-ready"); // reveals the button; without scripts it stays hidden
}
