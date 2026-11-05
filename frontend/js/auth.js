// Supabase Auth in the browser. Only the public URL + anon key reach the client
// (served by GET /api/config). Authorization is enforced by the backend and RLS.
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.118.0/+esm";

let clientPromise;

export function getClient() {
  clientPromise ??= fetch("/api/config")
    .then((r) => r.json())
    .then(({ supabase_url, supabase_anon_key }) => {
      if (!supabase_url || !supabase_anon_key) throw new Error("Auth is not configured on the server");
      return createClient(supabase_url, supabase_anon_key, {
        auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
      });
    });
  return clientPromise;
}

export async function getAccessToken() {
  const { data } = await (await getClient()).auth.getSession();
  return data.session?.access_token ?? null;
}

export async function signIn(email, password) {
  const { error } = await (await getClient()).auth.signInWithPassword({ email, password });
  if (error) throw error;
}

export async function signUp({ email, password, fullName, phone }) {
  const { data, error } = await (await getClient()).auth.signUp({
    email,
    password,
    options: {
      data: { full_name: fullName, phone }, // profile only — never used for authorization
      emailRedirectTo: `${location.origin}/login/`,
    },
  });
  if (error) throw error;
  return { needsConfirmation: !data.session };
}

export async function signOut() {
  await (await getClient()).auth.signOut();
}

export async function sendPasswordReset(email) {
  const { error } = await (await getClient()).auth.resetPasswordForEmail(email, {
    redirectTo: `${location.origin}/login/?mode=reset`,
  });
  if (error) throw error;
}

export async function updatePassword(password) {
  const { error } = await (await getClient()).auth.updateUser({ password });
  if (error) throw error;
}

export async function onAuthChange(callback) {
  (await getClient()).auth.onAuthStateChange((event, session) => callback(event, session));
}

/**
 * Page guard. Redirects to the login page when signed out.
 * Returns the user from the backend ({ id, email, role }).
 */
export async function requireUser() {
  const { api } = await import("/js/api.js");
  if (!(await getAccessToken())) {
    location.replace(`/login/?next=${encodeURIComponent(location.pathname)}`);
    return new Promise(() => {}); // navigation in progress
  }
  try {
    return await api("/api/me");
  } catch (e) {
    if (e.status === 401) {
      await signOut();
      location.replace(`/login/?next=${encodeURIComponent(location.pathname)}`);
      return new Promise(() => {});
    }
    throw e;
  }
}

// Supabase error codes -> Hebrew messages.
const MESSAGES = {
  invalid_credentials: "האימייל או הסיסמה שגויים.",
  email_not_confirmed: "צריך לאשר את כתובת האימייל. בדקו את תיבת הדואר.",
  user_already_exists: "כבר קיים חשבון עם האימייל הזה. אפשר להתחבר.",
  email_exists: "כבר קיים חשבון עם האימייל הזה. אפשר להתחבר.",
  weak_password: "הסיסמה חלשה מדי. בחרו לפחות 8 תווים.",
  same_password: "הסיסמה החדשה זהה לישנה.",
  over_email_send_rate_limit: "נשלחו יותר מדי מיילים. נסו שוב בעוד כמה דקות.",
  over_request_rate_limit: "יותר מדי ניסיונות. נסו שוב בעוד כמה דקות.",
  validation_failed: "אחד השדות לא תקין.",
};

export function authErrorMessage(error) {
  return MESSAGES[error?.code] ?? "משהו השתבש. נסו שוב.";
}
