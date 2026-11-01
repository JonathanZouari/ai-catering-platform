// Caterer login against Supabase Auth, plus an API client that sends the token.
import { api } from "/js/api.js";

const KEY = "caterer-session";
let configPromise;

export function getConfig() {
  configPromise ??= api("/api/config");
  return configPromise;
}

export const isLoggedIn = () => Boolean(localStorage.getItem(KEY));

export function logout() {
  localStorage.removeItem(KEY);
  location.hash = "";
  location.reload();
}

async function requestToken(grantType, body) {
  const { supabase_url: url, supabase_anon_key: anonKey } = await getConfig();
  if (!url) throw new Error("ההתחברות אינה מוגדרת בשרת");
  const response = await fetch(`${url}/auth/v1/token?grant_type=${grantType}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: anonKey },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error("האימייל או הסיסמה שגויים");
  const session = await response.json();
  localStorage.setItem(KEY, JSON.stringify({
    access_token: session.access_token,
    refresh_token: session.refresh_token,
  }));
}

export const login = (email, password) => requestToken("password", { email, password });

export async function adminApi(path, options = {}) {
  const send = () => {
    const { access_token: token } = JSON.parse(localStorage.getItem(KEY) ?? "{}");
    const headers = { ...options.headers, Authorization: `Bearer ${token}` };
    return api(path, { ...options, headers });
  };
  try {
    return await send();
  } catch (error) {
    if (error.status !== 401) throw error;
    const { refresh_token: refreshToken } = JSON.parse(localStorage.getItem(KEY) ?? "{}");
    try {
      await requestToken("refresh_token", { refresh_token: refreshToken });
    } catch {
      logout();
      throw error;
    }
    return send();
  }
}

export const postJson = (path, data) =>
  adminApi(path, { method: "POST", body: JSON.stringify(data) });
export const patchJson = (path, data) =>
  adminApi(path, { method: "PATCH", body: JSON.stringify(data) });
export const putJson = (path, data) =>
  adminApi(path, { method: "PUT", body: JSON.stringify(data) });
export const remove = (path) => adminApi(path, { method: "DELETE" });

export function upload(path, file) {
  const body = new FormData();
  body.append("file", file);
  return adminApi(path, { method: "POST", body });
}
