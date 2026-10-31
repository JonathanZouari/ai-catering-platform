# Customer experience & kitchen preview: UX proposal (prototype)

Status: **Prototype / proposal**. It is not part of the confirmed MVP scope in `PRD.md`, and the business still has to accept it. The brand **"אש ומלח"** is a *proposed* identity for this prototype, and the page labels it that way.

## Visual direction

- **Mood:** editorial culinary. A cream navigation bar, a dark full-bleed hero, and a deep forest-green menu, with restrained champagne/brass accents and thin hairlines. Hebrew RTL; system fonts only (Frank Ruehl or David for headings, Segoe UI for text).
- **Hero:** a muted ambient loop of the schnitzel clip behind the headline.
  - The disclosure ("וידאו שנוצר ב־AI להמחשה, לא צולם במטבח של העסק") sits above the dark overlay, in its own row, away from the buttons.
  - The loop is never audible. It pauses when offscreen, when the tab is hidden, while the full window is open, and on request (a "השהיית הווידאו" button).
  - With reduced motion it shows a still plated frame and no loop.
- **Menu:**
  - Grouped by category, each with a serif heading and a dish count.
  - Numbered, spacious rows with large dish names.
  - The demo price ("מחיר לדוגמה") sits next to the selection button, and the selection button is outlined and quiet.
  - Every row has a visible line: "כשרות ואלרגנים: טרם נמסר מידע".
- **No media tiles:** rows never contain a permanent video, poster or placeholder. Each row shows a small text cue instead: "וידאו הכנה · נוצר ב־AI להמחשה" (with a dot), or "ללא סרטון הכנה כרגע".
- **Selection:**
  - The full list stays at the end of the menu.
  - On desktop (1100 px and up), a compact sticky summary (count, sample total, "לסיכום") appears in the left corner once something is selected.
  - On mobile, an always-visible bottom bar.
- **Contrast:** all text pairs pass WCAG AA (values at the top of `customer.css`).

## Name-hover preview (desktop)

- **Activation:** hovering a dish **name** with a mouse starts the clip immediately. Touch is ignored here; a tap on the name opens the full window.
- **Placement:**
  - The window goes in the free space of the row, between the dish text (limited to about 34rem) and the price/selection column. It never covers the name, the price or the button.
  - When a window is too narrow, it may cover the description, but never the name.
  - Width is up to 540 px, at 16:9.
- **Soft edges:** two crossed gradient masks (`mask-composite: intersect`) dissolve every edge, with the strongest fade at the corners. No border, background or shadow. Only the sharp centre and the buttons take the pointer.
- **Dismissal:** the whole row keeps it open, so the pointer can travel across the row into the window. Leaving both the row and the window closes it after 220 ms.
  - Close, Esc, a scroll caused by the pointer, resize and a hidden tab also close it.
  - Hide only pauses the clip; there is no seek during the fade-out.
- **Switching:** one `<video>` element. Moving to another name stops the previous clip at once, and a token discards late `play()` results.
- **Keyboard:** focusing a name shows the same preview without moving focus. A scroll caused by focus doesn't close it; the window follows the row. Esc dismisses it; Enter opens the full window. The floating window is `aria-hidden`; the page button and the full window are the accessible paths.
- **Reduced motion:** no hover or focus playback.

## Sound

- **Default:** off. Hovering, scrolling and unrelated clicks never turn it on.
- **Hero entry:**
  - The primary button "כניסה לחוויה עם צלילי המטבח" turns kitchen sounds on (the shared `sound-pref.js` state), moves focus to the menu heading and scrolls there (instant scroll with reduced motion).
  - The quiet alternative "לתפריט ללא קול" leaves sound off, or turns it off, and goes to the same place.
  - This is not a blocking splash screen; both are ordinary buttons in the hero.
- **Consent:** besides the entry button, the nav button "הפעל צלילי מטבח" and the sound button in the floating window also count as explicit consent and as the user gesture browsers require. Consent lasts for the current page view only.
- **Status:** changes are announced in a `role="status"` line under the nav (also visible for a few seconds).
- **No guarantee of sound:** the button does not promise audio. If the browser still refuses, the clip continues muted, the setting returns to off, and the status says so and invites a retry with "הפעל צלילי מטבח".
- **Blocked audio:** if the browser refuses audible playback, the clip continues muted and the setting returns to off.
- **Mute:** always available, and in sync across all three controls.
- **No overlap:** the hero loop is always muted, and only one dish clip plays at a time.

