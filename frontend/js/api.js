// Thin fetch wrapper; backend errors use { error: { code, message, details } }.
// Sends the Supabase access token when the user is signed in.
import { getAccessToken } from "/js/auth.js";

export async function api(path, options = {}) {
  const token = await getAccessToken().catch(() => null);
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(body?.error?.message ?? `Request failed (${response.status})`);
    error.code = body?.error?.code ?? "http_error";
    error.status = response.status;
    throw error;
  }
  return body;
}
