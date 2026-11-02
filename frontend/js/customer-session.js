// Shared customer session (ADR 0005): one supabase-js client per page, and API calls that carry
// the customer's access token. Rejects with { code: "auth_unavailable" } when login isn't set up.
import { api } from "/js/api.js";

// Pinned: supabase-js runs in our origin with the customer's session, so never float the version.
const SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm";

let client = null;

export function supabase() {
  client ??= (async () => {
    const config = await api("/api/auth/config");
    const { createClient } = await import(SUPABASE_JS);
    return createClient(config.supabase_url, config.supabase_anon_key, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
    });
  })().catch((err) => {
    client = null; // allow a retry on the next call
    throw Object.assign(new Error("auth unavailable"), { code: "auth_unavailable", cause: err });
  });
  return client;
}

export async function session() {
  const { data } = await (await supabase()).auth.getSession(); // refreshed when needed
  return data.session;
}

export async function call(path, options = {}) {
  const s = await session();
  const headers = s ? { Authorization: `Bearer ${s.access_token}` } : {};
  return api(path, { ...options, headers });
}
