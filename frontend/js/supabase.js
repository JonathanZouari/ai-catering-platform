// Supabase browser client. The publishable key is meant to be public; access is enforced by RLS.
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm";

export const supabase = createClient(
  "https://hnvsrtgmcfywulrllghu.supabase.co",
  "sb_publishable_AvfN6eq7_KEI6-Hp_SRUcw_nvmvc4rh",
);

export const roleOf = (user) => (user?.app_metadata?.role === "owner" ? "owner" : "customer");
