// Single "kitchen sounds" consent shared by the hero entry button, the page
// button, the hover preview and the preview dialog. Off by default and kept for
// this page view only: it is turned on only by an explicit click (a user
// gesture), so "on" always means the browser has had the interaction it needs
// for audible playback. If a browser still refuses, callers set it back to off
// with reason "blocked", so the UI never claims sound that isn't playing.

const listeners = new Set();
let on = false;

export const isSoundOn = () => on;

/** @param {boolean} next @param {{reason?: "user" | "blocked"}} [meta] */
export function setSoundOn(next, { reason = "user" } = {}) {
  if (next === on) return;
  on = next;
  listeners.forEach((fn) => fn(on, reason));
}

export const onSoundChange = (fn) => listeners.add(fn);
