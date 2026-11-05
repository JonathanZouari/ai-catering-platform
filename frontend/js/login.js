// Customer login by email magic link (Supabase Auth). The session is kept by supabase-js in localStorage.
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm";
import { api } from "./api.js";

const $ = (id) => document.getElementById(id);
const form = $("login-form");
const field = $("email-field");
const error = $("email-error");

const { supabase_url: url, supabase_anon_key: key } = await api("/config/public");
const supabase = createClient(url, key);

function show(session) {
  form.hidden = Boolean(session) || !$("sent").hidden;
  $("signed-in").hidden = !session;
  if (session) {
    $("sent").hidden = true;
    $("user-email").textContent = session.user.email;
  }
}

function fail(message) {
  field.classList.add("invalid");
  error.textContent = message;
  error.hidden = false;
  $("email").focus();
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = $("email").value.trim();
  if (!$("email").checkValidity() || !email) return fail("צריך כתובת מייל תקינה.");
  field.classList.remove("invalid");
  error.hidden = true;

  const button = form.querySelector("button");
  button.disabled = true;
  const { error: sendError } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: `${location.origin}/login/` },
  });
  button.disabled = false;
  if (sendError) return fail("לא הצלחנו לשלוח את הקישור. כדאי לנסות שוב בעוד דקה.");

  $("sent-email").textContent = email;
  form.hidden = true;
  $("sent").hidden = false;
  $("announce").textContent = "הקישור נשלח למייל.";
});

$("sign-out").addEventListener("click", () => supabase.auth.signOut());

// Fires on load (including right after the magic-link redirect) and on sign-in/out.
supabase.auth.onAuthStateChange((_event, session) => show(session));
