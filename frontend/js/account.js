// Customer account (ADR 0005): passwordless sign-in with a 6-digit email code via Supabase Auth,
// profile completion, and the customer's own orders. Server data goes in via textContent only.
import { call as authedCall, session, supabase } from "/js/customer-session.js";

const STATUS = { draft: "טיוטה", pending_approval: "ממתינה לאישור", approved: "אושרה", rejected: "נדחתה" };
const RESEND_SECONDS = 60;

const $ = (id) => document.getElementById(id);
const STEPS = ["email-step", "code-step", "profile-step", "account"];
let sb = null;
let pendingEmail = "";
let me = null;

function show(step, title, lede) {
  for (const id of STEPS) $(id).hidden = id !== step;
  $("title").textContent = title;
  $("lede").textContent = lede;
}

function fail(id, text) {
  $(id).textContent = text;
  $(id).hidden = !text;
}

let toastTimer;
function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
}

function authMessage(error) {
  if (error?.status === 429) return "יותר מדי ניסיונות. נסו שוב בעוד כמה דקות";
  return "משהו השתבש, נסו שוב";
}

async function call(path, options = {}) {
  try {
    return await authedCall(path, options);
  } catch (err) {
    if (err.status === 401) await signOut();
    throw err;
  }
}

function showEmail() {
  show("email-step", "כניסה", "בלי סיסמה: שולחים לכם קוד לאימייל, ומקלידים אותו כאן.");
  $("email").focus();
}

async function sendCode(email) {
  const { error } = await sb.auth.signInWithOtp({ email, options: { shouldCreateUser: true } });
  if (error) throw error;
  pendingEmail = email;
  $("sent-to").textContent = email;
  startResendTimer();
}

let resendTimer;
function startResendTimer() {
  const b = $("resend");
  let left = RESEND_SECONDS;
  clearInterval(resendTimer);
  b.disabled = true;
  b.textContent = `שליחה מחדש (${left})`;
  resendTimer = setInterval(() => {
    left -= 1;
    if (left > 0) { b.textContent = `שליחה מחדש (${left})`; return; }
    clearInterval(resendTimer);
    b.disabled = false;
    b.textContent = "שליחה מחדש";
  }, 1000);
}

async function loadMe() {
  me = await call("/api/me");
  if (!me.profile) {
    show("profile-step", "עוד רגע", "רק שם וטלפון, פעם אחת.");
    $("full-name").focus();
    return;
  }
  await showAccount();
}

const fact = (term, value) => {
  const row = document.createElement("div");
  const dt = Object.assign(document.createElement("dt"), { textContent: term });
  const dd = Object.assign(document.createElement("dd"), { textContent: value });
  if (term !== "שם") dd.dir = "ltr";
  row.append(dt, dd);
  return row;
};

const money = (v) => (v === null ? "—" : new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS" }).format(v));
const day = (iso) => new Intl.DateTimeFormat("he-IL", { day: "numeric", month: "short", year: "numeric" }).format(new Date(`${iso}T00:00`));

async function showAccount() {
  show("account", `שלום, ${me.profile.full_name}`, "כאן תראו את ההזמנות שלכם ואת הסטטוס שלהן.");
  $("profile-facts").replaceChildren(fact("שם", me.profile.full_name), fact("אימייל", me.email), fact("טלפון", me.profile.phone ?? "—"));
  const orders = await call("/api/me/orders");
  $("no-orders").hidden = orders.length > 0;
  $("order-rows").replaceChildren(...orders.map((o) => {
    const tr = document.createElement("tr");
    const event = document.createElement("th");
    event.scope = "row";
    // Drafts open in the event planner; submitted orders are read-only for now.
    event.append(o.status === "draft"
      ? Object.assign(document.createElement("a"), { href: `/customer/event/?order=${encodeURIComponent(o.id)}`, textContent: o.event_type })
      : o.event_type);
    const meta = `${day(o.event_date)} · ${o.guests} אורחים`;
    for (const line of [meta, o.decision_note].filter(Boolean)) {
      event.append(Object.assign(document.createElement("span"), { className: "help", textContent: line }));
    }
    const pill = Object.assign(document.createElement("span"), { className: `pill s-${o.status}`, textContent: STATUS[o.status] ?? o.status });
    const status = document.createElement("td");
    status.append(pill);
    const total = Object.assign(document.createElement("td"), { className: "num", textContent: money(o.total) });
    tr.append(event, status, total);
    return tr;
  }));
}

async function signOut() {
  await sb.auth.signOut().catch(() => {});
  me = null;
  showEmail();
}

function wire() {
  $("email-step").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("email");
    const email = input.value.trim().toLowerCase();
    if (!input.checkValidity() || !email) {
      input.setAttribute("aria-invalid", "true");
      fail("email-error", "צריך כתובת אימייל תקינה");
      input.focus();
      return;
    }
    input.removeAttribute("aria-invalid");
    fail("email-error", "");
    try {
      await sendCode(email);
      show("code-step", "בדקו את המייל", "הקלידו את הקוד שקיבלתם.");
      $("code").value = "";
      $("code").focus();
    } catch (err) {
      fail("email-error", authMessage(err));
    }
  });

  $("code-step").addEventListener("submit", async (e) => {
    e.preventDefault();
    const code = $("code").value.replace(/\D/g, "");
    if (code.length !== 6) {
      fail("code-error", "הקוד הוא 6 ספרות");
      $("code").focus();
      return;
    }
    fail("code-error", "");
    const { error } = await sb.auth.verifyOtp({ email: pendingEmail, token: code, type: "email" });
    if (error) {
      fail("code-error", error.status === 429 ? authMessage(error) : "הקוד שגוי או שפג תוקפו");
      $("code").select();
      return;
    }
    loadMe().catch((err) => { if (err.status !== 401) toast("משהו השתבש, נסו שוב"); });
  });

  $("resend").addEventListener("click", () => {
    sendCode(pendingEmail).then(() => toast("שלחנו קוד חדש")).catch((err) => fail("code-error", authMessage(err)));
  });
  $("change-email").addEventListener("click", () => { clearInterval(resendTimer); showEmail(); });

  $("profile-step").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = $("full-name");
    const phone = $("phone");
    const bad = [name, phone].filter((i) => !i.checkValidity() || !i.value.trim());
    for (const i of [name, phone]) i.setAttribute("aria-invalid", String(bad.includes(i)));
    if (bad.length) { fail("profile-error", "צריך שם וטלפון"); bad[0].focus(); return; }
    try {
      me = await call("/api/me", { method: "PUT", body: JSON.stringify({ full_name: name.value, phone: phone.value }) });
      fail("profile-error", "");
      await showAccount();
      toast("הפרטים נשמרו");
    } catch (err) {
      if (err.status === 401) return;
      fail("profile-error", err.code === "validation_error" ? "בדקו את השם והטלפון" : "משהו השתבש, נסו שוב");
    }
  });

  $("edit-profile").addEventListener("click", () => {
    $("full-name").value = me.profile.full_name;
    $("phone").value = me.profile.phone ?? "";
    show("profile-step", "עריכת פרטים", "השם והטלפון שלכם.");
    $("full-name").focus();
  });
  $("sign-out").addEventListener("click", () => signOut());
}

export async function initAccount() {
  try {
    sb = await supabase();
  } catch {
    $("unavailable").hidden = false;
    for (const id of STEPS) $(id).hidden = true;
    return;
  }
  wire();
  if (await session()) {
    loadMe().catch((err) => { if (err.status !== 401) toast("משהו השתבש, נסו שוב"); });
  } else {
    showEmail();
  }
}
