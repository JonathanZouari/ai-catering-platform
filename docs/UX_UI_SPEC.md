# UX/UI Specification (initial structure)

Status: **Draft v0.2**. High-fidelity prototypes (Claude Artifacts) come in the UI phase. The UI is Hebrew and RTL. Platform brand is **[OPEN #20]**; caterer branding is per caterer.

## 1. Principles

- Hebrew RTL throughout: `<html lang="he" dir="rtl">`, Hebrew-capable fonts, prices and phone numbers isolated so they read correctly in RTL text. The sketch below is in English for this doc only.
- Each customer page carries the caterer's logo and color. The Yummai logo (a smiling serving dome) appears on every page, small and above the caterer's own logo. The app floats on the blue backdrop with a margin of 5% of the width and 7% of the height on computers. A caterer color that fails contrast is not applied to text.
- Mobile-first; breakpoints 640 / 1024 px **[RECOMMENDATION]**.
- Accessibility target WCAG 2.2 AA: 4.5:1 text contrast, visible focus, 44×44 px touch targets, labels on all inputs, `aria-live` for price totals and chat replies, full keyboard use.
- CSS uses logical properties only (`margin-inline-start`, etc.).
- Premium but calm: generous whitespace, one accent color, restrained motion, `prefers-reduced-motion` respected.
- Never show a pending quotation as a confirmed booking — status badges use explicit text ("ממתין לאישור הקייטרינג").

## 2. Design tokens (neutral placeholders)

Defined in `frontend/css/base.css` as CSS custom properties: color (`--color-bg`, `--color-surface`, `--color-text`, `--color-muted`, `--color-accent`, `--color-success`, `--color-danger`, `--color-warning`), spacing scale (4-px based), radius, font stack (system fonts until brand fonts chosen), shadow levels. Dark mode not in scope unless requested.

### Visual direction

The look follows the product owner's example: one frame with three columns on computers.

- The page background is deep blue with soft shapes and a dot pattern, in CSS only. The app floats on it as one rounded card.
- Side column: logo in a circle, a welcome line, the steps, and the menu categories. Without a logo the circle shows the caterer's initial.
- Middle column: large horizontal dish cards with the photo filling one side, price in the opposite corner, and a small quantity control with a bag icon.
- Order column: customer name, event date (which returns to the details step), order tiles, totals, and a wide black button. On phones it opens from the bottom bar.
- Main buttons are black. Blue `#2563eb` is only for accents, and a caterer's brand colour replaces it on customer pages if it is readable on white.
- Icons are same-origin SVG masks in `frontend/img/`. No icon library and no third-party fonts.
- Without a photo, dish cards show a grey block with the dish's first letter.
- A dish card opens a detail sheet with the large photo, allergens and quantity. Allergen information stays one tap from every card.
- No star ratings or preparation times: the app has no such data.
- Category navigation scrolls by script, never by a `#` link, because the URL fragment holds the private token.

## 3. Customer screens

| # | Screen | Key elements |
|---|---|---|
| C1 | Event configuration | Caterer header with kashrut status; stepper; name and phone; event type, date (blocked dates disabled), time slot, guest composition counters with helper text (subset rule **[OPEN #4]**), dietary notes, pickup/delivery toggle, address + zone fee preview |
| C2 | Dish catalog | Category tabs/chips, dish cards (image, name, price + unit, kashrut badge, veg/vegan badges, calories or "לא צוין", "allergen info" link), filters, add/quantity stepper |
| C3 | Order summary & pricing | Itemized lines (qty × unit price = line), recommendation hints, meat + dairy warning or block per the caterer's rule, delivery fee, total, `version`-safe edits |
| C4 | AI assistant | Desktop: side panel next to C2/C3. Mobile: bottom sheet opened by a persistent button. Message list, input, proposal cards inline. Draft orders only; shown as unavailable when no key is set or a limit is reached |
| C5 | Quote submission & status | Review, explicit "Submit quotation request", status page: Draft / Awaiting approval / Approved / Rejected + caterer note. Shows the private link with a copy and WhatsApp share action and a notice to keep it private. Phase 5 shows dishes grouped by category with vegetarian and vegan filters, and a warning that must be ticked, or a block, when the order mixes meat and dairy |

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
| A1 | Order management | First screen after login. Filter by status (waiting first), list with event date/guests/total, detail with frozen snapshot, customer phone, Approve / Reject + note (required to reject). Drafts aren't shown |
| A2 | Dishes & categories | Table/cards, create/edit form, image upload, dietary + allergen editor with explicit Unknown option, calories per portion |
| A3 | Pricing configuration | Pricing unit, unit price, unit label per dish; bulk view |
| A4 | Availability | Calendar of blocked dates; capacity **[OPEN #5]** |
| A5 | Pickup & delivery | Time slots per weekday and type; delivery zones with fees |
| A6 | Business profile | Name, logo, color, customer link with copy action, kashrut status and certificate, meat + dairy rule (block / warn) |
| A7 | Quantity rules | Platform defaults per category, editable, with a revert-to-default action |

## 5. Frontend structure

```
frontend/
  customer/index.html   # C1–C5, served at /c/{slug}/ (single page, JS-driven steps)
  admin/index.html      # A1–A7
  css/base.css          # tokens, reset, primitives
  js/api.js             # fetch wrapper, error format handling
  assets/
```
Reusable components as small ES modules (e.g., `js/components/dish-card.js`) added in later phases.
