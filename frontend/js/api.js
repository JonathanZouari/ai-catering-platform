// Thin fetch wrapper; backend errors use { error: { code, message, details } }.
// Two separate session keys: the owner's pages never send the customer's token and vice versa.
function tokenStore(key) {
  return {
    get: () => sessionStorage.getItem(key),
    set: (token) => sessionStorage.setItem(key, token),
    clear: () => sessionStorage.removeItem(key),
  };
}
export const auth = tokenStore("admin_token");
export const customerAuth = tokenStore("customer_token");

// The customer's refresh token lives beside the access token, in the same per-tab storage.
const REFRESH_KEY = "customer_refresh";
const EXPIRES_KEY = "customer_expires";
const read = (k) => { try { return sessionStorage.getItem(k); } catch { return null; } };

export const customerSession = {
  save(body) {
    customerAuth.set(body.access_token);
    sessionStorage.setItem(REFRESH_KEY, body.refresh_token ?? "");
    sessionStorage.setItem(EXPIRES_KEY, String(Math.floor(Date.now() / 1000) + Number(body.expires_in ?? 3600)));
  },
  clear() {
    customerAuth.clear();
    sessionStorage.removeItem(REFRESH_KEY);
    sessionStorage.removeItem(EXPIRES_KEY);
  },
  expiresSoon: () => Number(read(EXPIRES_KEY) ?? 0) - Date.now() / 1000 < 60,
  // One refresh at a time: Supabase rotates refresh tokens, so parallel refreshes would fail.
  refreshing: null,
  refresh() {
    this.refreshing ??= (async () => {
      const rt = read(REFRESH_KEY);
      const config = await fetch("/api/public-config").then((r) => r.json()).catch(() => ({}));
      const fail = () => Object.assign(new Error("session_expired"), { code: "session_expired", status: 401 });
      if (!rt || !config.supabase_url || !config.supabase_anon_key) throw fail();
      const response = await fetch(`${config.supabase_url}/auth/v1/token?grant_type=refresh_token`, {
        method: "POST",
        headers: { "Content-Type": "application/json", apikey: config.supabase_anon_key },
        body: JSON.stringify({ refresh_token: rt }),
      }).catch(() => null);
      if (!response?.ok) throw fail(); // the stale token is kept: callers must not fall back to a guest
      this.save(await response.json());
    })().finally(() => { this.refreshing = null; });
    return this.refreshing;
  },
};

function makeApi(store, session = null) {
  // options.auth === false: send no bearer (e.g. calls that carry an X-Order-Token instead).
  return async function api(path, options = {}) {
    const { auth: useAuth, ...init } = options;
    const send = () => {
      const headers = { ...init.headers };
      // FormData must set its own multipart boundary.
      if (!(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
      const token = useAuth === false ? null : store.get();
      if (token) headers.Authorization = `Bearer ${token}`;
      return [token, fetch(path, { ...init, headers })];
    };
    // A signed-in customer's token is refreshed before it expires; if that fails we throw
    // session_expired instead of quietly continuing as a guest.
    if (session && useAuth !== false && store.get() && session.expiresSoon()) await session.refresh();
    let [token, pending] = send();
    let response = await pending;
    if (response.status === 401 && token && session) {
      await session.refresh();
      [token, pending] = send();
      response = await pending;
    }
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      if (response.status === 401 && token && !session) store.clear(); // owner: expired, stop sending
      const error = new Error(body?.error?.message ?? `Request failed (${response.status})`);
      error.code = body?.error?.code ?? "http_error";
      error.status = response.status;
      throw error;
    }
    return body;
  };
}

export const api = makeApi(auth); // owner pages
export const customerApi = makeApi(customerAuth, customerSession); // customer pages
