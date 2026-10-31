// Kitchen preparation preview dialog. Two modes:
//  - "video": an AI-generated illustrative clip (only dishes with `video`).
//    Plays inline; its own soundtrack is audible only when the user has enabled
//    "kitchen sounds". Synthesized sound is never used in this mode.
//  - "illustration": the SVG scene with an optional synthesized sound (~6 s).
// Native <dialog> gives focus containment and Esc. Close, switching dishes,
// and hiding the tab stop everything; a session token drops stale play() results.

import { SCENES } from "./kitchen-scenes.js";
import * as sound from "./kitchen-sound.js";
import { isSoundOn, setSoundOn, onSoundChange } from "./sound-pref.js";
import { bindSegment, isSegmented, segEnd, segStart } from "./video-segment.js";

const STAGE_MS = [1900, 2400, 1700]; // illustration total 6000 ms
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

const TEXT = {
  video: {
    eyebrow: "וידאו הכנה להמחשה · נוצר בבינה מלאכותית",
    badge: "וידאו שנוצר ב־AI · לא צולם במטבח של העסק",
    disclaimer:
      "הווידאו נוצר בבינה מלאכותית לצורך המחשה בלבד. הוא אינו צילום של המטבח, של העובדים או של מנה אמיתית של העסק. הקול מושמע רק אם הפעלתם את צלילי המטבח.",
  },
  illustration: {
    eyebrow: "הדמיה מאוירת · לא וידאו",
    badge: "אנימציה מאוירת · לא וידאו אמיתי",
    disclaimer:
      "המחשה בלבד: האיור והצליל (מסונתז בדפדפן) אינם מתעדים את ההכנה בפועל. הצליל מתנגן רק אם הפעלתם את צלילי המטבח.",
  },
};

