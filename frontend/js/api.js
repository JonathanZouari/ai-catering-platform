// Thin fetch wrapper; backend errors use { error: { code, message, details } }.
export async function api(path, options = {}) {
  const isForm = options.body instanceof FormData;
  const headers = { ...(isForm ? {} : { "Content-Type": "application/json" }), ...options.headers };
  const response = await fetch(path, { ...options, headers });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(body?.error?.message ?? `הבקשה נכשלה (${response.status})`);
    error.code = body?.error?.code ?? "http_error";
    error.status = response.status;
    throw error;
  }
  return body;
}
