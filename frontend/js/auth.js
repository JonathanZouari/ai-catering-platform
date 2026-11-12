// Login and roles, backed by Supabase Auth.
// Who you are is decided by the database, never by data the user can edit:
//   staff    = you have an active row in staff_users
//   customer = a customers row has your auth_user_id
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm";
import { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } from "/js/supabase-config.js";

export const supabase = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);

export const HOME_FOR_ROLE = { staff: "/admin/", customer: "/account/" };

// Returns { user, role, profile } or null when nobody is logged in.
export async function currentUser() {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) return null;
  const user = session.user;

  const { data: staff } = await supabase
    .from("staff_users").select("id, full_name, is_active").eq("id", user.id).maybeSingle();
  if (staff?.is_active) return { user, role: "staff", profile: staff };

  const { data: customer } = await supabase
    .from("customers").select("id, full_name, phone, email").eq("auth_user_id", user.id).maybeSingle();
  if (customer) return { user, role: "customer", profile: customer };

  return { user, role: null, profile: null };
}

// Sends the visitor to the login page unless they have the given role.
export async function requireRole(role) {
  const me = await currentUser();
  if (!me || me.role !== role) {
    const back = encodeURIComponent(location.pathname);
    location.replace(`/login/?next=${back}${me ? "&denied=1" : ""}`);
    return new Promise(() => {}); // stop the page while redirecting
  }
  return me;
}

export async function signIn(email, password) {
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
  return currentUser();
}

export async function signOut() {
  await supabase.auth.signOut();
  location.replace("/login/");
}

export function dishImageUrl(path) {
  if (!path) return null;
  return supabase.storage.from("dish-images").getPublicUrl(path).data.publicUrl;
}

export const shekels = (agorot) =>
  agorot == null ? "—" : new Intl.NumberFormat("he-IL", { style: "currency", currency: "ILS" }).format(agorot / 100);

export const STATUS_LABEL = {
  draft: "טיוטה",
  pending_approval: "ממתינה לאישור",
  approved: "מאושרת",
  rejected: "נדחתה",
  cancelled: "בוטלה",
  completed: "הסתיימה",
};
