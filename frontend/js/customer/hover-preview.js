// Floating, non-modal video preview for dishes that have a `video`.
//  - Activation: hovering the dish NAME (fine pointers) starts it immediately.
//  - Placement: in the free space of the dish row, between the dish text and the
//    price/selection column — never over the name or the controls.
//  - Dismissal: leaving the whole row (and the preview) closes it after a short
//    grace, so the pointer can travel across the row into the preview.
//  - Keyboard: visible focus on the name shows the same preview without moving
//    focus; Esc dismisses; Enter opens the full dialog. Touch: a tap opens the dialog.
// Muted unless kitchen sounds were enabled by an explicit click. One <video> only;
// a token discards play() results from an earlier show. Segment-aware.

import { isSoundOn, setSoundOn, onSoundChange } from "./sound-pref.js";
import { bindSegment, segStart } from "./video-segment.js";

const INTENT_MS = 0; // "immediately" on the name
const GRACE_MS = 220;
const MAX_W = 540;
const MIN_W = 300;
const GAP = 24; // clear space kept around the name and the selection column

const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

export function initHoverPreview({ grid, getDish, onOpen, isBlocked }) {
  const box = document.createElement("div");
  box.className = "hover-preview";
  // Mouse convenience only: keyboard and screen-reader users get the same video
  // and sound control through the full dialog and the page-level button.
  box.setAttribute("aria-hidden", "true");
  // Layers: the masked (edge-faded) video, a hit area over its sharp centre,
  // and an unmasked UI layer. Faded margins take no pointer events.
  box.innerHTML = `
    <div class="hover-preview__media"><video muted playsinline preload="none" tabindex="-1"></video></div>
    <div class="hover-preview__hit"></div>
    <div class="hover-preview__ui">
      <span class="hover-preview__label">וידאו AI להמחשה</span>
      <button type="button" class="hover-preview__close" tabindex="-1" aria-label="סגירת התצוגה הצפה"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></button>
      <button type="button" class="hover-preview__sound" tabindex="-1"></button>
      <span class="hover-preview__hint">לחצו לתצוגה מלאה</span>
    </div>`;
  document.body.append(box);
  const video = box.querySelector("video");
  const soundBtn = box.querySelector(".hover-preview__sound");
  const closeBtn = box.querySelector(".hover-preview__close");

  let active = null; // { card, dish } currently shown
  let pending = null; // card waiting for the intent delay
  let showTimer = 0;
  let hideTimer = 0;
  let token = 0;

  const segment = bindSegment(video, () => active?.dish.video);
  const visible = () => box.classList.contains("is-visible");

  function renderSound() {
    soundBtn.textContent = video.muted ? "הפעל צלילי מטבח" : "השתקה";
    soundBtn.classList.toggle("is-on", !video.muted);
  }

  // Free zone of the row: from the selection column's inner edge to the
  // leftmost line of dish text (RTL: text on the right, controls on the left).
  function place(card) {
    const row = card.getBoundingClientRect();
    const aside = card.querySelector(".dish-card__aside").getBoundingClientRect();
    const name = card.querySelector(".dish-name-trigger").getBoundingClientRect();
    const textLeft = Math.min(
      ...[...card.querySelectorAll(".dish-card__main > *")].map((el) => {
        const r = document.createRange();
        r.selectNodeContents(el);
        return r.getBoundingClientRect().left || el.getBoundingClientRect().left;
      }),
    );
    let zoneL = aside.right + GAP;
    let zoneR = textLeft - GAP;
    // Not enough room beside all the text: allow covering the description, never the name.
    if (zoneR - zoneL < MIN_W) zoneR = name.left - GAP;
    let w;
    let left;
    let top;
    if (zoneR - zoneL >= MIN_W * 0.85) {
      // Faded margins (~13% each side) may spill slightly past the zone edges.
      w = Math.min(MAX_W, (zoneR - zoneL) * 1.12);
      left = zoneL + (zoneR - zoneL - w) / 2;
      top = row.top + row.height / 2 - (w * 9) / 16 / 2;
    } else {
      // Narrow windows: under the name, over the description only.
      w = Math.max(240, Math.min(420, row.width - 16));
      left = name.right - w;
      top = name.bottom + 8;
    }
    const h = (w * 9) / 16;
    left = Math.min(Math.max(8, left), innerWidth - w - 8);
    top = Math.min(Math.max(8, top), innerHeight - h - 8);
    box.style.inlineSize = `${Math.round(w)}px`;
    box.style.left = `${Math.round(left)}px`;
    box.style.top = `${Math.round(top)}px`;
  }

  function play(t) {
    video.play().then(
      () => {
        if (t !== token) video.pause(); // a newer show/hide happened meanwhile
      },
      () => {
        if (t !== token) return;
        if (!video.muted) {
          // Audible playback refused: say so truthfully and continue muted.
          video.muted = true;
          setSoundOn(false, { reason: "blocked" });
          renderSound();
          play(t);
        }
        // Muted playback refused too: the frame stays hidden until a correct one exists.
      },
    );
  }

  function show(card, dish) {
    clearTimeout(showTimer);
    pending = null;
    if (isBlocked()) return;
    const t = ++token;
    active = { card, dish };
    place(card);
    segment.mask(); // nothing is visible until a frame from this dish's segment is presented
    if (video.getAttribute("src") !== dish.video.src) video.src = dish.video.src;
    if (video.readyState > 0) video.currentTime = segStart(dish.video);
    video.muted = !isSoundOn();
    renderSound();
    box.classList.add("is-visible");
    card.classList.add("is-previewing");
    play(t);
  }

  function hide() {
    token++;
    clearTimeout(showTimer);
    clearTimeout(hideTimer);
    pending = null;
    active?.card.classList.remove("is-previewing");
    active = null;
    // Pause only: no seek while fading out, so no other frame can appear.
    video.pause();
    box.classList.remove("is-visible");
  }

  function intend(card) {
    clearTimeout(hideTimer);
    if (active?.card === card || pending === card) return;
    const dish = getDish(card.dataset.dish);
    if (active) hide(); // switching dishes: stop the old clip right away
    clearTimeout(showTimer);
    if (!dish?.video || reducedMotion.matches || isBlocked()) return;
    pending = card;
    showTimer = setTimeout(() => pending === card && show(card, dish), INTENT_MS);
  }

  function leaveSoon() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(hide, GRACE_MS);
  }

  const isFineMouse = (e) => e.pointerType === "mouse" && finePointer.matches;

  // ---- pointer: the name activates; the whole row keeps it open ----
  grid.addEventListener("pointerover", (e) => {
    if (!isFineMouse(e)) return;
    const trigger = e.target.closest(".dish-name-trigger");
    if (trigger) return intend(trigger.closest(".dish-card"));
    if (active && active.card.contains(e.target)) clearTimeout(hideTimer);
  });
  grid.addEventListener("pointerout", (e) => {
    if (!isFineMouse(e)) return;
    const card = e.target.closest(".dish-card");
    if (!card || card.contains(e.relatedTarget)) return;
    if (box.contains(e.relatedTarget)) return clearTimeout(hideTimer); // moved into the preview
    if (pending === card) {
      clearTimeout(showTimer);
      pending = null;
    }
    if (active?.card === card) leaveSoon();
  });

  // ---- pointer: the preview itself ----
  box.addEventListener("pointerenter", () => clearTimeout(hideTimer));
  box.addEventListener("pointerleave", (e) => {
    if (!active?.card.contains(e.relatedTarget)) leaveSoon();
  });
  box.addEventListener("click", (e) => {
    if (!active) return;
    if (soundBtn.contains(e.target)) {
      // This click is the user gesture that allows audible playback.
      setSoundOn(video.muted);
      return;
    }
    if (closeBtn.contains(e.target)) return hide();
    if (!e.target.closest(".hover-preview__hit")) return;
    const { card, dish } = active;
    hide();
    onOpen(dish, card.querySelector(".dish-name-trigger"));
  });

  // ---- keyboard: preview on visible focus, without moving focus ----
  grid.addEventListener("focusin", (e) => {
    const trigger = e.target.closest?.(".dish-name-trigger");
    if (trigger?.matches(":focus-visible")) intend(trigger.closest(".dish-card"));
  });
  grid.addEventListener("focusout", (e) => {
    const card = e.target.closest?.(".dish-card");
    if (card && !card.contains(e.relatedTarget) && (active?.card === card || pending === card)) hide();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && (visible() || pending)) hide();
  });

  // ---- global stops ----
  // Pointer previews close on scroll; a keyboard-focused dish keeps its preview
  // (focusing scrolls the row into view) and the preview follows the row.
  window.addEventListener(
    "scroll",
    () => {
      const keyboardOwned = (active?.card ?? pending)?.contains(document.activeElement);
      if (keyboardOwned) {
        if (active) place(active.card);
      } else if (visible() || pending) hide();
    },
    { passive: true },
  );
  window.addEventListener("resize", () => (visible() || pending) && hide());
  document.addEventListener("visibilitychange", () => document.hidden && hide());
  onSoundChange((on) => {
    if (!visible()) return;
    video.muted = !on;
    renderSound();
    if (on && video.paused) play(token);
  });

  return { stop: hide, isActive: () => visible() };
}
