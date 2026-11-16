import { isAdmin, sb } from "./lib/supabase.js";

const $ = (id) => document.getElementById(id);
const form = $("auth-form"), title = $("auth-title"), nameField = $("name-field"), name = $("auth-name");
const email = $("auth-email"), password = $("auth-password"), hint = $("password-hint");
const error = $("auth-error"), submit = $("auth-submit"), toggle = $("auth-toggle");

const ERRORS = {
  invalid_credentials: "האימייל או הסיסמה שגויים.",
  user_already_exists: "כבר קיים חשבון עם האימייל הזה. נסו להיכנס.",
  email_exists: "כבר קיים חשבון עם האימייל הזה. נסו להיכנס.",
  weak_password: "הסיסמה חלשה מדי. בחרו סיסמה ארוכה יותר.",
  email_address_invalid: "כתובת האימייל אינה תקינה.",
  over_request_rate_limit: "יותר מדי ניסיונות. נסו שוב בעוד כמה דקות.",
};

let signingUp = false;

function setMode(next) {
  signingUp = next;
  title.textContent = next ? "הרשמה" : "כניסה לחשבון";
  submit.textContent = next ? "יצירת חשבון" : "כניסה";
  toggle.textContent = next ? "כבר יש לכם חשבון? כניסה" : "אין לכם חשבון? הרשמה";
  nameField.hidden = !next;
  hint.hidden = !next;
  password.autocomplete = next ? "new-password" : "current-password";
  showError("");
}

function showError(text) {
  error.textContent = text;
  error.hidden = !text;
}

/** Same-site paths only. Uses the browser's own URL parser, which strips tabs and newlines: "/\t/evil.example" means "//evil.example". */
function safeNext(raw) {
  if (!raw?.startsWith("/")) return null;
  try {
    const url = new URL(raw, location.origin);
    return url.origin === location.origin ? url.pathname + url.search + url.hash : null;
  } catch {
    return null;
  }
}

function destination(session) {
  return safeNext(new URLSearchParams(location.search).get("next")) ?? (isAdmin(session) ? "/admin/" : "/customer/");
}

toggle.addEventListener("click", () => setMode(!signingUp));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");
  if (!email.value.trim() || !password.value) return showError("הזינו אימייל וסיסמה.");
  if (signingUp && !name.value.trim()) return showError("הזינו שם מלא.");
  if (signingUp && password.value.length < 8) return showError("הסיסמה צריכה להכיל לפחות 8 תווים.");

  submit.disabled = true;
  const credentials = { email: email.value.trim(), password: password.value };
  const { data, error: failure } = signingUp
    ? await sb.auth.signUp({ ...credentials, options: { data: { full_name: name.value.trim() } } })
    : await sb.auth.signInWithPassword(credentials);
  submit.disabled = false;

  if (failure) return showError(ERRORS[failure.code] ?? "לא הצלחנו להשלים את הפעולה. נסו שוב.");
  if (data.session) location.replace(destination(data.session));
  else showError("שלחנו לכם מייל לאישור החשבון. אחרי האישור אפשר להיכנס.");
});

const { data: { session } } = await sb.auth.getSession();
if (session) location.replace(destination(session));
