import { isLoggedIn, login, logout } from "/js/admin/auth.js";
import { renderAvailability, renderDelivery } from "/js/admin/logistics.js";
import { renderMenu } from "/js/admin/menu.js";
import { renderOrders } from "/js/admin/orders.js";
import { renderProfile } from "/js/admin/profile.js";
import { renderQuantities } from "/js/admin/quantities.js";
import { attempt, field, h } from "/js/ui.js";

const SCREENS = {
  orders: ["הזמנות", renderOrders],
  menu: ["תפריט", renderMenu],
  availability: ["זמינות", renderAvailability],
  delivery: ["משלוחים", renderDelivery],
  quantities: ["כמויות", renderQuantities],
  profile: ["פרופיל העסק", renderProfile],
};

const app = document.getElementById("app");
const yummaiLabel = () => h("img", { className: "yummai-label", src: "/img/yummai-logo.svg", alt: "Yummai" });

function renderLogin() {
  const email = h("input", { type: "email", required: true, autocomplete: "username", dir: "ltr" });
  const password = h("input", {
    type: "password", required: true, autocomplete: "current-password", dir: "ltr",
  });
  app.replaceChildren(h("form", {
    className: "card login",
    onsubmit: async (event) => {
      event.preventDefault();
      if (await attempt(() => login(email.value, password.value))) start();
    },
  },
  yummaiLabel(),
  h("h1", {}, "כניסה לניהול העסק"),
  field("אימייל", email),
  field("סיסמה", password),
  h("button", { type: "submit" }, "כניסה")));
}

function renderShell() {
  const view = h("main", { id: "view", tabIndex: -1 });
  const links = Object.entries(SCREENS).map(([key, [label]]) => h("a", { href: `#${key}`, id: `nav-${key}` }, label));
  app.replaceChildren(
    h("nav", { className: "topbar", "aria-label": "ניווט ראשי" },
      yummaiLabel(),
      links,
      h("button", { className: "secondary", onclick: logout }, "יציאה")),
    view,
  );
  return view;
}

async function show(view) {
  const key = SCREENS[location.hash.slice(1)] ? location.hash.slice(1) : "orders";
  document.querySelectorAll(".topbar a").forEach((link) => {
    if (link.id === `nav-${key}`) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  await attempt(() => SCREENS[key][1](view));
}

function start() {
  const view = renderShell();
  window.onhashchange = () => show(view);
  show(view);
}

if (isLoggedIn()) start();
else renderLogin();
