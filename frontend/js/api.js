// Thin fetch wrapper; backend errors use { error: { code, message, details } }.
export async function api(path, options = {}) {
  const response = await fetch(path, {
    signal: AbortSignal.timeout(15000),
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(body?.error?.message ?? (typeof body?.detail === "string" ? body.detail : "לא ניתן להשלים את הבקשה. בדקו את הפרטים ונסו שוב."));
    error.code = body?.error?.code ?? "http_error";
    error.status = response.status;
    throw error;
  }
  return body;
}
