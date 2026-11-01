# Design brief — "Light & guest-first" (Maya Ribak)

Status: **as built** on branch `design/maya-light` (design proposal for OPEN #12 / #20: language, brand). Hebrew, RTL.
Source of truth for scope: `docs/PRD.md`, `docs/UX_UI_SPEC.md`, `docs/OPEN_DECISIONS.md`. This brief decides **look, layout and motion only**. It adds no features. Anything marked OPEN in those docs stays open.

---

## 1. Idea in one line

A calm, airy, light site where **the guests come first**: the visitor says *when* and *who is coming*, and the one memorable moment is **approving the AI agent's suggestion**, which visibly flies into the order.

## 2. What was built

| Screen | Page | State |
|---|---|---|
| Home (entry to C1) | `frontend/index.html` | Built. Typed intro, how it works, photo row. |
| C1 Event details | `frontend/customer/event.html` | Built. Form saved to `sessionStorage`. |
| C2 + C4 Menu with the agent | `frontend/customer/index.html` | Built, **mock data and a scripted agent**. |
| C3 Summary & quote | `frontend/customer/summary.html` | Built, **mock data**. Sending only records a local price snapshot. |
| C5 Status | not created | Not built. |
| A1–A5 Owner dashboard | `frontend/admin/index.html` | **Placeholder page only.** |

Nothing talks to the backend yet: dishes, prices, totals, allergens and agent replies are mock (`frontend/js/mock/menu.js`, marked "הדגמה" on screen). The mock total is a stand-in for the backend pricing engine (ADR 0003).

## 3. What to avoid

- No dark backgrounds. No black hero bands.
- No serif or heavy display fonts.
- No decorative glow, stickers, or graphics that carry no information. The one exception is the typed intro's cursor and strike (see §7).
- No event-type cards as the main home content. Event type is an optional field.
- Do not invent business rules (quantities per guest, capacity, VAT, payment). Show placeholders where the docs say OPEN.

## 4. Tokens (`frontend/css/base.css`, existing variable names kept)

Palette: **apricot + ink** on a cool off-white. Colour roles are split so decorative apricot is never used where contrast is needed.

| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#F7F7F4` | page background |
| `--color-surface` | `#FFFFFF` | cards, panels |
| `--color-text` | `#1E2430` | text (deep ink, never pure black) |
| `--color-muted` | `#646B78` | secondary text (5.0:1 on bg) |
| `--color-line` | `#E1E3E6` | hairlines, borders |
| `--color-primary` | `#2B2F38` | filled buttons (ink); white text 13.4:1 |
| `--color-primary-hover` | `#1B1E25` | |
| `--color-accent` | `#F2A86A` | apricot highlights: borders, selected tint edge, step underline, dots. **Decorative only** (1.9:1 on white) |
| `--color-accent-tint` | `#FCE6D3` | selected stepper / chip background, your chat bubbles, new-line highlight |
| `--color-accent-text` | `#8A4A12` | text on white or tint (6.8:1 / 5.7:1). `#B05F1E` was rejected: 3.9:1 on the tint |
| `--color-approve` | `#C2410C` | the agent's **approve** button only; white text 5.18:1. Hover `#9A3412` (7.3:1) |
| `--color-glow` | `#F97316` | typed-intro cursor and strike only (decorative, glowing) |
| `--color-faint` | `#858B96` | struck-out intro lines (large text, 3.2:1, needs 3:1) |
| `--color-focus` | `#2B2F38` | 3px focus ring (the apricot accent would fail 3:1) |
| `--color-success` / `-bg` | `#2E6B47` / `#E3F0E8` | "applied" |
| `--color-warning` / `-bg` | `#7A5410` / `#FBF1DA` | "awaiting approval" |
| `--color-danger` / `-bg` | `#8E2F25` / `#F7E6E4` | "rejected", form errors |
| `--radius` | `14px` (cards 22px, buttons and pills 999px) | |

Status colours are unchanged from the original brief. Colour is never the only signal: every status has a text label.

## 5. Typography

- **Heebo** (Google Fonts), weights 300 / 400 / 500. Nothing else.
- Display headings: Heebo **300**, large, line-height ~1.1, slight negative letter-spacing.
- Body: Heebo 400, 15–18px, line-height 1.6. Emphasis / labels: 500. Never 700+.
- `font-variant-numeric: tabular-nums` for prices, counts and totals.

## 6. Components

- **Buttons**: primary = ink pill (48–54px). Secondary = 1px ink outline pill, no fill. In the agent panel the secondary actions (send, "לא עכשיו") are outline, the single **approve** button is filled `#C2410C`, and the page's main CTA "לסיכום ושליחה לאישור" stays the filled ink primary. Text links for tertiary actions.
- **Cards**: white, 1px line, radius 22px, no shadow.
- **Steppers** (− n +): pill outline; when qty > 0 the border turns apricot with the tint background and `accent-text` number.
- **Chips** (category / vegetarian / vegan filters): pill outline; pressed = apricot border + tint.
- **Status pills**: text + tint. Texts: טיוטה / ממתין לאישור / אושרה / לא אושרה.
- **Steps indicator**: plain text list, current step underlined in apricot (מתי ומי מגיע → תפריט → סיכום ושליחה).
- **Dish card**: 1:1 photo with radius 14px, name, price on the opposite side, unit + meat/dairy/pareve + vegetarian/vegan tags in muted 13px, an allergen-info disclosure ("unknown" is never shown as safe), stepper. If a photo fails to load, the grey "no photo" placeholder with a thin plate circle shows.
- **Proposal card** (diff card): rows "dish 0 ← 5 trays", total "₪5,592 ← ₪5,882", buttons `לא עכשיו` / `אישור`. States pending → applying ("מעדכן…") → applied ("✓ נוסף להזמנה") / rejected / expired. Once decided it shrinks to one compact row.
- Touch targets ≥ 44×44. Visible 3px ink focus ring everywhere. Logical CSS properties only.

## 7. Screens as built

### Home (`/`)
- Header: wordmark (business name is OPEN #20, placeholder "שם העסק"), nav התפריט · איך זה עובד · לבעל העסק.
- **Typed intro** on a clean, empty light background (Heebo 300, large, RTL, start-aligned): a glowing orange cursor blinks, then three questions type in one after another — "כמה אוכל להזמין?" / "מה עם הטבעונים?" / "כמה זה יעלה בסוף?". Each gets a thin glowing orange strike drawn right to left and its text fades to light grey. Then the final line in ink, larger: "אתם מארחים. אנחנו נחשב." Then the CTA "לתכנון האירוע" (ink pill) and the line "תפריט, כמויות והצעת מחיר, עם סוכן שעוזר בדרך".
- The markup already contains the complete **final state**, so reduced motion, repeat visits and no-JS show a finished static page.
- Below the fold: "איך זה עובד" (3 short steps) and a calm row of 4 dish photos with a link to the menu. Footer: link to the owner area.

### C1 — Event details (`/customer/event.html`)
- H1 "כמה אורחים מגיעים?", a single white card: date, arrival/pickup time, counters for adults, children (hint "עד גיל 12"), "מתוכם צמחונים" and "מתוכם טבעונים" (hint "נספרים בתוך הסך הכולל", OPEN #4), delivery / pickup toggle, address (delivery only, with "דמי משלוח לפי אזור, יחושבו באישור העסק"), optional event-type select.
- CTA "לבניית התפריט · N אורחים": N is live and counts to its new value.
- Validates only what is certain (date not in the past, time, at least one guest, address for delivery). No capacity, blocked-date, subset or fee rules (OPEN #4, #5, #19). Saves to `sessionStorage` (`js/event-store.js`) and continues to the menu, whose header shows the details.

### C2 + C4 — Menu with the agent (`/customer/`)
- Desktop: catalog grid with category / diet chips on one side, **agent panel** on the other. The header is sticky and the panel is sticky below it, filling the rest of the viewport at any scroll position; the messages area takes the remaining height and scrolls to the newest item, so the latest proposal card is fully visible on load. Mobile: catalog + a sticky bottom bar with the total, a **"שאלו את הסוכן"** button (with a dot while a proposal waits) and "לסיכום". A hint pill above the bar ("לסוכן יש הצעה לטבעונים") opens the agent as a bottom sheet over a blurred catalog. The sheet traps focus, closes with Escape and returns focus.
- Agent panel: the note "מציע רק מנות מהתפריט של העסק, ולא משנה כלום בלי אישור שלך", messages, the proposal card, input, then a collapsible order list (collapsed by default, opens on approve), a delivery row "לפי אזור, יחושב באישור" (for pickup: "קבלה · איסוף עצמי" and no delivery wording anywhere), total, and the CTA "לסיכום ושליחה לאישור". The foot (delivery/pickup row, total, CTA) is always visible: only the order lines scroll, and the chat gives way when space runs short.
- The agent is scripted (two proposals, then a demo reply), labeled "הדגמה".

### C3 — Summary & quote (`/customer/summary.html`)
- Steps indicator with step 3 current, status pill "טיוטה · עוד לא נשלחה", H1 "הצעת המחיר שלך".
- One white card: event facts (date, time, guests with the adults/children split, delivery address or pickup) from `event-store`, then itemised lines (name, qty × unit price, line total in tabular numbers), a delivery row "לפי אזור, יחושב באישור" (delivery only), a big total, and "ההזמנה מחייבת רק אחרי אישור העסק."
- A second card: delivery address (delivery only, required) and optional notes. CTA "שליחה לאישור העסק" (ink primary) and a text link "חזרה לתפריט".
- On send: a calm confirmation on the same page ("ההזמנה נשלחה לבעל העסק"), the pill changes to "ממתין לאישור" (never shown as confirmed), the form is replaced, and the page returns to the top. The quote lines shown afterwards are the **price snapshot** taken at sending (also stored in `sessionStorage`).
- Pickup: "איסוף עצמי" instead of an address, no delivery row, no address field and a plain "סה״כ".
- A sent quote is shown only while it still matches the current event and order; a new event or a changed order starts a new draft.
- Empty order: "עוד לא נבחרו מנות" with a link back to the menu.
- Deliberately **not** in it: payment (OPEN #2), VAT (OPEN #14), a "enough food for everyone" coverage block (needs the business quantity rules, OPEN #3), editing after sending (OPEN #7).
- The menu now keeps the draft order in `sessionStorage` so this page can read it.

### C5, A1–A5
Not built. The owner area is a placeholder page so no link is dead. Design intent from the original brief is kept for later: C5 shows a 3-step timeline and no payment (OPEN #2); A1 is the owner's order list with frozen-price lines and approve/reject.

## 8. Motion (subtle, purposeful; `prefers-reduced-motion` turns all of it off)

| Where | What | Timing |
|---|---|---|
| Home intro | Cursor blinks 450ms, three lines type (20ms/char), strike draws right to left (300ms) while the text fades to grey, final line and CTA fade up. Whole sequence ~3.2s | plays **once per session** (`sessionStorage`); a click or any key skips to the final state; reduced motion / repeat visit show the final state at once |
| Event form | Guest count on the CTA counts to the new value | 380ms ease-out |
| Menu: manual add (+) | **Mobile only:** a small apricot dot flies from the dish card to the bottom-bar total. **Desktop** (side panel in view): no flight. On both: the stepper pops, the new summary line is highlighted (the order list opens briefly, then tucks away) and the total rolls | dot 450ms |
| **Menu: approve agent proposal (signature)** | A named ink pill flies in an arc from the proposal row to the order total (two nested elements: X `cubic-bezier(.3,.6,.4,1)`, Y `cubic-bezier(.55,-0.4,.8,.6)`), shrinks to 45% and fades. Then the total rolls (700ms, ease-out, 1px blur while rolling), the order list opens and the new line is highlighted in the tint for ~1.2s, the dish stepper pulses twice | flight 750ms |
| Agent messages | Fade-up on arrival | 450ms, 200ms stagger |
| Bottom sheet | Slides up over the blurred catalog | 350ms |

Totals use a visually hidden `aria-live="polite"` region that announces only the final value, not every rolling step. With reduced motion there are no flights, no rolling and no running animations (checked).

## 9. Food photography

12 photos, one consistent style, in `frontend/assets/` (one per mock dish). Origin and rights are recorded per image in `frontend/assets/README.md`: generated by Maya with an image generation tool, 2026-11-01, licensed for use in this project. If an image is missing the dish card falls back to the grey placeholder.

Style: overhead or 45° close-up of a single plated dish, light grey-white seamless background, soft natural daylight from the side, lots of empty space around the plate, modern minimal white ceramic plate, no hands, no text, no props except one linen napkin, refined restaurant plating, true-to-life colours.

Avoid: rustic wooden boards, candles, crowded tables, heavy dark backgrounds.

## 10. Accessibility (checked on every page at 1440px and 390px)

- No horizontal overflow, no clipped text, no dead internal links, no console errors.
- Every interactive element is reachable by keyboard and shows a visible focus ring; the mobile sheet traps focus; forms submit with Enter.
- Text contrast meets WCAG AA (4.5:1; 3:1 for large text). The two intentionally low-contrast, decorative elements are the orange cursor/strike (non-text) and the struck intro lines, which are large text at 3.2:1.
- `lang="he" dir="rtl"`, logical properties, labels on all inputs, `aria-live` for totals and chat.

## 11. Engineering constraints

- Static frontend served by FastAPI (ADR 0001): plain HTML, CSS, ES modules. No frameworks, no build step.
- Structure per `UX_UI_SPEC.md` §5, plus `css/site.css` (shared chrome), `css/home.css`, `css/event.css`, `css/customer.css`, `css/summary.css`, `js/summary.js`, `js/components/*` (stepper, dish card, proposal card, order summary, agent panel, bottom sheet, fly pill, status pill), `js/mock/menu.js`, `js/event-store.js`.
- RTL: `<html lang="he" dir="rtl">`. Mobile-first, breakpoints 640 / 1024.
- Mock data is clearly marked until the API exists.
