// Customer account page: sign up, sign in, password reset, profile photo, order history and files.
// Auth talks to Supabase Auth REST directly (like the owner login); the token is stored under the
// customer's own key. All DOM is built with h() (textContent); server data is never parsed as HTML.
import { customerApi as api, customerAuth } from "/js/api.js";
import { h } from "/js/dom.js";
import { S, DIR, LANGS } from "./i18n.js";

const $ = (id) => document.getElementById(id);
const app = $("app");
const prefLang = () => { try { return localStorage.getItem("lang"); } catch { return null; } };
let lang = S[prefLang()] ? prefLang() : "he";
const t = () => S[lang];
let config = null;

function say(text, kind = "ok") {
  const m = $("message");
  m.className = kind;
  m.textContent = text;
}

// ---- Supabase Auth REST
async function authCall(path, body, { method = "POST", token = null } = {}) {
  config ??= await api("/api/public-config", { auth: false });
  const { supabase_url: url, supabase_anon_key: key } = config;
  if (!url || !key) throw new Error(t().authNotSet);
  const response = await fetch(`${url}/auth/v1/${path}`, {
    method,
    headers: { "Content-Type": "application/json", apikey: key, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error("auth");
  return data;
}
const redirect = () => encodeURIComponent(`${location.origin}/customer/account.html`);

// Password-reset links land here with the session in the URL fragment (#access_token=...&type=recovery).
function recoveryToken() {
  const params = new URLSearchParams(location.hash.slice(1));
  if (params.get("type") !== "recovery") return null;
  history.replaceState(null, "", location.pathname); // do not leave the token in the address bar
  return params.get("access_token");
}

async function run(fn) {
  say("");
  try { await fn(); } catch (e) { say(e.message === "auth" ? t().loginFail : e.message, "error"); }
}

const field = (label, type, props = {}) => {
  const input = h("input", { type, required: true, dir: type === "text" ? null : "ltr", ...props });
  return [h("label", {}, label, input), input];
};

// ---- screens
function loginScreen(mode = "login") {
  const [emailL, email] = field(t().email, "email", { autocomplete: "username" });
  const [passL, password] = field(t().password, "password", { autocomplete: mode === "login" ? "current-password" : "new-password", minlength: mode === "signup" ? "8" : null });
  const [nameL, name] = field(t().fullName, "text", { autocomplete: "name", maxlength: "200" });
  const switchTo = (m) => h("button", { type: "button", class: "link", onclick: () => loginScreen(m) });
  const toggle = switchTo(mode === "login" ? "signup" : "login");
  toggle.textContent = mode === "login" ? t().noAccount : t().haveAccount;
  const forgot = h("button", { type: "button", class: "link", onclick: () => resetScreen() }, t().forgot);
  const form = h("form", { class: "ep-card ep-form", onsubmit: (ev) => {
    ev.preventDefault();
    run(async () => {
      if (mode === "login") {
        const body = await authCall("token?grant_type=password", { email: email.value, password: password.value });
        customerAuth.set(body.access_token);
        return accountScreen();
      }
      try {
        await authCall("signup", { email: email.value, password: password.value, data: { full_name: name.value } });
      } catch { throw new Error(t().signupFail); }
      say(t().signupDone);
      loginScreen("login");
    });
  } },
  h("h2", {}, mode === "login" ? t().login : t().signup),
  mode === "signup" && nameL, emailL, passL,
  mode === "signup" && h("p", { class: "hint" }, t().passwordHint),
  h("button", { class: "primary", type: "submit" }, mode === "login" ? t().login : t().signup),
  h("div", {}, toggle, mode === "login" && forgot));
  app.replaceChildren(form);
}

function resetScreen() {
  const [emailL, email] = field(t().email, "email", { autocomplete: "username" });
  app.replaceChildren(h("form", { class: "ep-card ep-form", onsubmit: (ev) => {
    ev.preventDefault();
    // Same answer whether or not the email exists, so accounts cannot be probed.
    run(async () => { await authCall(`recover?redirect_to=${redirect()}`, { email: email.value }).catch(() => {}); say(t().resetDone); });
  } }, h("h2", {}, t().forgot), emailL,
  h("button", { class: "primary", type: "submit" }, t().resetSend),
  h("button", { type: "button", class: "link", onclick: () => loginScreen() }, t().backToLogin)));
}

function newPasswordScreen(token) {
  const [passL, password] = field(t().newPassword, "password", { autocomplete: "new-password", minlength: "8" });
  app.replaceChildren(h("form", { class: "ep-card ep-form", onsubmit: (ev) => {
    ev.preventDefault();
    run(async () => {
      try { await authCall("user", { password: password.value }, { method: "PUT", token }); } catch { throw new Error(t().passwordFail); }
      say(t().passwordDone);
      loginScreen();
    });
  } }, h("h2", {}, t().newPassword), passL, h("p", { class: "hint" }, t().passwordHint),
  h("button", { class: "primary", type: "submit" }, t().setPassword)));
}

const money = (v, cur) => new Intl.NumberFormat({ he: "he-IL", ar: "ar-IL-u-nu-latn", en: "en-IL" }[lang], { style: "currency", currency: cur }).format(Number(v));

async function filesPanel(order) {
  const box = h("div", { class: "files" });
  const input = h("input", { type: "file", accept: "image/jpeg,image/png,image/webp,application/pdf" });
  const render = async () => {
    const files = await api(`/api/orders/${order.id}/files`, { auth: true });
    box.replaceChildren(...(files.length ? files : [null]).map((f) => f
      ? h("div", { class: "file-row" },
        h("a", { href: f.url, target: "_blank", rel: "noopener noreferrer" }, f.original_name),
        h("button", { type: "button", class: "link", onclick: () => run(async () => { await api(`/api/orders/${order.id}/files/${f.id}`, { method: "DELETE" }); await render(); }) }, t().fileDelete))
      : h("p", { class: "hint" }, t().noFiles)));
  };
  const upload = h("button", { type: "button", onclick: () => run(async () => {
    if (!input.files[0]) return;
    const data = new FormData();
    data.append("file", input.files[0]);
    try { await api(`/api/orders/${order.id}/files`, { method: "POST", body: data }); } catch (e) { throw new Error(`${t().uploadFail} ${e.message}`); }
    input.value = "";
    await render();
  }) }, t().fileUpload);
  await render();
  return h("details", { class: "order-files" }, h("summary", {}, t().files), h("p", { class: "hint" }, t().filesHint), box, input, upload);
}

async function accountScreen() {
  const [me, orders] = await Promise.all([api("/api/me"), api("/api/me/orders")]).catch((e) => {
    if (e.status === 401) { loginScreen(); return []; }
    throw e;
  });
  if (!me) return;
  const [nameL, name] = field(t().fullName, "text", { value: me.full_name, maxlength: "200" });
  const phone = h("input", { type: "tel", value: me.phone ?? "", maxlength: "50", dir: "ltr" });
  const photo = h("input", { type: "file", accept: "image/jpeg,image/png,image/webp" });
  const avatar = me.avatar_url ? h("img", { class: "avatar", alt: "", src: me.avatar_url, width: "96", height: "96" }) : null;
  const profile = h("form", { class: "ep-card ep-form", onsubmit: (ev) => {
    ev.preventDefault();
    run(async () => {
      const body = { full_name: name.value };
      if (phone.value.trim()) body.phone = phone.value.trim();
      await api("/api/me", { method: "PATCH", body: JSON.stringify(body) });
      say(t().saved);
    });
  } }, h("h2", {}, t().profile), h("p", { dir: "ltr" }, me.email), nameL, h("label", {}, t().phone, phone),
  h("button", { class: "primary", type: "submit" }, t().save));
  const photoCard = h("div", { class: "ep-card" }, h("h3", {}, t().avatar), avatar, photo,
    h("button", { type: "button", onclick: () => run(async () => {
      if (!photo.files[0]) return;
      const data = new FormData();
      data.append("file", photo.files[0]);
      try { await api("/api/me/avatar", { method: "POST", body: data }); } catch (e) { throw new Error(`${t().uploadFail} ${e.message}`); }
      await accountScreen();
    }) }, t().avatarUpload),
    me.avatar_url && h("button", { type: "button", class: "link", onclick: () => run(async () => { await api("/api/me/avatar", { method: "DELETE" }); await accountScreen(); }) }, t().avatarRemove));
  const list = await Promise.all(orders.map(async (o) => h("li", { class: "ep-card order-row" },
    h("div", {}, h("strong", {}, `${t().orderDate}: ${o.event_date}`), " · ", t().stageSub[o.status] ?? o.status),
    o.total != null && h("div", {}, `${t().orderTotal}: ${money(o.total, o.currency)}`),
    await filesPanel(o))));
  app.replaceChildren(profile, photoCard,
    h("section", {}, h("h2", {}, t().myOrders), orders.length ? h("ul", { class: "order-list" }, list) : h("p", {}, t().noOrders),
      h("a", { class: "primary-link", href: "/customer/" }, t().newOrder)),
    h("button", { type: "button", onclick: () => { customerAuth.clear(); loginScreen(); } }, t().logout));
}

// ---- boot
function chrome() {
  document.documentElement.lang = lang;
  document.documentElement.dir = DIR[lang];
  $("langs").replaceChildren(h("div", { class: "pills", role: "group", "aria-label": t().lang },
    Object.entries(LANGS).map(([code, label]) => h("button", { type: "button", "aria-pressed": String(code === lang), onclick: () => {
      lang = code;
      try { localStorage.setItem("lang", code); } catch { /* ignore */ }
      boot();
    } }, label))));
}

async function boot() {
  chrome();
  say("");
  const recovery = recoveryToken();
  if (recovery) return newPasswordScreen(recovery);
  if (customerAuth.get()) return run(accountScreen);
  loginScreen();
}
boot();
