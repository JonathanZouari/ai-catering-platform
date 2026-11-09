// Live order changes from Supabase Realtime, so the dashboard updates by itself.
// Our own small client for the one thing we need, instead of loading supabase-js.
// A message is only a signal to reload from our API: prices and status always come from the
// backend, and RLS makes Supabase send each caterer only its own orders.
import { accessToken, getConfig } from "/js/admin/auth.js";

const TOPIC = "realtime:orders";
const HEARTBEAT_MS = 25_000;
const TOKEN_CHECK_MS = 60_000;
const MAX_RETRY_MS = 30_000;

export function watchOrders(onChange) {
  let socket;
  let ref = 0;
  let retryMs = 1000;
  let timers = [];
  let stopped = false;
  let sentToken;

  const send = (topic, event, payload) => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ topic, event, payload, ref: String(++ref) }));
    }
  };

  const clearTimers = () => {
    timers.forEach(clearInterval);
    timers = [];
  };

  async function connect() {
    if (stopped) return;
    const { supabase_url: url, supabase_anon_key: anonKey } = await getConfig();
    if (!url) return;
    let token;
    try {
      token = await accessToken();
    } catch {
      return; // Logged out: nothing to watch.
    }
    const address = `${url.replace(/^http/, "ws")}/realtime/v1/websocket?apikey=${encodeURIComponent(anonKey)}&vsn=1.0.0`;
    socket = new WebSocket(address);

    socket.addEventListener("open", () => {
      retryMs = 1000;
      sentToken = token;
      send(TOPIC, "phx_join", {
        config: { postgres_changes: [{ event: "*", schema: "public", table: "orders" }] },
        access_token: token,
      });
      timers.push(setInterval(() => send("phoenix", "heartbeat", {}), HEARTBEAT_MS));
      // Logins last an hour, so hand Realtime the refreshed token before the old one expires.
      timers.push(setInterval(async () => {
        try {
          const fresh = await accessToken();
          if (fresh !== sentToken) {
            sentToken = fresh;
            send(TOPIC, "access_token", { access_token: fresh });
          }
        } catch {
          stop();
        }
      }, TOKEN_CHECK_MS));
    });

    socket.addEventListener("message", (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (message.topic === TOPIC && message.event === "postgres_changes") onChange();
    });

    socket.addEventListener("close", () => {
      clearTimers();
      if (stopped) return;
      // Missed changes are picked up by the reload that follows a reconnect.
      setTimeout(() => connect().then(onChange, () => {}), retryMs);
      retryMs = Math.min(retryMs * 2, MAX_RETRY_MS);
    });
  }

  function stop() {
    stopped = true;
    clearTimers();
    socket?.close();
  }

  connect();
  return stop;
}
