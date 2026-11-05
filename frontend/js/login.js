import {
  authErrorMessage,
  getAccessToken,
  onAuthChange,
  sendPasswordReset,
  signIn,
  signUp,
  updatePassword,
} from "/js/auth.js";
import { api } from "/js/api.js";

const TITLES = {
  login: "ברוכים השבים",
  signup: "יצירת חשבון",
  forgot: "איפוס סיסמה",
  reset: "בחירת סיסמה חדשה",
};

const params = new URLSearchParams(location.search);
const title = document.getElementById("auth-title");
const msg = document.querySelector("[data-msg]");
const tabs = document.querySelectorAll("[data-tabs] [role=tab]");
let resetting = params.get("mode") === "reset";

function showMessage(text, kind = "error") {
  msg.textContent = text;
  msg.dataset.kind = kind;
  msg.hidden = !text;
}

function setMode(mode) {
  document.querySelectorAll("[data-form]").forEach((f) => (f.hidden = f.dataset.form !== mode));
  tabs.forEach((t) => {
    const on = t.dataset.mode === mode;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
  });
  document.querySelector("[data-tabs]").hidden = mode === "reset";
  title.textContent = TITLES[mode];
  showMessage("");
  document.querySelector(`[data-form="${mode}"] input`)?.focus();
}

// Only same-site paths; never redirect to another origin.
function nextPath(role) {
  const next = params.get("next");
  if (next && next.startsWith("/") && !next.startsWith("//")) return next;
  return role === "admin" ? "/admin/" : "/customer/";
}

async function goNext() {
  const me = await api("/api/me");
  location.replace(nextPath(me.role));
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-mode]");
  if (btn) setMode(btn.dataset.mode);
});

// Arrow-key navigation between tabs.
document.querySelector("[data-tabs]").addEventListener("keydown", (e) => {
  if (!["ArrowLeft", "ArrowRight"].includes(e.key)) return;
  const list = [...tabs];
  const i = list.indexOf(document.activeElement);
  const next = list[(i + 1) % list.length];
  next.focus();
  setMode(next.dataset.mode);
});

async function withBusy(form, fn) {
  const btn = form.querySelector(".auth-submit");
  btn.disabled = true;
  btn.setAttribute("aria-busy", "true");
  try {
    await fn();
  } catch (err) {
    showMessage(authErrorMessage(err));
  } finally {
    btn.disabled = false;
    btn.removeAttribute("aria-busy");
  }
}

function invalid(form) {
  if (form.checkValidity()) return false;
  const bad = form.querySelector(":invalid");
  const label = bad.closest(".field")?.querySelector("span")?.firstChild?.textContent?.trim();
  showMessage(bad.validity.tooShort ? "הסיסמה צריכה לכלול לפחות 8 תווים." : `נא למלא ${label} תקין.`);
  bad.focus();
  return true;
}

const handlers = {
  async login(form, data) {
    await signIn(data.get("email").trim(), data.get("password"));
    await goNext();
  },
  async signup(form, data) {
    const { needsConfirmation } = await signUp({
      email: data.get("email").trim(),
      password: data.get("password"),
      fullName: data.get("fullName").trim(),
      phone: data.get("phone").trim() || null,
    });
    if (needsConfirmation) {
      form.reset();
      showMessage("נרשמתם! שלחנו מייל לאישור הכתובת. אחרי האישור תוכלו להתחבר.", "success");
    } else {
      await goNext();
    }
  },
  async forgot(form, data) {
    await sendPasswordReset(data.get("email").trim());
    showMessage("אם קיים חשבון עם האימייל הזה, נשלח אליו קישור לאיפוס.", "success");
  },
  async reset(form, data) {
    await updatePassword(data.get("password"));
    resetting = false;
    showMessage("הסיסמה עודכנה.", "success");
    await goNext();
  },
};

document.querySelectorAll("[data-form]").forEach((form) => {
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    showMessage("");
    if (invalid(form)) return;
    withBusy(form, () => handlers[form.dataset.form](form, new FormData(form)));
  });
});

// Recovery link signs the user in with a temporary session -> ask for a new password.
onAuthChange((event) => {
  if (event === "PASSWORD_RECOVERY") {
    resetting = true;
    setMode("reset");
  }
});

if (resetting) {
  setMode("reset");
} else {
  // Already signed in (or just confirmed the email) -> continue.
  getAccessToken().then((token) => token && !resetting && goNext().catch(() => {}));
}
