// Browser Supabase client: publishable key only (RLS limits what it can read or write).
// Pinned version; there is no bundler, so it loads as an ES module from the CDN.
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.119.0/+esm";
import { api } from "./api.js";

let clientPromise = null;

/** Resolves to the client, or null when the server has no Supabase configured (local SQLite). */
export function supabase() {
  clientPromise ??= api("/api/config").then((cfg) =>
    cfg.supabase_url && cfg.supabase_publishable_key
      ? createClient(cfg.supabase_url, cfg.supabase_publishable_key)
      : null,
  ).catch((error) => {
    clientPromise = null;
    throw error;
  });
  return clientPromise;
}
