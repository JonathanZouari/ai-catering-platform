# Design brief — "Light & guest-first" (Maya Ribak)

Status: design proposal for OPEN #12 / #20 (language, brand). Hebrew, RTL.
Source of truth for scope: `docs/PRD.md`, `docs/UX_UI_SPEC.md`, `docs/OPEN_DECISIONS.md`. This brief decides **look, layout and motion only**. It adds no features. Anything marked OPEN in those docs stays open.

---

## 1. Idea in one line

A calm, airy, light site where **the guests come first**: the visitor starts by saying *when* and *who is coming*, and the one memorable moment is **approving the AI agent's suggestion**, which visibly flies into the order.

## 2. What to avoid

- No dark backgrounds. No black hero bands.
- No serif or heavy display fonts.
- No warm-cream + terracotta palette.
- No decorative glow, stickers, or graphics that carry no information.
- No event-type cards as the main home content. Event type is an optional field.
- No illustrative graphic for the guest mix on the home page. The mix lives in the form and in the live number on the CTA.
- Do not invent business rules (quantities per guest, capacity, VAT, payment). Show placeholders where the docs say OPEN.

## 3. Tokens (map into `frontend/css/base.css`, keep the existing variable names)

| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#F7F7F4` | page background (cool off-white) |
| `--color-surface` | `#FFFFFF` | cards, panels |
| `--color-text` | `#1E2430` | text (deep ink, never pure black) |
| `--color-muted` | `#646B78` | secondary text |
| `--color-line` (new) | `#E1E3E6` | hairlines, borders |
| `--color-accent` | `#1F3C96` | the ONLY accent: primary buttons, current step, selected qty |
| `--color-accent-hover` (new) | `#152C70` | |
| `--color-accent-tint` (new) | `#EBF0FA` | selected dish control background |
| `--color-success` | `#2E6B47` | "applied", "enough" |
| `--color-warning` | `#7A5410` on `#FBF1DA` | "awaiting approval", "consider adding" |
| `--color-danger` | `#8E2F25` on `#F7E6E4` | "rejected" |
| `--radius` | `14px` (cards 22px, buttons 999px) | |

Contrast must pass WCAG 2.2 AA (4.5:1 for text). Colour is never the only signal: every status has a text label.

## 4. Typography

- **Heebo** (Google Fonts), weights 300 / 400 / 500. Nothing else.
- Display headings: Heebo **300**, 40–62px, line-height 1.08, slight negative letter-spacing.
- Body: Heebo 400, 15–18px, line-height 1.6.
- Emphasis / labels: 500. Never 700+.
- Thin weights only at large sizes. Prices, tables and admin data use 400.
- `font-variant-numeric: tabular-nums` for all prices, counts and totals.
- Inspiration (not to copy): yamaonline.co.il and arestaurant.co.il use Narkiss Block, a paid font. Heebo is the free stand-in.

## 5. Components

- **Buttons**: primary = filled accent pill, 48–54px high. Secondary = 1px ink outline pill, no fill. Text links for tertiary actions.
- **Cards**: white, 1px `--color-line`, radius 22px, no shadow.
- **Steppers** (−  n  +): pill outline; when qty > 0 border and background switch to accent / accent-tint.
- **Status pills**: small, text + tint (see tokens). Texts: טיוטה / ממתין לאישור / אושרה / לא אושרה.
- **Steps indicator**: plain text list, current step underlined in accent. Three steps: מתי ומי מגיע → תפריט → סיכום ושליחה.
- **Dish card**: image 4:3 radius 14px (or the "no photo" placeholder: light grey box with a thin empty plate circle), name 18px, price right-aligned, unit + kashrut/diet tag in muted 13px, stepper.
- Touch targets ≥ 44×44. Visible focus ring in accent. Logical CSS properties only.

## 6. Screens

