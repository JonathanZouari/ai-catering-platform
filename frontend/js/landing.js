import { api } from "/js/api.js";

// ---------- Mobile navigation ----------
const toggle = document.querySelector(".nav-toggle");
const nav = document.getElementById("site-nav");

function setNav(open) {
  toggle.setAttribute("aria-expanded", String(open));
  nav.classList.toggle("is-open", open);
}

toggle.addEventListener("click", () => setNav(toggle.getAttribute("aria-expanded") !== "true"));
nav.addEventListener("click", (e) => { if (e.target.closest("a")) setNav(false); });
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
    setNav(false);
    toggle.focus();
  }
});

// ---------- Centerpiece dish tilt ----------
// Only on large screens with a precise pointer and motion allowed; otherwise the CSS still pose stays.
const hero = document.querySelector(".hero");
const dish = document.querySelector(".dish");
const canTilt = matchMedia("(min-width: 1024px) and (hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)");
const target = { x: 0, y: 0 };
const current = { x: 0, y: 0 };
let frame = 0;

function step() {
  current.x += (target.x - current.x) * 0.09;
  current.y += (target.y - current.y) * 0.09;
  dish.style.setProperty("--tx", current.x.toFixed(4));
  dish.style.setProperty("--ty", current.y.toFixed(4));
  const settled = Math.abs(target.x - current.x) < 0.001 && Math.abs(target.y - current.y) < 0.001;
  frame = settled ? 0 : requestAnimationFrame(step);
}

function aim(x, y) {
  target.x = x;
  target.y = y;
  if (!frame) frame = requestAnimationFrame(step);
}

const clamp = (n) => Math.max(-1, Math.min(1, n));

hero.addEventListener("pointermove", (e) => {
  if (!canTilt.matches || e.pointerType !== "mouse") return;
  const r = dish.getBoundingClientRect();
  aim(clamp((e.clientX - (r.left + r.width / 2)) / r.width), clamp((e.clientY - (r.top + r.height / 2)) / r.height));
});
hero.addEventListener("pointerleave", () => aim(0, 0));
canTilt.addEventListener("change", () => aim(0, 0));

// ---------- Turning the dish (drag / swipe) ----------
// The plate's surface follows the pointer around its center. On release it coasts and slows to a stop,
// unless reduced motion is on, in which case it stops where it was let go.
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
const spin = { angle: 0, velocity: 0, pointer: null, lastAngle: 0, lastTime: 0, frame: 0, coastFrom: 0 };
const MAX_VELOCITY = 0.75; // deg per ms; caps any coast at about a third of a turn
const FRICTION = 0.9; // velocity kept per 60 Hz frame; a brisk flick coasts roughly a quarter turn

function renderSpin() {
  dish.style.setProperty("--spin", `${spin.angle.toFixed(2)}deg`);
}

function pointerAngle(e) {
  const r = dish.getBoundingClientRect();
  const dx = e.clientX - (r.left + r.width / 2);
  const dy = e.clientY - (r.top + r.height / 2);
  // Too close to the center the angle swings wildly, so ignore that zone.
  if (Math.hypot(dx, dy) < r.width * 0.08) return null;
  return (Math.atan2(dy, dx) * 180) / Math.PI;
}

function stopCoasting() {
  cancelAnimationFrame(spin.frame);
  spin.frame = 0;
}

function coast(now) {
  // Time only from rAF stamps; the first frame counts as one 60 Hz step.
  const dt = spin.coastFrom === null ? 16.67 : Math.min(Math.max(now - spin.coastFrom, 0), 50);
  spin.coastFrom = now;
  spin.angle += spin.velocity * dt;
  spin.velocity *= FRICTION ** (dt / 16.67);
  renderSpin();
  spin.frame = Math.abs(spin.velocity) > 0.004 ? requestAnimationFrame(coast) : 0;
}

dish.addEventListener("pointerdown", (e) => {
  if (e.button !== 0 || spin.pointer !== null) return;
  stopCoasting();
  spin.pointer = e.pointerId;
  spin.velocity = 0;
  spin.lastAngle = pointerAngle(e);
  spin.lastTime = e.timeStamp;
  dish.setPointerCapture(e.pointerId);
  dish.classList.add("is-dragging");
});

dish.addEventListener("pointermove", (e) => {
  if (e.pointerId !== spin.pointer) return;
  const a = pointerAngle(e);
  if (a === null || spin.lastAngle === null) {
    spin.lastAngle = a;
    return;
  }
  let delta = a - spin.lastAngle;
  if (delta > 180) delta -= 360;
  if (delta < -180) delta += 360;
  const dt = Math.max(e.timeStamp - spin.lastTime, 1);
  spin.velocity = Math.max(-MAX_VELOCITY, Math.min(MAX_VELOCITY, 0.7 * (delta / dt) + 0.3 * spin.velocity));
  spin.angle += delta;
  spin.lastAngle = a;
  spin.lastTime = e.timeStamp;
  renderSpin();
  if (Math.abs(delta) > 0.5) dish.classList.add("has-turned");
});

