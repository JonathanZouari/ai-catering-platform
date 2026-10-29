# Design Direction: Neo-Brutal Pop

Status: **Proposal**, resolves the visual part of OPEN #12. Not yet implemented in `frontend/css/base.css`.

Designs were produced in Stitch (project "AI Catering Platform – Young & Colorful"). Three directions were explored on the dish catalog screen (C2); **Neo-Brutal Pop** was chosen.

| Direction | Idea | Status |
|---|---|---|
| **Neo-Brutal Pop** | Thick black outlines, hard shadows, flat bright blocks | **Chosen** |
| Aurora Glass Night | Dark mode, glass cards, neon glow | Not chosen |
| Fresh Market Soft | Mint/cream, pastel cards, soft blobs | Not chosen |

## Visual language

- Colors: yellow `#FFE600` (primary), hot pink `#FF3EA5`, cyan `#00C2FF`, white background, black ink `#000`.
- Fonts: Syne (headlines), DM Sans (body), Space Grotesk (labels).
- Shape: 4 px radius, 3 px black borders, hard offset shadows without blur (`4px 4px 0 #000`).
- Cards are not tilted; only small stickers (price, "new") may tilt a few degrees.
- One block color per category, not random colors.
- Hebrew first, RTL; use logical CSS properties (see `UX_UI_SPEC.md` §1).

## UX issues found and fixes applied to the catalog screen (C2)

1. **Accessibility and contrast.** Black text on light blocks only (≥ 4.5:1); kashrut/vegan/vegetarian badges carry an icon and text, never color alone; allergen link ≥ 14 px with a 44×44 px target; visible focus ring.
2. **Visual hierarchy.** "Add" button and price are the dominant element of each dish card; badges and allergen link are secondary; uniform grid; smaller marquee and headline so the first dishes appear above the fold.
3. **Bottom bar and AI button.** AI button floats above the sticky bar without covering the total or the CTA, on the RTL start side; bottom padding so the last dish is not clipped; bar shows item count, live total (`aria-live`), and a primary CTA ≥ 48 px.

## Open follow-ups

- Empty cart state for the bottom bar ("עוד לא בחרת מנות", CTA disabled) is **not designed yet**.
- The generated AI button carried an unrequested "free" badge; remove it, since pricing of the assistant is not a decided fact.
- A bottom navigation bar appeared in the generated HTML; confirm whether it is wanted next to the sticky cart bar.
- Remaining screens (C1, C4, C3/C5, admin A1) to be designed in the same language.
- Stitch designs are not exported into the repo yet; implementation should map the tokens above to the CSS custom properties in `base.css`.
