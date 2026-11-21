// Counts what a visitor does on the site, for the lead form: dishes seen, minutes, visits,
// where they came from and whether they used the assistant. Stays in this browser until the
// visitor chooses to send the lead form.
const KEY = "catering.lead.signals.v1";
const SESSION_KEY = "catering.lead.session";
const SOURCES = { google: "google", instagram: "instagram", facebook: "facebook", fb: "facebook" };

function read() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) ?? null;
  } catch {
    return null;
  }
}

function write(s) {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* storage unavailable: signals simply stay at their defaults */
  }
}

function detectSource() {
  const params = new URLSearchParams(location.search);
  const utm = (params.get("utm_source") ?? "").toLowerCase();
  if (params.get("ref") === "friend" || utm === "referral") return "referral";
  for (const [needle, source] of Object.entries(SOURCES)) if (utm.includes(needle)) return source;
  let host = "";
  try {
    host = document.referrer ? new URL(document.referrer).hostname : "";
  } catch {
    host = "";
  }
  if (!host || host === location.hostname) return "direct";
  for (const [needle, source] of Object.entries(SOURCES)) if (host.includes(needle)) return source;
  return "other";
}

let state = read() ?? { source: detectSource(), visits: 0, seconds: 0, dishes: [], usedChat: false };

/** Call once per page. A new browser session counts as a new visit. */
export function startTracking() {
  try {
    if (!sessionStorage.getItem(SESSION_KEY)) {
      sessionStorage.setItem(SESSION_KEY, "1");
      state.visits += 1;
    }
  } catch {
    state.visits = Math.max(state.visits, 1);
  }
  write(state);
  // Time counts only while the page is visible.
  setInterval(() => {
    if (document.visibilityState === "visible") {
      state.seconds += 15;
      write(state);
    }
  }, 15000);
}

export function markDishViewed(id) {
  if (state.dishes.includes(id)) return;
  state.dishes = [...state.dishes, id].slice(-500);
  write(state);
}

export function markChatUsed() {
  if (state.usedChat) return;
  state.usedChat = true;
  write(state);
}

export function leadSignals() {
  return {
    dishes_viewed: state.dishes.length,
    minutes_on_site: Math.round((state.seconds / 60) * 10) / 10,
    visits: Math.max(1, state.visits),
    source: state.source,
    used_chat: state.usedChat,
  };
}
