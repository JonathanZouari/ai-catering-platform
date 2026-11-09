// Owner login via Supabase Auth (email + password).
// supabase-js keeps the session in localStorage and refreshes the access token automatically.
// Every admin API call sends that token; the backend checks it and the admin role.
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm";
import { api } from "/js/api.js";

let clientPromise;

function client() {
  clientPromise ??= api("/api/auth/config").then(({ supabase_url, publishable_key }) =>
    createClient(supabase_url, publishable_key, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
    }),
  );
  return clientPromise;
}

export async function signIn(email, password) {
  const supabase = await client();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message === "Invalid login credentials"
    ? "האימייל או הסיסמה שגויים."
    : "לא הצלחנו להתחבר. נסו שוב בעוד רגע.");
  return currentAdmin();
}

export async function signOut() {
  const supabase = await client();
  await supabase.auth.signOut();
}

// Calls a backend admin endpoint with the current access token.
export async function adminApi(path, options = {}) {
  const supabase = await client();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    const error = new Error("נא להתחבר.");
    error.code = "unauthenticated";
    throw error;
  }
  return api(path, { ...options, headers: { ...options.headers, Authorization: `Bearer ${token}` } });
}

// The signed-in admin, or null when nobody (or a non-admin) is signed in.
export async function currentAdmin() {
  try {
    return await adminApi("/api/admin/me");
  } catch (error) {
    if (error.code === "forbidden") {
      await signOut();
      throw new Error("לחשבון הזה אין הרשאה לממשק העסק.");
    }
    if (error.code === "unauthenticated") return null;
    throw error;
  }
}
