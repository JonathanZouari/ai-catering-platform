// Accessibility center: a fixed button on every page that opens a panel of display settings.
// Classic script loaded in <head> so saved settings apply before the first paint. Settings live in
// this browser only (localStorage) and are applied as classes on <html>; css/a11y-center.css styles them.
(() => {
  const KEY = "catering.a11y.v1";
  const TOGGLES = [
    ["contrast", "ניגודיות גבוהה"],
    ["links", "הדגשת קישורים וכפתורים"],
    ["readable", "גופן קריא"],
    ["spacing", "ריווח טקסט מוגדל"],
    ["focus", "סימון בולט של מיקוד המקלדת"],
    ["still", "עצירת אנימציות"],
  ];
  const SIZES = [["", "רגיל"], ["lg", "גדול"], ["xl", "גדול מאוד"]];
  const html = document.documentElement;

  let state = {};
  try {
    state = JSON.parse(localStorage.getItem(KEY)) ?? {};
  } catch {
    state = {};
  }

  function apply() {
    for (const [key] of TOGGLES) html.classList.toggle(`a11y-${key}`, Boolean(state[key]));
    for (const [size] of SIZES) if (size) html.classList.toggle(`a11y-text-${size}`, state.size === size);
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      /* storage blocked: settings last for this page only */
    }
  }
  apply();

  function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "text") node.textContent = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    }
    node.append(...children);
    return node;
  }

  function build() {
    const panelId = "a11y-panel";
    const button = el("button", {
      type: "button", class: "a11y-fab", id: "a11y-fab", "aria-expanded": "false", "aria-controls": panelId,
    }, el("span", { class: "a11y-fab-icon", "aria-hidden": "true" }), el("span", { class: "a11y-fab-label", text: "נגישות" }));

    const toggles = TOGGLES.map(([key, label]) => {
      const input = el("input", { type: "checkbox", id: `a11y-${key}` });
      input.checked = Boolean(state[key]);
      input.addEventListener("change", () => {
        state[key] = input.checked;
        apply();
      });
      return el("label", { class: "a11y-option", for: `a11y-${key}` }, input, el("span", { text: label }));
    });

    const sizes = SIZES.map(([size, label]) => {
      const input = el("input", { type: "radio", name: "a11y-size", id: `a11y-size-${size || "md"}` });
      input.checked = (state.size ?? "") === size;
      input.addEventListener("change", () => {
        state.size = size;
        apply();
      });
      return el("label", { class: "a11y-option", for: `a11y-size-${size || "md"}` }, input, el("span", { text: label }));
    });

    const reset = el("button", { type: "button", class: "a11y-reset", text: "איפוס ההגדרות" });
    reset.addEventListener("click", () => {
      state = {};
      apply();
      for (const input of panel.querySelectorAll("input")) input.checked = input.id === "a11y-size-md";
      reset.focus();
    });

    const close = el("button", { type: "button", class: "a11y-close", "aria-label": "סגירת מרכז הנגישות", text: "×" });
    const panel = el("section", { id: panelId, class: "a11y-panel", "aria-labelledby": "a11y-title", hidden: "" },
      el("div", { class: "a11y-head" }, el("h2", { id: "a11y-title", text: "מרכז נגישות" }), close),
      el("fieldset", { class: "a11y-group" }, el("legend", { text: "גודל טקסט" }), ...sizes),
      el("fieldset", { class: "a11y-group" }, el("legend", { text: "תצוגה" }), ...toggles),
      el("div", { class: "a11y-foot" }, reset, el("a", { href: "/accessibility/", text: "הצהרת נגישות" })));

    const setOpen = (open) => {
      panel.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
      if (open) panel.querySelector("input:checked, input")?.focus();
    };
    button.addEventListener("click", () => setOpen(panel.hidden));
    close.addEventListener("click", () => {
      setOpen(false);
      button.focus();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !panel.hidden) {
        setOpen(false);
        button.focus();
      }
    });
    document.addEventListener("pointerdown", (e) => {
      if (!panel.hidden && !panel.contains(e.target) && !button.contains(e.target)) setOpen(false);
    });

    const root = el("div", { class: "a11y-center" }, button, panel);
    document.body.append(root);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
