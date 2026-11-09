# Visual Identity: yumm.ai (Green Eggs and Ham option)

Status: **Phases B, C and D implemented, plus a motion layer (design system, landing page, event setup, menu and assistant, motion)** on branch `design/green-eggs-and-ham`. The illustrated assets (mascot, occasions, food art) arrive in phases C and D. Decisions are recorded in `docs/VISUAL_INTEGRATION_PLAN.md`; asset status is in `docs/ASSET_MANIFEST.md`.

## Direction

"Storybook kitchen" for adults: warm cream ground, bold ink outlines, deep green for structure, red and butter yellow as accents. Illustration lives in the hero, occasion picker, category headers and assistant. Ordering surfaces (forms, prices, quote status) stay calm and typographic.

The look evokes classic picture-book energy through colour, outline weight, hand-lettered headlines and friendly shapes. It does not reuse any existing book's characters, lettering or illustrations. The V3 mascot is a stand-in that has not passed an originality review (see the manifest).

## Colour

Defined once in `frontend/css/base.css` (`:root`). Components use the semantic `--color-*` tokens, never raw hex.

| Token | Value | Role |
|---|---|---|
| `--brand-cream` / `--color-bg` | `#FFF9ED` | Page ground (client brief) |
| `--brand-green-deep` / `--color-accent` | `#3F702B` | Buttons, links, focus, selected states |
| `--brand-green-deeper` / `--color-accent-strong` | `#2E551E` | Hover and pressed (derived) |
| `--brand-green` / `--color-fill` | `#82B441` | Fills and illustration only; carries dark text, never white |
| `--brand-red` | `#F0442D` | Decoration and large type only |
| `--brand-red-text` / `--color-danger` | `#C2321F` | Errors, meat badge, small red text (derived) |
| `--brand-yellow` / `--color-highlight` | `#FFD65A` | Highlights |
| `--brand-ink` / `--color-text` | `#202020` | Text and outlines |
| `--color-muted` | `#4A4A44` | Secondary text |
| `--color-control-border` | `#7A7260` | Inputs, chips, choice cards |

Contrast (WCAG, measured): ink on cream 15.5, muted on cream 8.5, deep green on cream 5.6, white on deep green 5.9, ink on brand green 6.6, ink on yellow 11.7, control border on cream 4.55, danger text on cream 5.3, danger on its tint 4.7, warning on its tint 7.2. Not allowed: white on brand green (2.5), brand red as small text on cream (3.6).

## Type

| Role | Face | Use |
|---|---|---|
| Display | **Playpen Sans Hebrew ExtraBold** (static, self-hosted, SIL OFL 1.1) | Page titles, category and landing headlines (32px and up), the wordmark |
| Interface | **Heebo** (variable, self-hosted) | Forms, dish names, prices, dietary labels, chat, buttons |

**Size rule:** the face's hand-drawn mem and aleph look alike when small, so it is only used at 32px and up. Smaller headings (panel titles, step titles, chat) use Heebo at weight 800.

Files: `assets/fonts/playpen-sans-hebrew-{hebrew,latin}-800.woff2` (24 KB + 63 KB) and Heebo. No external font host. Headlines use `text-wrap: balance`. Prices and totals use tabular numerals.

Scale: `--text-sm` 14, `--text-base` 16, `--text-lg` 18, `--text-xl` 22, `--text-2xl` 28, `--text-hero` fluid 32 to 56 px.

## Wordmark

