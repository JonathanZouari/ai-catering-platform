# UX/UI Specification (initial structure)

Status: **Draft v0.2**. Visual direction chosen: **"Table Journal" (יומן שולחן)**, an editorial food-magazine look, Hebrew RTL. It was picked from three Claude Artifact prototypes; the logo is still **[OPEN #20]**.

## 1. Principles

- Mobile-first; breakpoints 640 / 1024 px **[RECOMMENDATION]**.
- Accessibility target WCAG 2.2 AA: 4.5:1 text contrast, visible focus, 44×44 px touch targets, labels on all inputs, `aria-live` for price totals and chat replies, full keyboard use.
- Hebrew RTL (`<html lang="he" dir="rtl">`). Logical CSS properties only (`margin-inline-start`, `inset-inline-end`, etc.), never left/right.
- Premium but calm: generous whitespace, one accent color, restrained motion, `prefers-reduced-motion` respected.
- Never show a pending quotation as a confirmed booking — status badges use explicit text ("Awaiting business approval").

## 2. Design system ("Table Journal")

Source of truth: `frontend/css/base.css` (tokens, primitives, every app-screen component) and `frontend/css/home.css` (landing page only).

**Look.** Warm paper page, espresso text, a pomegranate accent for every action and selection, and saffron for small marks of place. Rounded corners and quiet cards on the paper background (v2, 2026-11-14; before that: square corners and rules). Large food photography, 3D depth on the landing page, and hand-drawn line illustrations with handwritten notes.

**Color tokens ("pomegranate & saffron", 2026-11-08).** Light values are listed. Dark values (espresso background, paper text, light pomegranate) switch automatically with `prefers-color-scheme`, or can be forced with `data-theme`. Every text pair passes WCAG AA in both themes.

| Token | Light | Use |
|---|---|---|
| `--bg` / `--surface` | `#fff8ef` / `#fffdf9` | Page and panel background |
| `--fg` | `#2a1a12` | Text and rules |
| `--muted` | `#6b5546` | Secondary text |
| `--line` / `--line-strong` | `#ecdcc8` / `#9a7f6a` | Dividers and control borders (3.5:1) |
| `--accent` / `--accent-fg` / `--accent-ink` | `#a11d3a` / `#fff8ef` / `#a11d3a` | Primary button, selected chips and segments, menu bar, own chat messages, toast, focus ring, illustrations |
| `--spark` / `--spark-soft` | `#b8780f` / `#fbe7c2` | Saffron: the current page in the header, draft pills, the hand-drawn rule under headings, text selection |
| `--success` / `--danger` / `--warning-ink` (+ `-soft`) | | Status pills, notices. Danger is a vermilion (`#b93a14`) next to the pomegranate accent, so errors always carry text and `aria-invalid` too |
| `--meat` / `--dairy` / `--parve` | | Kashrut badges |
| `--photo-ink`, `--paper`, `--paper-ink` | | Text on photos; the polaroid cards |
| `--shade` | `32 14 8` | RGB triplet for warm photo overlays and shadows: `rgb(var(--shade) / .5)` |

Browser surfaces follow the palette: caret, checkbox/radio accent, scrollbar and text selection.

**Type.** All fonts come from Google Fonts.

| Token | Font | Use |
|---|---|---|
| `--font-display` | Frank Ruhl Libre 400/700/900 | Headings |
| `--font-body` | Assistant 400/600/700 | Body text |
| `--font-hand` | Amatic SC 700 | Handwritten notes only (`.hand`) |

**Radius.** `--radius` 18px (cards, photos), `--radius-sm` 12px (inputs, notices), `--radius-pill` 999px (buttons, chips, pills). `--header-h` is the sticky header's height (69px, 61px on phones); sticky bars sit below it.

**Illustrations.** Two kinds.
- Painted: four watercolour cut-outs, `assets/img/art-*.webp` (lemons, pomegranate, olives, pot), with transparent backgrounds. Decoration only (`alt=""`, class `.paint`): the landing page and the empty state on the account page.
- Line art: `js/illustrations.js`, on a 64×64 grid: basket, pot, grill, glass, lemon, olive, calendar, plate, sign, arrow, pom, fish, cake, bread, tray, fork and search.
- To place one, write `<i data-ill="pot"></i>`. `hydrateIllustrations()` replaces it with an inline SVG.
- Color comes from `currentColor`, which defaults to the accent.

**Motion.** `js/motion.js` runs it, and it stays restrained: nothing hijacks scroll except the 3D ring on the landing page.
- It adds `.motion` to `<html>` only when reduced motion is off. Content is never hidden without JS or for reduced-motion users.
- `.reveal` children fade in one after another when they enter the screen. Illustrations inside them draw themselves in.
- `.tilt` tiles and `.dish-media` lean toward a mouse pointer.
- The photo band on app screens moves with parallax.

**Header (every page).** One header, the same links in the same place: דף הבית, התפריט (`/menu/`), איך מזמינים, האזור האישי, the "תכנון אירוע" button, and "כניסת עסק" set apart at the end. Admin pages use the same structure with their own links and "חזרה לאתר הלקוחות" in that last place. The current page is marked with `aria-current="page"` (saffron pill). Up to 860px the links fold behind `.nav-toggle`; Escape closes the menu.

**Order steps (`.steps`).** The event form, the dish screen and the status page show the same four illustrated steps: האירוע, המנות, סיכום ושליחה, אישור העסק. Done steps get `.done`, the current one `aria-current="step"`.

**Landing page** (`index.html`, `js/home.js`):
- Hero, "the table from above": five dish photos cut round like plates, with painted garnish between them. The plates land one after another on load, and drift a little with scroll and pointer.
- A four-column "day of an event" strip.
- A handwritten marquee.
- A scroll-driven 3D ring of featured dishes, with arrow buttons. Static marketing content; each card links to the public menu.
- Stories, then "how to order".

**App screens** (`customer/`, `admin/`):
- Each screen opens with a photo band and a handwritten caption with an illustration.
- The classes for C1–C5 and A1 already exist in `base.css`: `.dish`, `.stepper`, `.lines`, `.ai`, `.proposal`, `.timeline`, `.order-row`.
- Event form (C1): one `.form-card` per question group, each with a drawn icon in its title.
- Account page: the orders card first and wide (`.account-grid`), each order with a button that says what happens next; the profile card beside it.
- Dish screen (C2): `.menu-bar` sticks under the header with the category tabs (`.cat-tabs`, one category open at a time, "כל התפריט" last), a search across the whole menu and the diet filters. The tabs wrap so every category shows; on phones they are one scrolling row with a fading edge. Chosen dishes carry an "על השולחן" mark and sit as small plates on the table bar.

**Public menu** (`menu/index.html`, `js/public-menu.js`): every available dish, read-only, with no login and no order. The same tabs, search, filters and cards as the dish screen (the card helpers are shared from `js/menu.js`), without quantity controls.

## 3. Customer screens

| # | Screen | Key elements |
|---|---|---|
| C1 | Event configuration | Stepper; event type, date (blocked dates disabled), time slot, guest composition counters with helper text (subset rule **[OPEN #4]**), dietary notes, pickup/delivery toggle, address + zone fee preview |
| C2 | Dish catalog | Category tabs/chips, dish cards (image, name, price + unit, kashrut badge, veg/vegan badges, "allergen info" link), filters, add/quantity stepper |
| C3 | Order summary & pricing | Itemized lines (qty × unit price = line), recommendation hints, delivery fee, total, `version`-safe edits |
| C4 | AI assistant | Desktop: side panel next to C2/C3. Mobile: bottom sheet opened by a persistent button. Message list, input, proposal cards inline |
| C5 | Quote submission & status | Review, explicit "Submit quotation request", status page: Draft / Awaiting approval / Approved / Rejected + owner note |

### Proposal diff card (C4)

```
┌ Suggested change ───────────────────────┐
│ Add  Roasted vegetables        × 2 trays │
│ Hummus             3 → 5 trays           │
│ ─────────────────────────────────────── │
│ Total   1,200.00  →  1,350.00  (+150.00) │
│ [ Reject ]                   [ Approve ] │
└──────────────────────────────────────────┘
```
States: pending, applying, applied, rejected, expired ("Your order changed; ask again"). Approve is the only path to mutation.

## 4. Admin screens

| # | Screen | Key elements |
|---|---|---|
| A1 | Order management | Filter by status, list with event date/guests/total, detail with frozen snapshot, Approve / Reject + note |
| A2 | Dishes & categories | Table/cards, create/edit form, image upload, dietary + allergen editor with explicit Unknown option |
| A3 | Pricing configuration | Pricing unit, unit price, unit label per dish; bulk view |
| A4 | Availability | Blocked dates; slot capacity; owner settings (child portion, lead days) |
| A5 | Pickup & delivery | Time slots per weekday and type; delivery zones with fees |

## 5. Frontend structure

```
frontend/
  customer/index.html   # C1–C5 (single page, JS-driven steps)
  admin/index.html      # A1–A5
  index.html            # landing page
  menu/index.html       # public menu, read-only
  css/base.css          # tokens, reset, primitives, app-screen components
  css/home.css          # landing page only
  js/api.js             # fetch wrapper, error format handling
  js/illustrations.js   # line-art SVG set
  js/motion.js          # reveals, draw-in, tilt, photo band parallax, phone nav toggle
  js/home.js            # landing page: hero table, 3D ring
  js/public-menu.js     # public menu page
  assets/img/           # Unsplash placeholders until real photography [OPEN #20]
```
Reusable components as small ES modules (e.g., `js/components/dish-card.js`) added in later phases.
