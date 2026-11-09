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

// Seconds until the stored login expires, read from the token itself (not trusted, only timed).
function secondsLeft(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return payload.exp - Date.now() / 1000;
  } catch {
    return 0;
  }
}

// A login token with at least two minutes left, refreshing it first if needed.
export async function accessToken() {
  const session = JSON.parse(localStorage.getItem(KEY) ?? "{}");
  if (!session.access_token) throw new Error("not logged in");
  if (secondsLeft(session.access_token) > 120) return session.access_token;
  await requestToken("refresh_token", { refresh_token: session.refresh_token });
  return JSON.parse(localStorage.getItem(KEY)).access_token;
}

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