export function initKitchenPreview({ onAdd, getQty }) {
  const dialog = document.getElementById("kitchen-preview");
  const $ = (sel) => dialog.querySelector(sel);
  const titleEl = $("#kp-title");
  const sceneEl = $(".kp__scene");
  const stepEls = [...dialog.querySelectorAll(".kp__steps li")];
  const statusEl = $(".kp__status");
  const progressEl = $(".kp__progress span");
  const soundBtn = $("[data-kp=sound]");
  const addBtn = $("[data-kp=add]");
  const video = $(".kp__video");
  const playBtn = $("[data-kp=play]");

  let dish = null;
  let scene = null;
  let mode = null;
  let opener = null;
  let timers = [];
  let stage = -1;
  let session = 0; // bumps on every open/close; async results from older sessions are ignored

  const clearTimers = () => {
    timers.forEach(clearTimeout);
    timers = [];
  };

  const toggleBtn = $("[data-kp=toggle]");
  const endedText = "הווידאו הסתיים. אפשר לצפות שוב או להוסיף לבחירה.";
  // Keeps playback, seeking and every shown frame inside this dish's segment.
  const segment = bindSegment(video, () => (mode === "video" ? dish?.video : null), {
    onEnd: () => (statusEl.textContent = endedText),
  });
  // ---------- shared ----------
  function renderSoundBtn() {
    const on = mode === "video" ? !video.muted : isSoundOn();
    soundBtn.setAttribute("aria-pressed", String(on));
    const what = mode === "video" ? "קול הווידאו" : "צליל";
    soundBtn.querySelector(".kp__sound-label").textContent = `${what}: ${on ? "פעיל" : "כבוי"}`;
  }

  function renderAddBtn() {
    const qty = getQty(dish.id);
    addBtn.textContent = qty ? `הוספה נוספת (${qty} בבחירה)` : "הוספה לבחירה";
  }

  function setMode(next) {
    mode = next;
    dialog.dataset.mode = next;
    $(".kp__eyebrow-text").textContent = TEXT[next].eyebrow;
    $(".kp__badge").textContent = TEXT[next].badge;
    $("#kp-disclaimer").textContent = TEXT[next].disclaimer;
  }

  // Stops all playback from the current dish (video, timers, synthesized sound).
  function stopAll() {
    session++;
    clearTimers();
    sound.stop(0.05);
    video.pause();
    playBtn.hidden = true;
    stage = -1;
  }

  // ---------- video mode ----------
  function showPlayFallback(message) {
    playBtn.hidden = false;
    statusEl.textContent = message;
  }

  function playVideo({ fromStart = true } = {}) {
    const token = session;
    playBtn.hidden = true;
    if (fromStart) {
      segment.mask();
      video.currentTime = segStart(dish.video);
    }
    const p = video.play();
    if (!p) return;
    p.then(
      () => {
        if (token !== session || !dialog.open) video.pause(); // stale: dialog closed or switched
        else statusEl.textContent = video.muted ? "הווידאו מתנגן ללא קול." : "הווידאו מתנגן עם קול.";
      },
      () => {
        if (token !== session) return;
        if (!video.muted) {
          // Audible playback refused: fall back to muted and report sound as off.
          video.muted = true;
          setSoundOn(false, { reason: "blocked" });
          renderSoundBtn();
          playVideo({ fromStart: false });
        } else {
          showPlayFallback("הדפדפן לא הפעיל את הווידאו אוטומטית. לחצו על \"הפעלת הווידאו\".");
        }
      },
    );
  }

  function openVideo() {
    setMode("video");
    $(".kp__method").textContent = "";
    sceneEl.innerHTML = "";
    video.muted = !isSoundOn(); // opening is a click/tap, so audible playback is allowed
    segment.mask();
    video.src = dish.video.src;
    // A segment of a combined file: native controls would expose the whole file
    // (and the other dish), so use our own play/pause instead.
    const segmented = isSegmented(dish.video);
    video.controls = !segmented;
    toggleBtn.hidden = !segmented;
    renderSoundBtn();
    if (reducedMotion.matches) {
      showPlayFallback("הפעלה ידנית: מופעלת אצלכם הגדרת הפחתת תנועה.");
    } else {
      statusEl.textContent = "טוען וידאו…";
      playVideo({ fromStart: false });
    }
  }

  video.addEventListener("ended", () => {
    if (mode === "video") statusEl.textContent = endedText;
  });
  const renderToggle = () => (toggleBtn.textContent = video.paused ? "המשך ניגון" : "השהיה");
  video.addEventListener("play", renderToggle);
  video.addEventListener("pause", renderToggle);
  toggleBtn.addEventListener("click", () => {
    if (!video.paused) return video.pause();
    const atEnd = video.currentTime >= Math.min(segEnd(dish.video), video.duration || Infinity) - 0.1;
    playVideo({ fromStart: atEnd });
  });
  video.addEventListener("error", () => {
    if (mode === "video" && video.getAttribute("src")) {
      playBtn.hidden = true;
      statusEl.textContent = "לא ניתן לטעון את הווידאו כרגע. אפשר להוסיף את המנה גם בלי לצפות.";
    }
  });
  // Keep our toggle in sync with the native controls' mute button.
  video.addEventListener("volumechange", () => mode === "video" && renderSoundBtn());
  playBtn.addEventListener("click", () => playVideo({ fromStart: video.ended }));

  // ---------- illustration mode ----------
  function setProgress(fraction, ms) {
    progressEl.style.transition = ms ? `transform ${ms}ms linear` : "none";
    progressEl.style.transform = `scaleX(${fraction})`;
  }

  function setStage(i, { withSound = true } = {}) {
    stage = i;
    sceneEl.querySelectorAll(".layer").forEach((layer, idx) => layer.classList.toggle("is-active", idx === i));
    stepEls.forEach((li, idx) => {
      if (idx === i) li.setAttribute("aria-current", "step");
      else li.removeAttribute("aria-current");
      li.classList.toggle("is-done", idx < i);
    });
    statusEl.textContent = `שלב ${i + 1} מתוך 3: ${scene.stages[i]}`;
    if (i === 1 && withSound && isSoundOn()) sound.start(scene.sound);
    if (i === 2) sound.stop(1.2); // gentle fade while plating
  }

  function finish() {
    stage = 3;
    stepEls.forEach((li) => {
      li.removeAttribute("aria-current");
      li.classList.add("is-done");
    });
    statusEl.textContent = "המנה מוכנה להגשה. אפשר לצפות שוב או להוסיף לבחירה.";
  }

  function playIllustration() {
    clearTimers();
    sound.stop();
    sceneEl.classList.remove("is-instant");
    sceneEl.querySelectorAll(".layer").forEach((l) => l.classList.remove("is-active"));
    setProgress(0, 0);
    void sceneEl.offsetWidth; // restart CSS animations
    let t = 0;
    STAGE_MS.forEach((ms, i) => {
      timers.push(
        setTimeout(() => {
          setStage(i);
          setProgress((i + 1) / STAGE_MS.length, ms);
        }, t),
      );
      t += ms;
    });
    timers.push(setTimeout(finish, t));
  }

  function openIllustration() {
    setMode("illustration");
    scene = SCENES[dish.prep.type];
    toggleBtn.hidden = true;
    video.removeAttribute("src");
    video.load();
    $(".kp__method").textContent = `· סוג הכנה: ${scene.label}`;
    stepEls.forEach((li, i) => (li.querySelector(".kp__step-text").textContent = scene.stages[i]));
    sceneEl.innerHTML = `<svg viewBox="0 0 320 220" aria-hidden="true" focusable="false">${scene.svg(dish.prep)}</svg>`;
    renderSoundBtn();
    if (isSoundOn()) sound.prime(); // we are inside the user's click/keypress
    playIllustration();
  }

  // ---------- controls ----------
  function replay() {
    if (mode === "video") playVideo();
    else playIllustration();
  }

  function skip() {
    if (mode === "video") {
      // Jump to the plated ending and hold it.
      session++;
      video.pause();
      const end = Math.min(segEnd(dish.video), video.duration);
      if (Number.isFinite(end)) video.currentTime = Math.max(segStart(dish.video), end - 0.3);
      playBtn.hidden = true;
      statusEl.textContent = "דילגתם לסוף הווידאו: המנה מוגשת.";
      return;
    }
    clearTimers();
    sound.stop();
    sceneEl.classList.add("is-instant");
    setStage(2, { withSound: false });
    setProgress(1, 0);
    finish();
  }

  function teardown() {
    // The close event is async; if the dialog was reopened meanwhile, keep the new session.
    if (dialog.open) return;
    stopAll();
    video.removeAttribute("src");
    video.load(); // release the media resource
    sceneEl.innerHTML = "";
    statusEl.textContent = "";
    setProgress(0, 0);
    if (opener?.isConnected) opener.focus();
    opener = null;
  }

  function open(nextDish, trigger) {
    stopAll(); // switching dishes, or anything left from a previous open
    dish = nextDish;
    opener = trigger ?? document.activeElement;
    titleEl.textContent = dish.name;
    renderAddBtn();
    if (!dialog.open) dialog.showModal();
    if (dish.video) openVideo();
    else openIllustration();
  }

  // The dialog's sound button is the same "kitchen sounds" preference as the page button.
  soundBtn.addEventListener("click", () => {
    const want = mode === "video" ? video.muted : !isSoundOn();
    setSoundOn(want);
    applySound(want); // also when the preference was unchanged (e.g. muted after a refused play)
  });

  function applySound(on) {
    if (!dialog.open) return;
    if (mode === "video") {
      video.muted = !on;
    } else if (on) {
      sound.prime();
      if (stage === 1) sound.start(scene.sound);
    } else {
      sound.stop();
    }
    renderSoundBtn();
  }
  onSoundChange(applySound);
  $("[data-kp=replay]").addEventListener("click", replay);
  $("[data-kp=skip]").addEventListener("click", skip);
  $("[data-kp=close]").addEventListener("click", () => dialog.close());
  addBtn.addEventListener("click", () => {
    onAdd(dish.id);
    renderAddBtn();
  });
  dialog.addEventListener("close", teardown);
  // Click on the backdrop (outside the panel) closes.
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) dialog.close();
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden || !dialog.open) return;
    if (mode === "video") {
      session++; // drop any pending play()
      video.pause();
      showPlayFallback("הווידאו הושהה כשעברתם ללשונית אחרת.");
    } else if (stage >= 0 && stage < 3) {
      skip();
    }
  });

  return { open };
}
