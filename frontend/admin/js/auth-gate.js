// Decides which screen an auth state leads to. The client and screens are injected for tests.
//
// Every check carries a generation number. Signing out or changing account bumps it, so a
// getUser, getSession or refreshSession that answers late can never open a closed session.
// Any failed check closes the staff screens: access is kept only while the server confirms it.
import { isSessionInvalidError, staffRoleOf, tokenHasStaffRole } from "./helpers.js";

export function createStaffGate({ client, ui }) {
  let generation = 0;
  let inFlight = null;
  let currentUserId = null;

  function invalidate() {
    generation += 1;
    inFlight = null;
  }

  function closeAccess() {
    currentUserId = null;
    ui.closeShell();
  }

  function failClosed(error) {
    closeAccess();
    ui.showUnverified(error);
  }

  function expireSession() {
    invalidate();
    closeAccess();
    ui.showLogin({ message: "תוקף ההתחברות פג. יש להתחבר מחדש." });
    client.auth.signOut({ scope: "local" }).catch(() => {});
  }

  async function check(mine) {
    const stale = () => mine !== generation;

    // getUser asks the auth server. The stored session alone can be stale or tampered with.
    const { data, error } = await client.auth.getUser();
    if (stale()) return;
    if (error) {
      if (isSessionInvalidError(error)) expireSession();
      else failClosed(error);
      return;
    }

    const user = data.user;
    const role = staffRoleOf(user);
    if (!role) {
      closeAccess();
      ui.showDenied(user);
      return;
    }

    const { data: sessionData } = await client.auth.getSession();
    if (stale()) return;
    if (sessionData.session?.user?.id !== user.id) {
      failClosed({ message: "session changed during verification" });
      return;
    }

    // Row security reads the token, so a role granted after sign-in needs one fresh token.
    if (!tokenHasStaffRole(sessionData.session.access_token)) {
      const { data: refreshed, error: refreshError } = await client.auth.refreshSession();
      if (stale()) return;
      if (refreshError) {
        failClosed(refreshError);
        return;
      }
      if (refreshed.session?.user?.id !== user.id) {
        failClosed({ message: "session changed during verification" });
        return;
      }
      if (!tokenHasStaffRole(refreshed.session.access_token)) {
        closeAccess();
        ui.showDenied(user);
        return;
      }
    }

    if (currentUserId !== user.id) {
      closeAccess();
      currentUserId = user.id;
      ui.showApp(user, role);
    }
  }

  // Callers during a running check share it. Only invalidate starts a separate one.
  function verify() {
    if (inFlight) return inFlight;
    const mine = ++generation;
    const run = check(mine)
      .catch((error) => {
        if (mine === generation) failClosed(error);
      })
      .finally(() => {
        if (inFlight === run) inFlight = null;
      });
    inFlight = run;
    return run;
  }

  function switchAccount() {
    invalidate();
    closeAccess();
    ui.showChecking();
    return verify();
  }

  return {
    async start() {
      const mine = generation;
      const { data, error } = await client.auth.getSession();
      if (mine !== generation) return;
      if (error || !data.session) ui.showLogin();
      else await verify();
    },

    verify,

    handleAuthEvent(event, session) {
      if (event === "SIGNED_OUT") {
        invalidate();
        closeAccess();
        ui.showLogin();
      } else if (event === "SIGNED_IN") {
        if (session?.user?.id !== currentUserId) switchAccount();
      } else if ((event === "TOKEN_REFRESHED" || event === "USER_UPDATED") && currentUserId) {
        // A role can be withdrawn at any time, so each new token is checked with the server again.
        if (session?.user?.id !== currentUserId) switchAccount();
        else verify();
      }
    },

    // Returns the error when the server refused, leaving the session and the screen as they are.
    async signOut() {
      invalidate();
      const { error } = await client.auth.signOut();
      if (error) return { error };
      invalidate();
      closeAccess();
      ui.showLogin();
      return {};
    },
  };
}
