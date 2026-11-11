import assert from "node:assert/strict";
import { test } from "node:test";

import { createRealtimeController } from "../js/realtime.js";

function setup() {
  const channels = [];
  const removed = [];
  const timers = new Map();
  let nextTimer = 1;
  const statuses = [];
  let refreshes = 0;

  const client = {
    channel(topic) {
      const channel = {
        topic,
        filter: null,
        change: null,
        report: null,
        on(type, filter, callback) {
          assert.equal(type, "postgres_changes");
          channel.filter = filter;
          channel.change = callback;
          return channel;
        },
        subscribe(callback) {
          channel.report = callback;
          return channel;
        },
      };
      channels.push(channel);
      return channel;
    },
    removeChannel: async (channel) => {
      removed.push(channel);
      // The real client reports CLOSED when a channel is removed.
      channel.report?.("CLOSED");
    },
  };

  const controller = createRealtimeController({
    client,
    onRefresh: () => { refreshes += 1; },
    onStatus: (status) => statuses.push(status),
    setTimer: (callback, delay) => {
      const id = nextTimer++;
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimer: (id) => timers.delete(id),
  });

  const runTimers = () => {
    const pending = [...timers.values()];
    timers.clear();
    pending.forEach((timer) => timer.callback());
  };

  return { channels, removed, timers, statuses, controller, runTimers, refreshes: () => refreshes };
}

test("subscribes to postgres changes on the selected table only", () => {
  const { channels, controller } = setup();
  controller.switchTo("customers");
  assert.equal(channels.length, 1);
  assert.deepEqual(channels[0].filter, { event: "*", schema: "public", table: "customers" });
});

test("reports live only after the server confirms the subscription", () => {
  const { channels, statuses, controller } = setup();
  controller.switchTo("customers");
  assert.deepEqual(statuses, ["connecting"]);
  channels[0].report("SUBSCRIBED");
  assert.deepEqual(statuses, ["connecting", "live"]);
});

test("switching tables removes the old channel and leaves exactly one active", () => {
  const { channels, removed, controller } = setup();
  controller.switchTo("customers");
  controller.switchTo("dishes");
  assert.equal(channels.length, 2);
  assert.deepEqual(removed, [channels[0]]);
  assert.notEqual(channels[0].topic, channels[1].topic);
});

test("returning to the same table uses a fresh topic", () => {
  const { channels, controller } = setup();
  controller.switchTo("customers");
  controller.switchTo("customers");
  assert.notEqual(channels[0].topic, channels[1].topic);
});

test("a burst of changes causes a single debounced refresh", () => {
  const { channels, controller, runTimers, refreshes, timers } = setup();
  controller.switchTo("customers");
  channels[0].change();
  channels[0].change();
  channels[0].change();
  assert.equal(timers.size, 1);
  runTimers();
  assert.equal(refreshes(), 1);
});

test("events from a replaced channel are ignored", () => {
  const { channels, statuses, controller, runTimers, refreshes } = setup();
  controller.switchTo("customers");
  controller.switchTo("dishes");
  const before = statuses.length;
  channels[0].change();
  channels[0].report("SUBSCRIBED");
  channels[0].report("CHANNEL_ERROR");
  runTimers();
  assert.equal(refreshes(), 0);
  assert.equal(statuses.length, before);
});

test("stop unsubscribes, cancels timers and silences late events", () => {
  const { channels, removed, statuses, controller, timers, refreshes, runTimers } = setup();
  controller.switchTo("customers");
  channels[0].change();
  controller.stop();
  assert.deepEqual(removed, [channels[0]]);
  assert.equal(timers.size, 0);
  assert.equal(statuses.at(-1), "idle");
  channels[0].change();
  channels[0].report("SUBSCRIBED");
  runTimers();
  assert.equal(refreshes(), 0);
  assert.equal(statuses.at(-1), "idle");
});

test("a dropped connection shows offline, retries with backoff and refreshes on reconnect", () => {
  const { channels, statuses, controller, runTimers, refreshes, timers } = setup();
  controller.switchTo("customers");
  channels[0].report("SUBSCRIBED");
  runTimers(); // Initial catch-up refresh.
  assert.equal(refreshes(), 1);

  channels[0].report("CHANNEL_ERROR");
  assert.equal(statuses.at(-1), "offline");
  assert.equal([...timers.values()][0].delay, 5000);
  runTimers();
  assert.equal(channels.length, 2);

  channels[1].report("TIMED_OUT");
  assert.equal([...timers.values()][0].delay, 10000);
  runTimers();
  channels[2].report("SUBSCRIBED");
  assert.equal(statuses.at(-1), "live");
  runTimers();
  assert.equal(refreshes(), 2);
});

test("repeated error reports schedule one retry, not several", () => {
  const { channels, controller, timers } = setup();
  controller.switchTo("customers");
  channels[0].report("CHANNEL_ERROR");
  channels[0].report("CLOSED");
  assert.equal(timers.size, 1);
});

test("browser offline and online events close and reopen the channel", () => {
  const { channels, removed, statuses, controller } = setup();
  controller.switchTo("customers");
  channels[0].report("SUBSCRIBED");
  controller.networkChanged(false);
  assert.equal(statuses.at(-1), "offline");
  assert.deepEqual(removed, [channels[0]]);
  controller.networkChanged(true);
  assert.equal(channels.length, 2);
  assert.equal(statuses.at(-1), "connecting");
});

test("network events after stop do nothing", () => {
  const { channels, controller } = setup();
  controller.switchTo("customers");
  controller.stop();
  controller.networkChanged(true);
  assert.equal(channels.length, 1);
});
