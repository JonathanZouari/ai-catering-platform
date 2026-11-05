// Supabase Realtime as a change signal only. Payloads are never trusted or rendered: every event
// triggers a re-fetch through our own backend, which does the real access checks and pricing.
// supabase-js is vendored (/vendor, loaded by a plain <script>) because the CSP allows only 'self'.
// Row-level security decides which events a user is sent; guests with only the anon key get just
// the public menu tables. If the library or the connection is unavailable, nothing happens and
// the pages keep working as before.
export function watch({ config, token = null, tables, onChange }) {
  const lib = globalThis.supabase;
  if (!lib || !config?.supabase_url || !config?.supabase_anon_key) return () => {};
  const client = lib.createClient(config.supabase_url, config.supabase_anon_key, {
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  });
  if (token) client.realtime.setAuth(token);
  let timer = null;
  const fire = () => { clearTimeout(timer); timer = setTimeout(onChange, 400); }; // coalesce bursts
  const channel = client.channel(`live-${Math.random().toString(36).slice(2)}`);
  for (const t of tables) {
    const { table, filter } = typeof t === "string" ? { table: t } : t;
    channel.on("postgres_changes", { event: "*", schema: "public", table, ...(filter ? { filter } : {}) }, fire);
  }
  channel.subscribe();
  return () => { clearTimeout(timer); client.removeChannel(channel); };
}
