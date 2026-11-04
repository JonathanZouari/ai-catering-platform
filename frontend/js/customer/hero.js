// The homepage hero video, the agreed behaviour from the Stitch design.
// The footage ends in a bright streak, so it never loops natively. Two layers of the
// same video take turns: while the front layer plays, the back layer waits paused on
// its first frame. Just before the streak the back layer starts and fades in on top
// while the front keeps playing at full opacity underneath, so the picture never dips
// to a blank or solid colour. Then the old front is hidden, rewound, and waits its turn.
// Everything is timed from the video's own position, not from a clock.

const RATE = 0.6; // playback speed
const CUT = 4.15; // media seconds: last clean frame before the light streak
const XFADE = 0.6; // wall-clock seconds for the crossfade (keep short, to avoid doubled dishes)
const MARGIN = 0.1; // media seconds: the outgoing layer stops this far before CUT
const XFADE_AT = CUT - XFADE * RATE - MARGIN; // media time at which the crossfade starts

let stopCurrent = null;

// Starts the hero in `media` (a .hero-media element holding one <video>). Returns a stop function.
export function startHero(media) {
  stopCurrent?.();
  const first = media.querySelector(".hero-video");
  if (!first) return () => {};
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  // The file is downloaded once and both layers play the same in-memory copy; two
  // network <video>s would fetch it twice. Nothing is fetched with reduced motion.
  const SRC = first.dataset.src;
  let blobUrl = null;
  let loading = null;
  const second = first.cloneNode(true);
  second.classList.add("is-hidden");
  first.after(second);
  const layers = [first, second];
  let front = first;
  let back = second;
  const ready = new WeakMap(); // layer -> paused on frame 0 and decodable
  let state = "idle"; // idle | intro | playing | crossfading | stopped
  let rafId = 0;
  let timers = [];

  const loadOnce = () => {
    loading ??= fetch(SRC).then((response) => {
      if (!response.ok) throw new Error(`hero video ${response.status}`);
      return response.blob();
    }).then((blob) => {
      if (state === "stopped") throw new Error("hero stopped");
      blobUrl = URL.createObjectURL(blob);
      layers.forEach((video) => { video.preload = "auto"; video.src = blobUrl; });
    });
    return loading;
  };

  const later = (fn, ms) => timers.push(setTimeout(fn, ms));
  const clearTimers = () => { timers.forEach(clearTimeout); timers = []; };
  const setRate = (video) => { video.defaultPlaybackRate = RATE; video.playbackRate = RATE; };
  layers.forEach((video) => { video.loop = false; video.muted = true; setRate(video); });

  // Call fn once the video has put a new frame on screen (with a fallback for old browsers).
  const onFrame = (video, fn) => {
    let done = false;
    const once = () => { if (!done) { done = true; fn(); } };
    video.requestVideoFrameCallback?.(once);
    later(once, 300);
  };
  const hideNow = (video) => {
    video.classList.add("no-fade", "is-hidden");
    void video.offsetWidth;
    video.classList.remove("no-fade");
  };
  const showPoster = () => {
    clearTimers();
    cancelAnimationFrame(rafId);
    if (state !== "stopped") state = "idle";
    layers.forEach((video) => { video.pause(); hideNow(video); video.classList.remove("is-front"); });
    media.classList.remove("is-playing");
  };
  const play = (video) => {
    setRate(video);
    video.play()?.catch(showPoster);
  };

  // Park a layer paused on its first frame, then mark it ready.
  const prepare = (video) => {
    ready.set(video, false);
    video.pause();
    const settle = () => {
      if (video.readyState >= 2) ready.set(video, true);
      else video.addEventListener("loadeddata", settle, { once: true });
    };
    if (video.currentTime < 0.01 && !video.seeking) { settle(); return; }
    let seeked = false;
    video.addEventListener("seeked", () => { seeked = true; settle(); }, { once: true });
    video.currentTime = 0;
    later(() => { if (!seeked) { video.load(); settle(); } }, 1500);
  };

  const crossfade = () => {
    state = "crossfading";
    const incoming = back;
    const outgoing = front;
    incoming.classList.add("is-front");
    outgoing.classList.remove("is-front");
    play(incoming);
    onFrame(incoming, () => {
      if (state !== "crossfading") return;
      incoming.classList.remove("is-hidden");
      later(() => {
        if (state !== "crossfading") return;
        hideNow(outgoing);
        front = incoming;
        back = outgoing;
        prepare(back);
        state = "playing";
      }, XFADE * 1000 + 50);
    });
  };

  const watch = () => {
    cancelAnimationFrame(rafId);
    const tick = () => {
      if (state === "playing" || state === "intro") {
        const t = front.currentTime;
        if (state === "playing" && t >= XFADE_AT && ready.get(back)) crossfade();
        // The next layer isn't ready yet: hold on a clean frame rather than show the streak.
        else if (t >= CUT - 0.05 && !front.paused) front.pause();
      } else if (state === "crossfading" && front.currentTime >= CUT - 0.05 && !front.paused) {
        front.pause();
      }
      if (front.paused && state === "playing" && ready.get(back) && front.currentTime >= XFADE_AT) crossfade();
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
  };

  const fail = () => { layers.forEach((video) => video.classList.add("is-unavailable")); showPoster(); };

  const start = () => {
    if (reduce.matches || first.classList.contains("is-unavailable")) { showPoster(); return; }
    if (state !== "idle") return;
    front = first;
    back = second;
    front.classList.add("is-front");
    back.classList.remove("is-front");
    hideNow(back);
    state = "intro";
    watch();
    const go = () => {
      if (state !== "intro") return;
      if (front.currentTime > XFADE_AT) front.currentTime = 0;
      play(front);
      onFrame(front, () => {
        if (state !== "intro") return;
        // First appearance: a short fade from the poster, then the poster is retired.
        front.classList.remove("is-hidden");
        later(() => {
          if (state !== "intro") return;
          media.classList.add("is-playing");
          state = "playing";
        }, XFADE * 1000 + 50);
      });
      prepare(back);
    };
    // Until the download finishes, the poster stays.
    loadOnce().then(() => {
      if (front.readyState >= 2) go();
      else front.addEventListener("loadeddata", go, { once: true });
    }).catch(fail);
  };

  layers.forEach((video) => {
    video.addEventListener("error", () => { if (blobUrl) fail(); });
    video.addEventListener("ratechange", () => { if (video.playbackRate !== RATE) setRate(video); });
  });
  // In a background tab, pause rather than play through the streak unseen.
  const onVisibility = () => {
    if (state === "idle" || state === "stopped" || !blobUrl) return;
    if (document.hidden) front.pause();
    else if (front.currentTime < CUT - 0.05) play(front);
  };
  const onMotionChange = () => { if (reduce.matches) showPoster(); else start(); };
  document.addEventListener("visibilitychange", onVisibility);
  reduce.addEventListener("change", onMotionChange);

  if (reduce.matches) showPoster();
  else start();

  // Leaving the homepage stops the loop and frees the in-memory copy.
  const stop = () => {
    state = "stopped";
    showPoster();
    document.removeEventListener("visibilitychange", onVisibility);
    reduce.removeEventListener("change", onMotionChange);
    layers.forEach((video) => { video.removeAttribute("src"); video.load(); });
    if (blobUrl) URL.revokeObjectURL(blobUrl);
    if (stopCurrent === stop) stopCurrent = null;
  };
  stopCurrent = stop;
  return stop;
}
