// Owner screens: sign in with Supabase Auth, then manage dish photos.
// The browser only holds the user's session; uploads go through the backend
// (POST /api/admin/dishes/{id}/image), which checks the owner role and the file.
import { api } from "../api.js";
import { fill, h } from "../lib/dom.js";
import { fmtMoney } from "../lib/format.js";
import { supabase } from "../supabase.js";

const root = document.getElementById("admin");
const account = document.getElementById("account");
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 5 * 1024 * 1024;

let sb = null;

async function authed(path, options = {}) {
  const { data } = await sb.auth.getSession();
  const token = data.session?.access_token;
  return api(path, { ...options, headers: { ...options.headers, Authorization: `Bearer ${token}` } });
}

/* ---------------- sign in ---------------- */

function renderLogin(message = "") {
  fill(account);
  const error = h("p", { class: "form-error", role: "alert", text: message });
  const email = h("input", { class: "input", id: "email", type: "email", autocomplete: "username", required: true });
  const password = h("input", { class: "input", id: "password", type: "password", autocomplete: "current-password", required: true });
  const submit = h("button", { class: "btn btn-primary btn-block", type: "submit" }, "כניסה");

  const form = h("form", { class: "login-card", novalidate: true },
    h("h2", { text: "כניסה לבעלי העסק" }),
    h("div", { class: "field" }, h("label", { for: "email", text: "אימייל" }), email),
    h("div", { class: "field" }, h("label", { for: "password", text: "סיסמה" }), password),
    error,
    submit,
  );
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!email.value.trim() || !password.value) {
      error.textContent = "הזינו אימייל וסיסמה";
      return;
    }
    submit.disabled = true;
    error.textContent = "";
    const { error: authError } = await sb.auth.signInWithPassword({ email: email.value.trim(), password: password.value });
    submit.disabled = false;
    if (authError) error.textContent = "האימייל או הסיסמה שגויים";
    // On success onAuthStateChange renders the dashboard.
  });
  fill(root, form);
  email.focus();
}

/* ---------------- dashboard ---------------- */

function renderAccount(user) {
  fill(account,
    h("span", { class: "muted small", text: user.email }),
    h("button", { class: "btn btn-ghost", type: "button", onclick: () => sb.auth.signOut() }, "יציאה"));
}

function dishRow(dish) {
  const status = h("span", { class: "admin-dish-status muted", role: "status" });
  const thumb = () => dish.image_url
    ? h("img", { class: "admin-thumb", src: dish.image_url, alt: `תמונה של ${dish.name}` })
    : h("div", { class: "admin-thumb muted", text: "אין תמונה" });
  const thumbSlot = h("div", {}, thumb());

  const input = h("input", { type: "file", accept: IMAGE_TYPES.join(",") });
  input.addEventListener("change", async () => {
    const file = input.files[0];
    input.value = "";
    if (!file) return;
    status.classList.remove("error");
    if (!IMAGE_TYPES.includes(file.type)) {
      status.classList.add("error");
      status.textContent = "אפשר להעלות JPEG, PNG או WebP";
      return;
    }
    if (file.size > MAX_BYTES) {
      status.classList.add("error");
      status.textContent = "התמונה גדולה מ-5MB";
      return;
    }
    const form = new FormData();
    form.append("file", file);
    status.textContent = "מעלה…";
    try {
      dish = await authed(`/api/admin/dishes/${dish.id}/image`, { method: "POST", body: form });
      fill(thumbSlot, thumb());
      status.textContent = "התמונה נשמרה";
    } catch (err) {
      status.classList.add("error");
      status.textContent = err.status === 401 ? "פג תוקף הכניסה. היכנסו שוב." : err.message;
    }
  });

  return h("li", { class: `admin-dish${dish.is_available === false ? " is-hidden" : ""}` },
    thumbSlot,
    h("div", {},
      h("p", { class: "admin-dish-name", text: dish.name }),
      h("p", { class: "admin-dish-meta muted", text: fmtMoney(Number(dish.unit_price)) }),
      status),
    h("label", { class: "btn btn-secondary upload-label" },
      dish.image_url ? "החלפת תמונה" : "העלאת תמונה", input),
  );
}

async function renderDashboard() {
  fill(root, h("p", { class: "muted", text: "טוען…" }));
  let user;
  try {
    user = await authed("/api/admin/me");
  } catch (err) {
    if (err.status === 403) {
      await sb.auth.signOut();
      renderLogin("למשתמש הזה אין הרשאת בעלים");
      return;
    }
    fill(root, h("p", { class: "form-error", role: "alert", text: err.message }));
    return;
  }
  renderAccount(user);
  const dishes = await authed("/api/admin/dishes");
  fill(root,
    h("section", { class: "stack" },
      h("h2", { text: "תמונות המנות" }),
      h("p", { class: "muted", text: "JPEG, PNG או WebP, עד 5MB. התמונה מופיעה מיד בתפריט של הלקוחות." }),
      h("ul", { class: "admin-dishes" }, dishes.map(dishRow))));
}

/* ---------------- boot ---------------- */

async function boot() {
  try {
    sb = await supabase();
  } catch {
    fill(root, h("p", { class: "form-error", role: "alert", text: "השרת לא זמין" }));
    return;
  }
  if (!sb) {
    fill(root, h("p", { class: "form-error", role: "alert", text: "Supabase לא מוגדר בשרת (SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY)." }));
    return;
  }
  let signedIn = null;
  sb.auth.onAuthStateChange((event, session) => {
    // TOKEN_REFRESHED keeps the same user: no need to rebuild the screen.
    const now = Boolean(session);
    if (now === signedIn) return;
    signedIn = now;
    // Leave the auth callback before calling Supabase again (supabase-js recommendation).
    setTimeout(() => (now ? renderDashboard() : renderLogin()), 0);
  });
}

boot();
