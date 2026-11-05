import assert from "node:assert/strict";
import { test } from "node:test";

import { createStaffGate } from "../js/auth-gate.js";

const jwt = (payload) => `h.${Buffer.from(JSON.stringify(payload)).toString("base64url")}.s`;
const staffToken = jwt({ app_metadata: { role: "catering_owner" } });
const plainToken = jwt({ app_metadata: {} });
const staffUser = (id) => ({ id, email: `${id}@example.com`, app_metadata: { role: "catering_owner" } });
const sessionOf = (id, token = staffToken) => ({ access_token: token, user: { id } });

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

// Each auth call waits until the test answers it, in whatever order the test chooses.
function setup() {
  const pending = { getUser: [], getSession: [], refreshSession: [], signOut: [] };
  const log = [];
  const call = (name) => (arg) => {
    const waiter = deferred();
    pending[name].push({ ...waiter, arg });
    return waiter.promise;
  };
  const client = {
    auth: {
      getUser: call("getUser"),
      getSession: call("getSession"),
      refreshSession: call("refreshSession"),
      signOut: call("signOut"),
    },
  };
  const screen = (name) => (arg) => log.push([name, arg]);
  const ui = {
    closeShell: screen("closeShell"),
    showApp: (user, role) => log.push(["showApp", user.id, role]),
    showChecking: screen("showChecking"),
    showDenied: screen("showDenied"),
    showLogin: screen("showLogin"),
    showUnverified: screen("showUnverified"),
  };
  return { client, pending, log, gate: createStaffGate({ client, ui }) };
}

const settle = () => new Promise((resolve) => setImmediate(resolve));
const screens = (log) => log.map((entry) => entry[0]).filter((name) => name !== "closeShell");
const answerUser = async (pending, user, index = pending.getUser.length - 1) => {
  pending.getUser[index].resolve({ data: { user }, error: null });
  await settle();
};
const answerSession = async (pending, session, index = pending.getSession.length - 1) => {
  pending.getSession[index].resolve({ data: { session }, error: null });
  await settle();
};
async function grant(env, id = "a") {
  env.gate.verify();
  await answerUser(env.pending, staffUser(id));
  await answerSession(env.pending, sessionOf(id));
}

test("a verified staff user reaches the app", async () => {
  const env = setup();
  await grant(env);
  assert.deepEqual(env.log.at(-1), ["showApp", "a", "catering_owner"]);
});

test("a delayed getUser after sign-out cannot open the app", async () => {
  const env = setup();
  env.gate.verify();
  env.gate.handleAuthEvent("SIGNED_OUT", null);
  await answerUser(env.pending, staffUser("a"));
  assert.deepEqual(screens(env.log), ["showLogin"]);
  assert.equal(env.pending.getSession.length, 0);
});

test("a delayed getSession after sign-out cannot open the app", async () => {
  const env = setup();
  env.gate.verify();
  await answerUser(env.pending, staffUser("a"));
  env.gate.handleAuthEvent("SIGNED_OUT", null);
  await answerSession(env.pending, sessionOf("a"));
  assert.deepEqual(screens(env.log), ["showLogin"]);
});

test("a delayed refreshSession after sign-out cannot open the app", async () => {
  const env = setup();
  env.gate.verify();
  await answerUser(env.pending, staffUser("a"));
  await answerSession(env.pending, sessionOf("a", plainToken));
  env.gate.handleAuthEvent("SIGNED_OUT", null);
  env.pending.refreshSession[0].resolve({ data: { session: sessionOf("a") }, error: null });
  await settle();
  assert.deepEqual(screens(env.log), ["showLogin"]);
});

test("the previous account's late check cannot replace the new account's app", async () => {
  const env = setup();
  env.gate.verify();
  env.gate.handleAuthEvent("SIGNED_IN", sessionOf("b"));
  assert.equal(env.pending.getUser.length, 2, "the new account gets its own check");

  await answerUser(env.pending, staffUser("b"), 1);
  await answerSession(env.pending, sessionOf("b"));
  await answerUser(env.pending, staffUser("a"), 0);

  assert.deepEqual(screens(env.log), ["showChecking", "showApp"]);
  assert.deepEqual(env.log.at(-1), ["showApp", "b", "catering_owner"]);
  assert.equal(env.pending.getSession.length, 1, "the stale check stopped");
});

test("switching accounts closes the old shell before any check finishes", async () => {
  const env = setup();
  await grant(env, "a");
  env.log.length = 0;
  env.gate.handleAuthEvent("SIGNED_IN", sessionOf("b"));
  assert.deepEqual(env.log.map((entry) => entry[0]), ["closeShell", "showChecking"]);
});

test("signing out invalidates a running check immediately", async () => {
  const env = setup();
  env.gate.verify();
  const signOut = env.gate.signOut();
  await answerUser(env.pending, staffUser("a"));
  assert.deepEqual(screens(env.log), []);
  env.pending.signOut[0].resolve({ error: null });
  assert.deepEqual(await signOut, {});
  assert.deepEqual(screens(env.log), ["showLogin"]);
});

test("a refused sign-out reports the error and keeps the session's screen", async () => {
  const env = setup();
  await grant(env);
  env.log.length = 0;
  const signOut = env.gate.signOut();
  const failure = { message: "network" };
  env.pending.signOut[0].resolve({ error: failure });
  assert.deepEqual(await signOut, { error: failure });
  assert.deepEqual(env.log, []);
});