## Clip segments (combined source files)

- **The problem:** `noodles-preparation.mp4` is a combined file — 0–10 s is falafel and 10.1–20 s is noodles. The noodles dish declares `startTime: 10.1, endTime: 20`. The original file is untouched; no trimming tool is installed.
- **The guard:** `video-segment.js` binds each player to its segment.
  - It clamps `loadedmetadata`, `seeking` and `timeupdate` into the segment.
  - It pauses at the segment end and reports "finished".
  - It hides the picture (`.is-off-segment`) until a **presented frame** (`requestVideoFrameCallback`, with an event fallback) lies inside the segment.
  - Result: a frame from the other dish is never shown — not on show, hide, switch, replay or seek.
- **Full window:** for a segmented clip, native controls are replaced by "השהיה / המשך ניגון", replay and skip, so the progress bar can't expose the other dish. Clips that aren't segmented keep native controls.

## Files

| Piece | File |
|---|---|
| Page structure, hero, dialog markup | `frontend/customer/index.html` |
| Visual design, rows, hover mask, sticky summary, dialog | `frontend/css/customer.css` |
| Fictional dishes (`video` with optional `startTime`/`endTime`) | `frontend/js/customer/demo-dishes.js` |
| Rows, grouping, filters, selection, hero loop, sound switch | `frontend/js/customer/catalog.js` |
| Name-hover preview and placement | `frontend/js/customer/hover-preview.js` |
| Segment guard (shared) | `frontend/js/customer/video-segment.js` |
| Full window (video and illustration modes) | `frontend/js/customer/kitchen-preview.js` |
| Shared sound consent | `frontend/js/customer/sound-pref.js` |
| Illustration mode (no longer linked from the menu) | `kitchen-scenes.js`, `kitchen-sound.js` |

## Video status

| Dish | Clip | Notes |
|---|---|---|
| שניצלונים פריכים | `schnitzel-preparation.mp4` | 10 s, standalone |
| כדורי פלאפל ירוקים | `falafel-preparation.mp4` | 10 s, standalone |
| אטריות מוקפצות בירקות | `noodles-preparation.mp4` | combined file; segment 10.1–20 s only |
| ירקות שורש צלויים | `roast-roots-preparation.mp4` | 10.03 s, standalone, 1280×720, H.264 + AAC, index at the start of the file (faststart). Added 2026-11-01; SHA-256 `9d12c766…be73f8` matches the downloaded source. |
| סלט עלים וצנוניות | `leaf-radish-salad-preparation.mp4` | 10.03 s, standalone, 1280×720, H.264 + AAC, faststart. Added 2026-11-01; SHA-256 `84c8420f…6c280de8` matches the downloaded source. Opens on radish slicing, ends on leaves with radish on an ivory plate. |
| סלט ירקות ערבי | `arabic-salad-preparation.mp4` | 10.03 s, standalone, 1280×720, H.264 + AAC, faststart. Added 2026-11-01; SHA-256 `7b5a907f…328b67ca0` matches the downloaded source. Opens on cucumber dicing, ends on diced tomato, cucumber, onion and herbs with olive oil. |

**All six dishes now have a preparation clip**, each used by exactly one dish. The "ללא סרטון הכנה כרגע" cue stays in the code for any future dish without a clip.

## Adding videos for new dishes

1. Put each clip, made for **that** dish, in `frontend/assets/video/`.
2. Add `video: { src: "/assets/video/<file>.mp4", seconds: <length> }` to the dish in `demo-dishes.js`. If the file holds several dishes, also add `startTime`/`endTime`.
3. Nothing else is needed. The name becomes the hover/focus/tap trigger, and the cue changes to "וידאו הכנה". Keep the "AI-generated, not real footage" labelling unless the clip is genuine footage of the business.

## How to preview

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/customer/. Use a server that supports HTTP Range requests (FastAPI does); segments and seeking depend on it.

## Limitations

- **Media:** clips are served as-is (5.4–9.4 MB each, with no captions or WebM fallback). The noodles file still downloads its falafel half.
- **Segment checks:** verified in Chrome automation, where frames are throttled, so only a few frames per scenario were captured. Re-check on a real device.
- **Fallbacks:** without `requestVideoFrameCallback` (older Firefox), the frame guard uses events and is less precise. Without CSS masks, the edge fade becomes a plain rectangle.
- **Selection:** in-memory only. Quote submission isn't built.
- **Testing gaps:** not tested with real screen readers, on physical phones, or in Safari or Firefox.
