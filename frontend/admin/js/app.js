// Startup, staff authentication and the application shell.
import { createDataView } from "./data-view.js";
import { createStaffGate } from "./auth-gate.js";
import { clear, errorBlock, h, ident } from "./dom.js";
import { ROLE_LABELS, describeError, parseCloudConfig } from "./helpers.js";
import { focusSchemaCard, renderErdView, renderSchemaView } from "./schema-views.js";

const root = document.getElementById("app");

let client = null;
let gate = null;
let shell = null;

const wordmark = () => h("p", { class: "wordmark admin-wordmark" }, h("bdi", {}, "yumm", h("span", { class: "dot" }, "."), "ai"));

function card(...children) {
  return h("main", { class: "center-page" }, h("div", { class: "auth-card" }, wordmark(), children));
}

/* ---------- startup ---------- */

async function boot() {
  closeShell();
  clear(root).append(card(h("p", { role: "status" }, "בודק את חיבור הענן…")));
  let config;
  try {
    const response = await fetch("/api/cloud-config", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    config = parseCloudConfig(await response.json());
  } catch (error) {
    showSetupPending("unreachable", error.message);
    return;
  }
  if (!config.configured) {
    showSetupPending("unconfigured");
    return;
  }
  if (typeof window.supabase?.createClient !== "function") {
    showSetupPending("sdk");
    return;
  }

  client = window.supabase.createClient(config.url, config.publishableKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
  });
  gate = createStaffGate({
    client,
    ui: { closeShell, showApp, showChecking, showDenied, showLogin, showUnverified },
  });
  // Auth calls made directly inside this callback can deadlock the client's lock, so defer them.
  client.auth.onAuthStateChange((event, session) => {
    setTimeout(() => gate.handleAuthEvent(event, session), 0);
  });
  await gate.start();
}

async function signOut(button, errorArea) {
  button.disabled = true;
  clear(errorArea);
  const { error } = await gate.signOut();
  if (error) {
    button.disabled = false;
    errorArea.append(errorBlock({ message: "ההתנתקות נכשלה, והחשבון עדיין מחובר בדפדפן הזה.", detail: describeError(error).detail }));
  }
}

function closeShell() {
  shell?.destroy();
  shell = null;
}

/* ---------- screens without an application shell ---------- */

function showSetupPending(reason, detail) {
  const reasons = {
    unconfigured: "חיבור הענן עדיין לא הוגדר בשרת, ולכן אי אפשר להתחבר או לקרוא נתונים.",
    unreachable: "לא ניתן לקבל מהשרת את הגדרות החיבור לענן, ולכן אי אפשר להתחבר או לקרוא נתונים.",
    sdk: "ספריית החיבור לענן לא נטענה, ולכן אי אפשר להתחבר או לקרוא נתונים.",
  };
  clear(root).append(
    card(
      h("h1", {}, "הקמת הענן ממתינה"),
      h("p", {}, reasons[reason]),
      detail && ident(detail),
      reason === "unconfigured" && [
        h("p", { class: "muted" }, "לאחר הקמת הפרויקט יש להגדיר בשרת את שני המשתנים הבאים:"),
        ident("SUPABASE_URL"),
        ident("SUPABASE_PUBLISHABLE_KEY"),
      ],
      h(
        "div",
        { class: "stack" },
        h("button", { class: "btn btn-primary", type: "button", onclick: showOfflineExplorer }, "פתיחת סייר המבנה הלא מקוון"),
        h("button", { class: "btn btn-secondary", type: "button", onclick: boot }, "בדיקה חוזרת"),
      ),
      h("p", { class: "muted small" }, "הסייר מציג מבנה טבלאות מתוך קובץ סטטי בלבד. אין בו נתונים אמיתיים."),
    ),
  );
}

function showChecking() {
  clear(root).append(card(h("p", { role: "status" }, "בודק את הרשאות החשבון…")));
}

function showLogin({ message } = {}) {
  // Signing out reaches here twice, directly and through the auth event. Keep what was typed.
  if (!message && document.getElementById("login-email")) return;
  const errorArea = h("div", {}, message && h("div", { class: "notice notice-warning", role: "alert" }, message));
  const email = h("input", { id: "login-email", class: "input", type: "email", dir: "ltr", autocomplete: "username", required: true });
  const password = h("input", { id: "login-password", class: "input", type: "password", dir: "ltr", autocomplete: "current-password", required: true });
  const submit = h("button", { class: "btn btn-primary", type: "submit" }, "כניסה");

  async function onSubmit(event) {
    event.preventDefault();
    clear(errorArea);
    if (!email.value.trim() || !password.value) {
      errorArea.append(errorBlock({ message: "יש להזין דוא״ל וסיסמה." }));
      return;
    }
    submit.disabled = true;
    submit.textContent = "מתחבר…";
    const { error } = await client.auth.signInWithPassword({ email: email.value.trim(), password: password.value });
    if (error) {
      submit.disabled = false;
      submit.textContent = "כניסה";
      password.value = "";
      errorArea.append(errorBlock(describeError(error)));
      password.focus();
      return;
    }
    await gate.verify();
  }

  clear(root).append(
    card(
      h("h1", {}, "כניסת צוות"),
      h("p", { class: "muted" }, "ניהול נתוני העסק בענן. חשבונות צוות נפתחים בידי מנהל מורשה בלבד."),
      h(
        "form",
        { class: "stack", novalidate: true, onsubmit: onSubmit },
        h("div", { class: "field" }, h("label", { for: "login-email" }, "דוא״ל"), email),
        h("div", { class: "field" }, h("label", { for: "login-password" }, "סיסמה"), password),
        errorArea,
        submit,
      ),
    ),
  );
  email.focus();
}

