// Accessibility toolbar: text size, high contrast, link to the accessibility statement.
const KEY = "a11y";
const SIZES = [100, 115, 130, 150];
let prefs = { size: 0, hc: false };
try { prefs = { ...prefs, ...JSON.parse(localStorage.getItem(KEY)) }; } catch { /* storage may be blocked */ }

function apply() {
  const root = document.documentElement;
  root.style.fontSize = `${SIZES[prefs.size] ?? 100}%`;
  root.classList.toggle("a11y-hc", prefs.hc);
  try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch { /* ignore */ }
}

function button(label, onClick) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = label;
  b.addEventListener("click", onClick);
  return b;
}

function mount() {
  const wrap = document.createElement("div");
  wrap.className = "a11y";
  const panel = document.createElement("div");
  panel.className = "a11y-panel";
  panel.id = "a11y-panel";
  panel.hidden = true;
  panel.setAttribute("role", "group");
  panel.setAttribute("aria-label", "הגדרות נגישות");

  const hc = button("ניגודיות גבוהה", () => { prefs.hc = !prefs.hc; hc.setAttribute("aria-pressed", prefs.hc); apply(); });
  hc.setAttribute("aria-pressed", prefs.hc);
  const bigger = button("הגדלת טקסט", () => { prefs.size = Math.min(prefs.size + 1, SIZES.length - 1); apply(); });
  const smaller = button("הקטנת טקסט", () => { prefs.size = Math.max(prefs.size - 1, 0); apply(); });
  const reset = button("איפוס", () => { prefs = { size: 0, hc: false }; hc.setAttribute("aria-pressed", "false"); apply(); });
  const statement = document.createElement("a");
  statement.href = "/accessibility/";
  statement.textContent = "הצהרת נגישות";
  panel.append(bigger, smaller, hc, reset, statement);

  const toggle = button("נגישות", () => {
    panel.hidden = !panel.hidden;
    toggle.setAttribute("aria-expanded", String(!panel.hidden));
  });
  toggle.className = "a11y-toggle";
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-controls", "a11y-panel");
  wrap.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) { panel.hidden = true; toggle.setAttribute("aria-expanded", "false"); toggle.focus(); }
  });
  wrap.append(panel, toggle);
  document.body.append(wrap);
}

apply();
mount();
