// Shared owner-screen plumbing: token login, authed API calls, toast, two-step delete.
// Each admin page has #login, #toast and one content element, and calls startAdmin().
import { api } from "/js/api.js";

const TOKEN_KEY = "yummai_admin_token";
const ERRORS = {
  validation_error: "יש שדות חסרים או לא תקינים",
  not_found: "הפריט לא נמצא (אולי נמחק)",
  database_unavailable: "בסיס הנתונים לא מוגדר בשרת",
};

export const $ = (id) => document.getElementById(id);

function readToken() {
  try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
}
function writeToken(value) {
  try { value ? sessionStorage.setItem(TOKEN_KEY, value) : sessionStorage.removeItem(TOKEN_KEY); } catch { /* private mode: token lives for this page only */ }
}
let token = readToken();
let page = { content: null, load: async () => {}, errors: {} };

export function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

let toastTimer;
export function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
}
export const explain = (err) => page.errors[err.code] ?? ERRORS[err.code] ?? "משהו השתבש, נסו שוב";

function showLogin() {
  token = null;
  writeToken(null);
  $(page.content).hidden = true;
  $("login").hidden = false;
  $("token").focus();
}

export async function call(path, options = {}) {
  try {
    return await api(path, { ...options, headers: { Authorization: `Bearer ${token}` } });
  } catch (err) {
    if (err.status === 401) showLogin();
    throw err;
  }
}

async function reload() {
  await page.load();
  $("login").hidden = true;
  $(page.content).hidden = false;
}

// Runs a change, reloads the page data, and reports. Returns true on success.
export async function mutate(request, done) {
  try {
    await request();
    await reload();
    toast(done);
    return true;
  } catch (err) {
    if (err.status !== 401) toast(explain(err));
    return false;
  }
}

// Two-step delete instead of a blocking confirm() dialog.
export function confirmThen(button, action) {
  if (button.dataset.armed) { delete button.dataset.armed; action(); return; }
  const label = button.textContent;
  button.dataset.armed = "1";
  button.textContent = "ללחוץ שוב למחיקה";
  setTimeout(() => { delete button.dataset.armed; button.textContent = label; }, 4000);
}

// content: id of the element shown after login; load: fetches and renders the page data;
// errors: page-specific messages by error code.
export function startAdmin({ content, load, errors = {} }) {
  page = { content, load, errors };
  $("login").addEventListener("submit", (e) => {
    e.preventDefault();
    token = $("token").value.trim();
    writeToken(token);
    $("token").value = "";
    reload().catch((err) => toast(err.status === 401 ? "קוד שגוי" : explain(err)));
  });
  token ? reload().catch((err) => { if (err.status !== 401) toast(explain(err)); }) : showLogin();
}