`yumm.ai` in the display face, deep green with a red dot. The Latin name is always LTR (`<bdi>`), even inside RTL pages. This is a typographic placeholder; a designed logo is still pending (open decision #20).

## Shape, depth, interaction

- Radius: `--radius-sm` 10, `--radius` 16, `--radius-lg` 24, pill for chips and badges. Illustrated objects get a 2px ink outline (`--outline-width`): buttons, dish cards. Panels use a 2px warm line.
- Depth: soft, warm shadows (`--shadow-1`, `--shadow-2`). No hard offset shadows.
- Focus: 3px deep-green ring with 3px offset on every interactive element (`--focus-ring`).
- Targets: 44px minimum (`--touch-target`).
- Motion: see "Motion layer" below. `prefers-reduced-motion` disables every transition, animation and effect.
- Breakpoints (documented, since media queries cannot read variables): phone 640, desktop and docked assistant 992, container 1120. Main layouts use container queries.

## Components in this phase

Buttons (primary, secondary, ghost, danger), form fields, badges (kashrut, dietary, status), chips, steppers, dish card, order summary, assistant panel with proposal diff card, status hero, skeletons, empty states, `.wordmark`, and `.illus` (a reserved-ratio box for illustrations, so images never shift layout). Unchanged by design: all behavior, pricing, the store and the approve/reject flow.

## Visual QA checklist

Run before each phase review. Last full run: Phase E (see `docs/VISUAL_INTEGRATION_PLAN.md` section 17).

- [x] Phone (390, and 320 after a fix), tablet (768) and desktop render without horizontal scroll on every step.
- [x] Display face only at 32 px and up; check that mem and aleph stay distinguishable in every headline.
- [x] Text contrast at least 4.5:1 (3:1 for 24 px+ or bold 18.5 px+); no white on brand green; no small text in brand red.
- [x] Every interactive element shows a visible focus ring; tab order matches reading order.
- [x] All ordering actions work with images disabled.
- [x] Illustrations: informative ones have alt text, decorative ones use `alt=""`; dimensions reserved.
- [x] Quote status always says pending business approval until approved; the celebrating mascot appears only for "request sent".
- [x] AI proposals show current value, proposed value, price difference, explicit approve and reject; no animation or mascot on those buttons.
- [x] Dish cards use business photography when it exists, never illustrations.
- [x] Dietary icons are labels beside backend data, never a source of truth.
- [x] `prefers-reduced-motion` and the menu's "stop animations" respected; nothing animates on page load; no continuous animation.
- [x] Existing ordering flow (event, menu, summary, submit, status) still works end to end.

## Phase C additions

- **Landing page** (`/`): hero with the welcome mascot on a yellow sun, occasion cards that link into the event step (`/customer/?occasion=...` preselects the type), a three-step explanation, an assistant introduction with a static, labelled example of the approval card, a closing call to action. No JavaScript.
- **Event step:** the event-type dropdown became illustrated radio cards (7 types, including anniversary). The art is decorative (`alt=""`); the visible label names each choice, so the step works with images off. The mascot greets once beside the title on wide screens and never sits over a field.
- **Illustration helper** (`js/lib/illustrations.js`): one manifest of keys, sizes and paths; `<picture>` with WebP and PNG fallback, reserved width and height, lazy loading except above the fold.
- Asset provenance and status: `docs/ASSET_MANIFEST.md`.

## Phase D additions

- **Menu:** each category has a food drawing in its header and in its filter chip (salad, main dish, fish, sides, dessert, drinks). The drawings are decorative (`alt=""`; the label names the category). Dish cards still show no image unless the data supplies one, so no drawing is ever presented as the dish being sold.
- **Assistant:** the mascot is the assistant's identity, as a round crop of its face and hat (`components/mascot.js`). State per moment: welcome (header, button, first message), thinking (while it replies), suggesting (a message that carries a proposal), explaining (an answer without a proposal), celebrating (a small avatar next to "the change was applied", after the customer approved it). The proposal card, the approve and reject buttons, and the price difference carry no mascot and no styling beyond the shared components.
- **Quote status:** after submission the celebrating mascot acknowledges that the request was sent. The badge (clock icon, "ממתין לאישור העסק"), the headline and the sentence "זו בקשה להצעת מחיר ולא הזמנה מאושרת" always accompany it, and the mascot does not appear for approved or rejected states.
- No animation was added; the mascot is static until the static design is approved.

## Motion layer (added after the static design was approved, trimmed for IS 5568)

Principles: transform and opacity only; an effect only ever answers something the visitor did or a state change. **Nothing plays on page load and nothing hides content waiting for a scroll** (IS 5568 / WCAG 2.2.2); the page-load animations of the first motion layer (hero arrival, scroll reveal, step rise, mascot wave, stepper and status pops, the occasion hop) were removed in the accessibility pass. The assistant's avatar wobbles three times while it is thinking, then stops. Code: `css/motion.css`, `js/lib/motion.js`, `js/landing.js`. `backend/tests/test_accessibility.py` fails if a page-load animation comes back.

| Where | What | Meaning |
|---|---|---|
| Landing hero | The art drifts a few pixels toward the pointer (fine pointers only); the header gains a shadow once scrolled | Orientation |
| Landing occasion cards and steps | The drawing tilts and grows slightly on hover or focus | Affordance |
| Landing approval example | Clickable: approve (total counts up to 1,350 and confetti), reject (nothing changes), or start over. It demonstrates that nothing changes until approved and sends nothing | Teaches the core rule |
| Menu | Adding a dish bumps its card, slides a new line into the order panel, and counts the subtotal up or down | Feedback |
| Summary | The total counts to its new value | Feedback |
| Assistant | New messages rise in; the avatar wobbles (three loops at most) while it is replying; confetti and the celebrating mascot appear only after an approved change | State change |
| "Request sent" screen | One burst of confetti, once, after submitting; the pending text is always beside the mascot | Acknowledgement |

Accessibility: animated numbers are `aria-hidden` while a visually hidden copy holds the real value, so screen readers hear each change once. Confetti is `aria-hidden` and removed from the DOM after a second. Every effect is switched off by `prefers-reduced-motion` and by the accessibility menu's "עצירת אנימציות" (class `a11y-no-motion` on `<html>`, read by `reduced()` in `js/lib/motion.js` and mirrored in `css/base.css`): numbers jump to their final value, confetti is skipped, and every animation and transition is disabled. The two loading indicators that repeat (skeleton shimmer, the "typing" dots) only run while something is loading and are stopped by the same switches.

## Accessibility modes (IS 5568)

Added in the accessibility pass; the full criterion map and manual checklist are in `docs/ACCESSIBILITY.md`.

- **Text size:** `html.a11y-size-1` / `html.a11y-size-2` scale the root to 125% / 150%. Every font size is in rem (a test enforces it), so everything scales.
- **High contrast:** `:root.a11y-contrast` in `css/base.css` replaces the colour tokens with a white and black palette. Text pairs reach 7:1 or more (tested); the focus ring is 4px black. Components still use only the semantic `--color-*` tokens, so nothing else changes.
- **Underlined links:** `html.a11y-links`.
- **Forced colours (Windows High Contrast):** the mask icons keep `forced-color-adjust: none` so they stay visible.
- **Short viewports** (200% zoom on a laptop, a phone on its side): below 480px of height the sticky header and fixed bottom bar scroll with the page.
