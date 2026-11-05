import { getConfig, isLoggedIn, login, logout, adminApi } from "/js/admin/auth.js";
import { renderAvailability, renderDelivery } from "/js/admin/logistics.js";
import { renderMenu } from "/js/admin/menu.js";
import { renderOrders } from "/js/admin/orders.js";
import { renderProfile } from "/js/admin/profile.js";
import { renderQuantities } from "/js/admin/quantities.js";
import { watchOrders } from "/js/admin/realtime.js";
import { api } from "/js/api.js";
import { attempt, field, h } from "/js/ui.js";

const SCREENS = {
  orders: ["הזמנות", "receipt_long", renderOrders],
  menu: ["תפריט", "restaurant_menu", renderMenu],
  availability: ["זמינות", "event_available", renderAvailability],
  delivery: ["משלוחים", "local_shipping", renderDelivery],
  quantities: ["כמויות", "calculate", renderQuantities],
  profile: ["פרופיל העסק", "storefront", renderProfile],
};

const app = document.getElementById("app");
const icon = (name) => h("span", { className: `icon icon-${name}`, "aria-hidden": "true" });

// Before login the page knows only the site's caterer, from the public API.
async function siteBrand() {
  try {
    const { site_caterer: slug } = await getConfig();
    return slug ? await api(`/api/c/${slug}`) : null;
  } catch {
    return null;
  }
}

function logoFor(caterer, storageUrl) {
  const src = caterer?.logo_path && storageUrl ? `${storageUrl}/${caterer.logo_path}` : "/img/brand/logo.jpg";
  return h("img", { className: "admin-logo", src, alt: "" });
}

async function renderLogin() {
  const email = h("input", { type: "email", required: true, autocomplete: "username", dir: "ltr" });
  const password = h("input", { type: "password", required: true, autocomplete: "current-password", dir: "ltr" });
  const submit = h("button", { type: "submit" }, icon("login"), "כניסה");
  const [brand, config] = await Promise.all([siteBrand(), getConfig().catch(() => ({}))]);
  app.replaceChildren(h("main", { className: "login-page" },
    h("form", {
      className: "card login",
      onsubmit: async (event) => {
        event.preventDefault();
        submit.disabled = true;
        const ok = await attempt(() => login(email.value, password.value));
        submit.disabled = false;
        if (ok) start();
      },
    },
    h("div", { className: "login-brand" },
      logoFor(brand, config.storage_public_url),
      h("p", { className: "eyebrow" }, "אזור ניהול"),
      h("h1", {}, brand ? `ניהול ${brand.name}` : "כניסה לניהול העסק"),
      h("p", { className: "muted" }, "הזמנות, תפריט, זמינות ופרופיל העסק במקום אחד.")),
    field("אימייל", email),
    field("סיסמה", password),
    submit,
    h("a", { className: "back-to-site", href: "/" }, icon("arrow_back"), "חזרה לאתר"))));
  email.focus();
}

function renderShell(profile, storageUrl) {
  const view = h("main", { id: "view", tabIndex: -1 });
  const links = Object.entries(SCREENS).map(([key, [label, iconName]]) => h("a", { href: `#${key}`, id: `nav-${key}`, className: "nav-item" },
    icon(iconName), h("span", {}, label), key === "orders" ? h("span", { className: "nav-count", hidden: true }) : null));
  app.replaceChildren(
    h("div", { className: "admin" },
      h("aside", { className: "sidebar" },
        h("div", { className: "sidebar-brand" },
          logoFor(profile, storageUrl),
          h("div", {},
            h("strong", {}, profile?.name ?? "ניהול העסק"),
            profile?.kashrut_status ? h("small", {}, icon("verified"), profile.kashrut_status) : null)),
        h("nav", { className: "topbar", "aria-label": "ניווט ראשי" }, links),
        h("div", { className: "sidebar-foot" },
          h("a", { className: "button secondary", href: "/", target: "_blank", rel: "noopener" }, icon("home"), "צפייה באתר"),
          h("button", { type: "button", className: "secondary", onclick: logout }, icon("logout"), "יציאה"))),
      view),
    h("p", { id: "live-status", className: "visually-hidden", role: "status" }),
  );
  return view;
}

async function updatePendingCount() {
  const badge = document.querySelector(".nav-count");
  if (!badge) return;
  try {
    const pending = await adminApi("/api/admin/orders?status=pending_approval");
    badge.textContent = String(pending.length);
    badge.hidden = pending.length === 0;
    badge.setAttribute("aria-label", `${pending.length} ממתינות לאישור`);
  } catch {
    badge.hidden = true;
  }
}

async function show(view) {
  const key = SCREENS[location.hash.slice(1)] ? location.hash.slice(1) : "orders";
  document.querySelectorAll(".topbar a").forEach((link) => {
    if (link.id === `nav-${key}`) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  document.title = `${SCREENS[key][0]} | ניהול העסק`;
  view.dataset.screen = key;
  view.replaceChildren(h("div", { className: "loading", role: "status" }, h("span", { className: "spinner", "aria-hidden": "true" }), "טוען…"));
  await attempt(() => SCREENS[key][2](view));
  view.focus({ preventScroll: true });
  updatePendingCount();
}

async function start() {
  const [profile, config] = await Promise.all([
    adminApi("/api/admin/profile").catch(() => null),
    getConfig().catch(() => ({})),
  ]);
  const view = renderShell(profile, config.storage_public_url);
  window.onhashchange = () => show(view);
  show(view);
  watchOrders(() => {
    clearTimeout(liveRefresh);
    liveRefresh = setTimeout(() => refreshLive(view), 300);
  });
}

let liveRefresh;

// A new or changed order: update the counter, and the list if it's on screen and idle.
async function refreshLive(view) {
  updatePendingCount();
  if (view.dataset.screen !== "orders" || document.querySelector("dialog[open]")) return;
  await attempt(() => renderOrders(view));
  const live = document.getElementById("live-status");
  if (live) live.textContent = "רשימת ההזמנות עודכנה";
}

if (isLoggedIn()) start();
else renderLogin();
