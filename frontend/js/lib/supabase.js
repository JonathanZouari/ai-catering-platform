// Shared Supabase client. The publishable key is safe in the browser: RLS decides what it can do.
// window.supabase comes from the vendored script tag in each page.
import { api } from "../api.js";

async function createClient() {
  try {
    const { supabaseUrl, supabasePublishableKey } = await api("/api/public-config");
    return window.supabase.createClient(supabaseUrl, supabasePublishableKey);
  } catch (error) {
    const message = document.createElement("p");
    message.setAttribute("role", "alert");
    message.textContent = "המערכת אינה זמינה כרגע. נסו שוב בעוד כמה דקות.";
    (document.querySelector("main") ?? document.body).replaceChildren(message);
    throw error;
  }
}

export const sb = await createClient();

const DRAFT_KEY = "catering.customer.draft.v1";

export const isAdmin = (session) => session?.user?.app_metadata?.role === "admin";

/** Sends visitors without a session to the login page. This is UX only; RLS is the real guard. */
export async function requireSession() {
  const { data: { session } } = await sb.auth.getSession();
  if (session) return session;
  location.replace(`/login/?next=${encodeURIComponent(location.pathname + location.search + location.hash)}`);
  return new Promise(() => {}); // the page is leaving; stop the caller here
}

export async function signOut() {
  await sb.auth.signOut();
  try {
    localStorage.removeItem(DRAFT_KEY); // the next person on this device must not see this draft
  } catch {
    /* storage unavailable */
  }
  location.replace("/login/");
}

export const dishImageUrl = (path) => (path ? sb.storage.from("dish-images").getPublicUrl(path).data.publicUrl : null);
