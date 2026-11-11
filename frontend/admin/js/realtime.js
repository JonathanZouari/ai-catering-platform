// Owns the single live-update channel for the selected table. The client and timers are
// injected so tests can drive it without a network. Status values: idle, connecting, live, offline.

const RETRY_MIN_MS = 5000;
const RETRY_MAX_MS = 60000;

export function createRealtimeController({
  client,
  onRefresh,
  onStatus,
  debounceMs = 400,
  setTimer = setTimeout,
  clearTimer = clearTimeout,
}) {
  let channel = null;
  let table = null;
  let generation = 0; // Callbacks from a replaced channel carry an old generation and are ignored.
  let debounceTimer = null;
  let retryTimer = null;
  let retryDelay = RETRY_MIN_MS;

  function clearTimers() {
    clearTimer(debounceTimer);
    clearTimer(retryTimer);
    debounceTimer = null;
    retryTimer = null;
  }

  function removeCurrentChannel() {
    if (channel) {
      Promise.resolve(client.removeChannel(channel)).catch(() => {});
      channel = null;
    }
  }

  function scheduleRefresh() {
    clearTimer(debounceTimer);
    debounceTimer = setTimer(() => {
      debounceTimer = null;
      onRefresh();
    }, debounceMs);
  }

  function scheduleRetry(mine) {
    if (retryTimer !== null) return;
    retryTimer = setTimer(() => {
      retryTimer = null;
      if (mine === generation && table) open();
    }, retryDelay);
    retryDelay = Math.min(retryDelay * 2, RETRY_MAX_MS);
  }

  function open() {
    // Bump first: removing the old channel reports CLOSED, which must not look like an outage.
    const mine = ++generation;
    removeCurrentChannel();
    clearTimer(retryTimer);
    retryTimer = null;
    onStatus("connecting");
    // A unique topic per attempt: the client hands back an existing channel for a repeated topic.
    channel = client
      .channel(`admin-table:${table}:${mine}`)
      .on("postgres_changes", { event: "*", schema: "public", table }, () => {
        if (mine === generation) scheduleRefresh();
      })
      .subscribe((status) => {
        if (mine !== generation) return;
        if (status === "SUBSCRIBED") {
          retryDelay = RETRY_MIN_MS;
          onStatus("live");
          // Picks up anything missed before this connection or during an outage.
          scheduleRefresh();
        } else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT" || status === "CLOSED") {
          onStatus("offline");
          scheduleRetry(mine);
        }
      });
  }

  return {
    switchTo(nextTable) {
      clearTimers();
      table = nextTable;
      retryDelay = RETRY_MIN_MS;
      open();
    },
    stop() {
      clearTimers();
      generation += 1;
      table = null;
      removeCurrentChannel();
      onStatus("idle");
    },
    // Called when the browser reports its network is back or gone.
    networkChanged(isOnline) {
      if (!table) return;
      if (isOnline) {
        retryDelay = RETRY_MIN_MS;
        open();
      } else {
        clearTimers();
        generation += 1;
        removeCurrentChannel();
        onStatus("offline");
      }
    },
  };
}
