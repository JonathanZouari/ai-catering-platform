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

function makeApi(store) {
  // options.auth === false: send no bearer (e.g. calls that carry an X-Order-Token instead).
  return async function api(path, options = {}) {
    const { auth: useAuth, ...init } = options;
    const headers = { ...init.headers };
    // FormData must set its own multipart boundary.
    if (!(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
    const token = useAuth === false ? null : store.get();
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(path, { ...init, headers });
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      if (response.status === 401 && token) store.clear(); // expired: stop sending it
      const error = new Error(body?.error?.message ?? `Request failed (${response.status})`);
      error.code = body?.error?.code ?? "http_error";
      error.status = response.status;
      throw error;
    }
    return body;
  };
}

export const api = makeApi(auth); // owner pages
export const customerApi = makeApi(customerAuth); // customer pages