function showDenied(user) {
  const errorArea = h("div", {});
  const button = h("button", { class: "btn btn-secondary", type: "button", onclick: () => signOut(button, errorArea) }, "התנתקות");
  clear(root).append(
    card(
      h("h1", {}, "אין הרשאת צוות"),
      h("p", {}, "ההתחברות הצליחה, אבל לחשבון הזה אין תפקיד ניהול. לא נטענו נתונים."),
      user?.email && ident(user.email),
      h("p", { class: "muted" }, "הרשאה ניתנת בידי מנהל מורשה בצד השרת, ואי אפשר להפעיל אותה מהמסך הזה."),
      errorArea,
      button,
    ),
  );
}

function showUnverified(error) {
  const errorArea = h("div", {});
  const button = h("button", { class: "btn btn-secondary", type: "button", onclick: () => signOut(button, errorArea) }, "התנתקות");
  clear(root).append(
    card(
      h("h1", {}, "לא ניתן לאמת את החשבון"),
      errorBlock(describeError(error), { onRetry: () => gate.verify() }),
      h("p", { class: "muted" }, "הנתונים נשארים נעולים עד שהשרת מאשר את ההרשאה."),
      errorArea,
      button,
    ),
  );
}

/* ---------- application shell ---------- */

function buildShell({ tabs, banner, account }) {
  const panels = new Map();
  const buttons = new Map();
  const nav = h("div", { class: "view-tabs", role: "tablist", "aria-label": "תצוגות" });
  const body = h("main", { class: "shell-main" });
  let erd = null;
  let active = null;

  function activate(id) {
    active = id;
    for (const [tabId, panel] of panels) {
      panel.hidden = tabId !== id;
      buttons.get(tabId).setAttribute("aria-selected", String(tabId === id));
      buttons.get(tabId).tabIndex = tabId === id ? 0 : -1;
    }
    const tab = tabs.find((item) => item.id === id);
    if (!tab.rendered) {
      tab.rendered = true;
      const result = tab.render(panels.get(id));
      if (id === "erd") erd = result;
    }
    if (id === "erd") erd?.refreshLayout();
  }

  tabs.forEach((tab, index) => {
    const panel = h("div", { id: `panel-${tab.id}`, role: "tabpanel", "aria-labelledby": `tab-${tab.id}`, hidden: true });
    const button = h("button", {
      id: `tab-${tab.id}`,
      type: "button",
      role: "tab",
      class: "view-tab",
      "aria-controls": `panel-${tab.id}`,
      onclick: () => activate(tab.id),
      onkeydown: (event) => {
        // In RTL the visually next tab is to the left.
        const step = { ArrowLeft: 1, ArrowRight: -1 }[event.key];
        if (!step) return;
        event.preventDefault();
        const next = tabs[(index + step + tabs.length) % tabs.length];
        activate(next.id);
        buttons.get(next.id).focus();
      },
    }, tab.label);
    panels.set(tab.id, panel);
    buttons.set(tab.id, button);
    nav.append(button);
    body.append(panel);
  });

  const onResize = () => {
    if (active === "erd") erd?.refreshLayout();
  };
  window.addEventListener("resize", onResize);

  clear(root).append(
    h("header", { class: "shell-head" }, h("div", { class: "shell-brand" }, wordmark(), h("p", { class: "shell-name" }, "ניהול העסק")), nav, account),
    banner,
    body,
  );
  activate(tabs[0].id);

  return {
    activate,
    destroy: () => window.removeEventListener("resize", onResize),
  };
}

function schemaTabs(activate) {
  return [
    { id: "schema", label: "מבנה הטבלאות", render: (panel) => renderSchemaView(panel) },
    {
      id: "erd",
      label: "תרשים קשרים",
      render: (panel) => renderErdView(panel, {
        onOpenTable: (name) => {
          activate("schema");
          focusSchemaCard(name);
        },
      }),
    },
  ];
}

function showOfflineExplorer() {
  closeShell();
  let view = null;
  const banner = h(
    "div",
    { class: "offline-banner", role: "status" },
    h("strong", {}, "מצב לא מקוון"),
    h("span", {}, "מבנה בלבד מתוך קובץ סטטי. אין כאן חיבור לענן, נתונים אמיתיים או אפשרות לשמור."),
  );
  const account = h("div", { class: "shell-account" }, h("button", { class: "btn btn-secondary", type: "button", onclick: boot }, "בדיקת החיבור"));
  view = buildShell({ tabs: schemaTabs((id) => view.activate(id)), banner, account });
  shell = view;
}

function showApp(user, role) {
  let view = null;
  let dataView = null;
  const errorArea = h("div", { class: "shell-error" });
  const signOutButton = h("button", { class: "btn btn-secondary", type: "button", onclick: () => signOut(signOutButton, errorArea) }, "התנתקות");
  const account = h(
    "div",
    { class: "shell-account" },
    h("div", { class: "account-info" }, h("span", { class: "badge badge-green" }, ROLE_LABELS[role]), user.email && ident(user.email)),
    signOutButton,
  );
  view = buildShell({
    tabs: [
      {
        id: "data",
        label: "נתונים",
        render: (panel) => {
          dataView = createDataView({
            client,
            container: panel,
            onSessionLost: () => gate.verify(),
          });
        },
      },
      ...schemaTabs((id) => view.activate(id)),
    ],
    banner: errorArea,
    account,
  });
  shell = {
    destroy() {
      dataView?.destroy();
      view.destroy();
    },
  };
}

boot();
