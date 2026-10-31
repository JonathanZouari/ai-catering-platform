// Clip segments. Some source files hold more than one dish (the noodles clip is
// seconds 10.1–20 of a combined file whose first half is falafel). The original
// files stay untouched; these helpers keep playback, seeking and — most
// importantly — every *displayed frame* inside the dish's own segment.

const EPS = 0.08; // seconds of tolerance around segment edges

export const segStart = (clip) => clip?.startTime ?? 0;
export const segEnd = (clip) => clip?.endTime ?? Infinity;
export const isSegmented = (clip) => Boolean(clip && (clip.startTime || Number.isFinite(clip.endTime)));

/**
 * Binds a <video> to whatever clip `getClip()` returns.
 *  - loadedmetadata / seeking / timeupdate clamp currentTime into the segment;
 *    reaching the segment end pauses and calls `onEnd`.
 *  - Frames outside the segment are never shown: the element gets
 *    `.is-off-segment` (opacity 0 in CSS) until a presented frame lies inside it.
 * Returns `mask()`, to call before changing src or seeking (hides the picture
 * until the first correct frame is presented).
 */
export function bindSegment(video, getClip, { onEnd } = {}) {
  const inSegment = (t) => {
    const clip = getClip();
    return !clip || (t >= segStart(clip) - EPS && t <= Math.min(segEnd(clip), video.duration || Infinity) + EPS);
  };

  const clamp = () => {
    const clip = getClip();
    if (!clip) return;
    const start = segStart(clip);
    const end = segEnd(clip);
    if (video.currentTime < start - EPS) {
      mask();
      video.currentTime = start;
    } else if (video.currentTime >= end) {
      video.pause();
      video.currentTime = Math.max(start, end - 0.05);
      onEnd?.();
    }
  };
  video.addEventListener("loadedmetadata", () => {
    if (getClip()) video.currentTime = segStart(getClip());
  });
  video.addEventListener("seeking", clamp);
  video.addEventListener("timeupdate", clamp);

  const show = (t) => video.classList.toggle("is-off-segment", !inSegment(t));

  // Frame-accurate path: check the media time of every frame actually presented.
  if ("requestVideoFrameCallback" in HTMLVideoElement.prototype) {
    let handle = 0;
    const arm = () => {
      if (handle) return;
      handle = video.requestVideoFrameCallback((_now, meta) => {
        handle = 0;
        show(meta.mediaTime);
        arm();
      });
    };
    // A new source drops pending callbacks; re-arm whenever frames may flow again.
    video.addEventListener("emptied", () => {
      if (handle) video.cancelVideoFrameCallback(handle);
      handle = 0;
    });
    ["loadeddata", "play", "seeked"].forEach((type) => video.addEventListener(type, arm));
    arm();
  } else {
    ["loadeddata", "seeked", "timeupdate"].forEach((type) => video.addEventListener(type, () => show(video.currentTime)));
  }

  function mask() {
    video.classList.add("is-off-segment");
  }
  return { mask };
}