function release(e, withMomentum) {
  if (e.pointerId !== spin.pointer) return;
  spin.pointer = null;
  dish.classList.remove("is-dragging");
  // A pause before letting go means the user meant to stop, not to fling.
  const paused = e.timeStamp - spin.lastTime > 90;
  if (withMomentum && !paused && !reduceMotion.matches && Math.abs(spin.velocity) > 0.02) {
    spin.coastFrom = null;
    spin.frame = requestAnimationFrame(coast);
  }
}

dish.addEventListener("pointerup", (e) => release(e, true));
// The browser took over (e.g. the swipe turned into a vertical scroll): stop without coasting.
dish.addEventListener("pointercancel", (e) => release(e, false));

// ---------- Inquiry form ----------
const form = document.getElementById("inquiry-form");
const status = document.getElementById("inquiry-status");
const done = document.getElementById("inquiry-done");
const doneText = document.getElementById("inquiry-done-text");
const submit = form.querySelector('button[type="submit"]');

const today = new Date();
const isoToday = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
form.elements.event_date.min = isoToday;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const rules = {
  name: (v) => (v.trim() ? "" : "Enter your name."),
  email: (v) => (!v.trim() ? "Enter your email address." : EMAIL.test(v.trim()) ? "" : "Enter an email address like name@example.com."),
  phone: (v) => (!v.trim() || /^[\d\s()+\-.]{6,40}$/.test(v.trim()) ? "" : "Use digits, spaces, and + ( ) - only."),
  event_type: (v) => (v ? "" : "Choose the type of event."),
  event_date: (v) => (!v ? "Choose the event date." : v < isoToday ? "Choose a date from today onward." : ""),
  guests: (v) => {
    const n = Number(v);
    if (!v) return "Enter how many guests are coming.";
    return Number.isInteger(n) && n >= 1 && n <= 2000 ? "" : "Enter a whole number from 1 to 2000.";
  },
  fulfillment: (v) => (v ? "" : "Choose pickup or delivery."),
};

const errorId = { name: "f-name-error", email: "f-email-error", phone: "f-phone-error", event_type: "f-type-error", event_date: "f-date-error", guests: "f-guests-error", fulfillment: "f-fulfillment-error" };

function controlsFor(name) {
  const el = form.elements[name];
  return el instanceof RadioNodeList ? [...el] : [el];
}

function showError(name, message) {
  const err = document.getElementById(errorId[name]);
  err.textContent = message;
  err.hidden = !message;
  for (const el of controlsFor(name)) {
    if (message) {
      el.setAttribute("aria-invalid", "true");
      el.setAttribute("aria-describedby", errorId[name]);
    } else {
      el.removeAttribute("aria-invalid");
      el.removeAttribute("aria-describedby");
    }
  }
  return !message;
}

function validate(name) {
  return showError(name, rules[name](form.elements[name].value));
}

// Re-check a field once it has shown an error, so the message clears as soon as it's fixed.
form.addEventListener("input", (e) => {
  const name = e.target.name;
  if (rules[name] && controlsFor(name)[0].hasAttribute("aria-invalid")) validate(name);
});
form.addEventListener("focusout", (e) => {
  const name = e.target.name;
  if (rules[name] && e.target.type !== "radio" && e.target.value) validate(name);
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  status.hidden = true;

  const invalid = Object.keys(rules).filter((name) => !validate(name));
  if (invalid.length) {
    controlsFor(invalid[0])[0].focus();
    return;
  }

  const data = Object.fromEntries(new FormData(form));
  const payload = {
    name: data.name.trim(),
    email: data.email.trim(),
    phone: data.phone.trim() || null,
    event_type: data.event_type,
    event_date: data.event_date,
    guests: Number(data.guests),
    fulfillment: data.fulfillment,
    notes: data.notes.trim() || null,
  };

  submit.disabled = true;
  submit.textContent = "Sending inquiry…";
  try {
    await api("/api/inquiries", { method: "POST", body: JSON.stringify(payload) });
    const date = new Date(`${payload.event_date}T12:00:00`).toLocaleDateString("en", { weekday: "long", day: "numeric", month: "long" });
    doneText.textContent = `Thanks, ${payload.name}. We have your inquiry for ${payload.guests} guests on ${date}, and we'll reply to ${payload.email}.`;
    form.hidden = true;
    done.hidden = false;
    done.focus();
  } catch (err) {
    status.textContent = err.status === 422
      ? "Some details didn't go through. Check the fields above and send again."
      : err.status
        ? "Your inquiry wasn't sent because of a problem on our side. Try again in a few minutes."
        : "Your inquiry wasn't sent because the connection failed. Check your connection and send again.";
    status.hidden = false;
  } finally {
    submit.disabled = false;
    submit.textContent = "Send inquiry";
  }
});

document.getElementById("inquiry-again").addEventListener("click", () => {
  form.reset();
  done.hidden = true;
  form.hidden = false;
  form.elements.name.focus();
});
