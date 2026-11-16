// Landing page lead form. Calls public.submit_lead with the publishable key; the database validates
// everything again and RLS keeps leads unreadable to visitors. No supabase-js needed for one call.
import { api } from "./api.js";

const form = document.getElementById("lead-form");
const status = document.getElementById("lead-status");
const button = form?.querySelector("button[type=submit]");

function setFieldError(name, text) {
  const input = form.elements[name];
  const error = document.getElementById(`err-lead-${name}`);
  input.closest(".field").classList.toggle("invalid", Boolean(text));
  input.setAttribute("aria-invalid", text ? "true" : "false");
  error.textContent = text;
  error.hidden = !text;
}

function validate() {
  const name = form.elements.name.value.trim();
  const phone = form.elements.phone.value.replace(/\D/g, "").replace(/^972/, "0");
  const errors = {
    name: name.length < 2 ? "נא למלא שם מלא." : "",
    phone: /^0\d{8,9}$/.test(phone) ? "" : "נא למלא מספר טלפון תקין, למשל 050-1234567.",
  };
  Object.entries(errors).forEach(([field, text]) => setFieldError(field, text));
  const first = Object.keys(errors).find((field) => errors[field]);
  if (first) form.elements[first].focus();
  return !first;
}

function show(text, kind) {
  status.textContent = text;
  status.className = `contact-status is-${kind}`;
}

async function submit(event) {
  event.preventDefault();
  if (!validate()) return;
  button.disabled = true;
  show("שולחים…", "ok");
  const payload = Object.fromEntries(new FormData(form));
  try {
    const { supabaseUrl, supabasePublishableKey } = await api("/api/public-config");
    const response = await fetch(`${supabaseUrl}/rest/v1/rpc/submit_lead`, {
      method: "POST",
      headers: { "Content-Type": "application/json", apikey: supabasePublishableKey },
      body: JSON.stringify({ payload }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      // Messages raised by submit_lead are written in Hebrew for the visitor.
      throw new Error(body?.message && /[֐-׿]/.test(body.message) ? body.message : "");
    }
    form.reset();
    show("תודה! קיבלנו את הפרטים ונחזור אליכם בהקדם.", "ok");
  } catch (error) {
    show(error.message || "השליחה לא הצליחה. נסו שוב בעוד כמה דקות.", "error");
  } finally {
    button.disabled = false;
  }
}

form?.addEventListener("submit", submit);