### C1 — Home = event setup (`frontend/index.html` → links to customer flow)
- Header: wordmark (business name is OPEN #20, use a placeholder), nav: התפריט · איך זה עובד · לבעל העסק.
- Hero, two columns (stack on mobile):
  - Text column: eyebrow "קייטרינג לאירועים פרטיים", H1 **"כמה אורחים מגיעים?"**, one-line subtitle.
  - **Planner card** right under it: date, arrival time, adults, children (hint "עד גיל 12"), of-which vegetarians, of-which vegans (hint "נספרים בתוך הסך הכולל" — OPEN #4), delivery / pickup toggle, optional event-type select "(לא חובה)". CTA: **"לבניית התפריט · 80 אורחים"** (the number is live).
  - Image column: **one large, calm food photograph** (see §8). No graphic, no illustration.
- Below: "איך זה עובד" — 3 short steps (real sequence, so numbering is fine).
- Footer: link to owner login.

### C2 + C4 — Menu with the agent (`frontend/customer/`)
- Desktop: catalog grid on one side, **agent side panel** on the other (as `UX_UI_SPEC.md` C4). Mobile: catalog list + bottom bar; agent opens as a bottom sheet over a blurred catalog.
- Agent panel: short note "מציע רק מנות מהתפריט של העסק, ולא משנה כלום בלי אישור שלך", messages, the **proposal card**, input, and the running order summary + total + CTA "לסיכום ושליחה לאישור".
- Proposal card = the diff card from the spec: rows "שם המנה  0 ← 5 מנות", total "₪5,592 ← ₪5,882", buttons אישור / לא עכשיו. States: pending → applying ("מעדכן…") → applied ("✓ נוסף להזמנה") / rejected / expired.

### C3 — Summary & quote
- Itemised lines (qty × unit = line), delivery "לפי אזור, יחושב באישור", big total, note "ההזמנה מחייבת רק אחרי אישור העסק", address + notes fields, CTA **"שליחה לאישור העסק"**.
- Side block **"יש מספיק לכולם?"**: one row per guest group (מבוגרים, ילדים, צמחונים, טבעונים) + desserts, each with a thin progress bar and "מספיק" / "כדאי להוסיף". Values come from the business quantity rules (OPEN #3); until then use mock data and label it.

### C5 — Status
- Big title per state, 3-step vertical timeline (נשלחה → בבדיקת העסק → אושרה), owner note box when present, order facts. No payment (OPEN #2).

### A1 — Owner orders (`frontend/admin/`)
- Top nav: הזמנות · מנות וקטגוריות · מחירים · זמינות · משלוחים ואיסוף.
- H1 "3 הזמנות מחכות לאישור שלך", two quiet stats inline (no big tiles).
- List with status filter + detail panel: event facts, availability checks, frozen-price lines, **"מה השתנה בשיחה עם הסוכן"**, owner note textarea, אישור ההזמנה / דחייה.
- Other admin screens (A2–A5): same components, later.

## 7. Motion (subtle, purposeful, `prefers-reduced-motion` turns all of it off)

| Where | What | Timing |
|---|---|---|
| Home hero | H1 words fade-up one after another; subtitle and card follow | 0.7s each, cubic-bezier(.2,.8,.2,1), 130ms stagger, once |
| Home planner | Total in the CTA counts to the new value | 380ms ease-out |
| **Agent approve (signature)** | A small accent pill with the dish name flies in an arc from the proposal row to the order total; it shrinks to 45% and fades. Then: total rolls (700ms, ease-out, 1px blur while rolling), the new summary line highlights in accent-tint for ~1.2s, the dish card stepper pulses twice | flight 750ms: X `cubic-bezier(.3,.6,.4,1)`, Y `cubic-bezier(.55,-0.4,.8,.6)` (two nested elements make the arc) |
| Agent messages | Each message / the card fades-up on arrival | 450ms, 200ms stagger |
| Summary | Coverage bars fill on load | 900ms, 120ms stagger |
| Status | Timeline line fills between completed steps | 700ms per segment |

Total roll and summary updates use `aria-live="polite"`.

## 8. Food photography

Real or generated, but **one consistent style** (if generated, record origin and rights in `frontend/assets/README.md`):

> Overhead or 45° close-up of a single plated dish, light grey-white seamless background, soft natural daylight from the side, lots of empty space around the plate, modern minimal white ceramic plate, no hands, no text, no props except one linen napkin, refined restaurant plating, true-to-life colors, 4:3.

Avoid: rustic wooden boards, candles, crowded tables, heavy dark backgrounds.

## 9. Engineering constraints

- Static frontend served by FastAPI (ADR 0001): plain HTML, CSS, ES modules. No frameworks, no build step.
- Keep the folder structure in `UX_UI_SPEC.md` §5. Reusable components as small modules (`js/components/…`).
- RTL: `<html lang="he" dir="rtl">`, logical properties everywhere.
- Mobile-first, breakpoints 640 / 1024.
- Mock data clearly marked until the API exists.