test("a failed revalidation locks the staff screens", async () => {
  const env = setup();
  await grant(env);
  env.log.length = 0;
  env.gate.handleAuthEvent("TOKEN_REFRESHED", sessionOf("a"));
  const failure = { name: "AuthRetryableFetchError", status: 0, message: "Failed to fetch" };
  env.pending.getUser.at(-1).resolve({ data: { user: null }, error: failure });
  await settle();
  assert.deepEqual(env.log.map((entry) => entry[0]), ["closeShell", "showUnverified"]);
  assert.equal(env.log[1][1], failure);
});

test("a thrown auth call also fails closed", async () => {
  const env = setup();
  await grant(env);
  env.log.length = 0;
  env.gate.verify();
  env.pending.getUser.at(-1).reject(new Error("boom"));
  await settle();
  assert.deepEqual(env.log.map((entry) => entry[0]), ["closeShell", "showUnverified"]);
});

test("a withdrawn role closes the shell and shows the denied screen", async () => {
  const env = setup();
  await grant(env);
  env.log.length = 0;
  env.gate.handleAuthEvent("TOKEN_REFRESHED", sessionOf("a"));
  await answerUser(env.pending, { id: "a", app_metadata: {} });
  assert.deepEqual(env.log.map((entry) => entry[0]), ["closeShell", "showDenied"]);
  env.gate.handleAuthEvent("TOKEN_REFRESHED", sessionOf("a"));
  assert.equal(env.pending.getUser.length, 2, "no more checks once access is closed");
});

test("a stored session for another user is never granted", async () => {
  const env = setup();
  env.gate.verify();
  await answerUser(env.pending, staffUser("a"));
  await answerSession(env.pending, sessionOf("b"));
  assert.deepEqual(screens(env.log), ["showUnverified"]);
});

test("a missing stored session is never granted", async () => {
  const env = setup();
  env.gate.verify();
  await answerUser(env.pending, staffUser("a"));
  await answerSession(env.pending, null);
  assert.deepEqual(screens(env.log), ["showUnverified"]);
});

test("revalidating the same user keeps the shell open", async () => {
  const env = setup();
  await grant(env);
  env.log.length = 0;
  env.gate.handleAuthEvent("TOKEN_REFRESHED", sessionOf("a"));
  await answerUser(env.pending, staffUser("a"));
  await answerSession(env.pending, sessionOf("a"));
  assert.deepEqual(env.log, []);
});

test("a token event for another user is treated as an account switch", async () => {
  const env = setup();
  await grant(env, "a");
  env.log.length = 0;
  env.gate.handleAuthEvent("TOKEN_REFRESHED", sessionOf("b"));
  assert.deepEqual(env.log.map((entry) => entry[0]), ["closeShell", "showChecking"]);
});

test("callers during a running check share one request", () => {
  const env = setup();
  env.gate.verify();
  env.gate.verify();
  assert.equal(env.pending.getUser.length, 1);
});

test("an expired session returns to login with an explanation", async () => {
  const env = setup();
  await grant(env);
  env.log.length = 0;
  env.gate.verify();
  env.pending.getUser.at(-1).resolve({ data: { user: null }, error: { status: 401, message: "expired" } });
  await settle();
  assert.deepEqual(env.log.map((entry) => entry[0]), ["closeShell", "showLogin"]);
  assert.ok(env.log[1][1].message);
  assert.deepEqual(env.pending.signOut[0].arg, { scope: "local" });
});

test("a token without the role is refreshed once, then denied without looping", async () => {
  const env = setup();
  env.gate.verify();
  await answerUser(env.pending, staffUser("a"));
  await answerSession(env.pending, sessionOf("a", plainToken));
  env.pending.refreshSession[0].resolve({ data: { session: sessionOf("a", plainToken) }, error: null });
  await settle();
  assert.deepEqual(screens(env.log), ["showDenied"]);
  env.gate.handleAuthEvent("TOKEN_REFRESHED", sessionOf("a", plainToken));
  assert.equal(env.pending.refreshSession.length, 1);
});

test("a freshly granted role passes after one refresh", async () => {
  const env = setup();
  env.gate.verify();
  await answerUser(env.pending, staffUser("a"));
  await answerSession(env.pending, sessionOf("a", plainToken));
  env.pending.refreshSession[0].resolve({ data: { session: sessionOf("a") }, error: null });
  await settle();
  assert.deepEqual(env.log.at(-1), ["showApp", "a", "catering_owner"]);
});

test("start shows login without a session and is ignored after a newer event", async () => {
  const empty = setup();
  const started = empty.gate.start();
  empty.pending.getSession[0].resolve({ data: { session: null }, error: null });
  await started;
  assert.deepEqual(screens(empty.log), ["showLogin"]);

  const raced = setup();
  raced.gate.start();
  raced.gate.handleAuthEvent("SIGNED_OUT", null);
  raced.pending.getSession[0].resolve({ data: { session: sessionOf("a") }, error: null });
  await settle();
  assert.equal(raced.pending.getUser.length, 0);
  assert.deepEqual(screens(raced.log), ["showLogin"]);
});
