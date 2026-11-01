# UX/UI Specification (initial structure)

Status: **Draft v0.1**. High-fidelity prototypes (Claude Artifacts) come in the UI phase; brand, colors, and language are **[OPEN #12, #20]**.

## 1. Principles

- Mobile-first; breakpoints 640 / 1024 px **[RECOMMENDATION]**.
- Accessibility target WCAG 2.2 AA: 4.5:1 text contrast, visible focus, 44×44 px touch targets, labels on all inputs, `aria-live` for price totals and chat replies, full keyboard use.
- Direction-agnostic CSS (logical properties: `margin-inline-start`, etc.) so RTL can be enabled without rewrites.
- Premium but calm: generous whitespace, one accent color, restrained motion, `prefers-reduced-motion` respected.
- Never show a pending quotation as a confirmed booking — status badges use explicit text ("Awaiting business approval").

## 2. Design tokens ("Butter & Ink" proposal)

Defined in `frontend/css/base.css` as CSS custom properties: color (`--color-bg`, `--color-surface`, `--color-text`, `--color-muted`, `--color-accent`, `--color-highlight`, `--color-success`, `--color-danger`, `--color-warning`, `--color-line`), spacing scale (4-px based, `--space-1` … `--space-16`), radii (`--radius` controls, `--radius-frame` photos and cards, `--radius-pill` chips and status), type scale (`--text-sm` … `--text-3xl`), `--target: 44px`. Measured contrast ratios are listed at the top of the file. Shadows are not used; depth comes from colour blocks and ink borders. Dark mode not in scope unless requested.

Fonts are self-hosted under `frontend/assets/fonts/` (OFL): **Rubik** for all UI text and **Rubik Doodle Shadow** for large display titles only (Hebrew subset). The palette and fonts are a proposal until brand is decided **[OPEN #20]**. Design source (Stitch screens): `docs/design/butter-ink/`.

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
| A4 | Availability | Calendar of blocked dates; capacity **[OPEN #5]** |
| A5 | Pickup & delivery | Time slots per weekday and type; delivery zones with fees |

## 5. Frontend structure

```
frontend/
  index.html            # landing page
  customer/index.html   # C1–C5 (single page, hash-routed steps; C4 is a <dialog>)
  admin/index.html      # A1 orders, A2 dishes (A3 pricing is part of A2); A4–A5 not built yet
  css/base.css          # tokens, reset, primitives
  css/home.css, customer.css, admin.css   # page styles
  js/api.js             # fetch wrapper, error format handling
  js/customer.js, admin.js                # page logic
  js/dom.js             # element builder (text via textContent only)
  js/format.js          # Intl price/date formatting, one locale setting
  js/sample-data.js     # SAMPLE DATA until the catalog/order APIs exist
  assets/fonts/, illustrations/, photos/
```
Until Phase 2–3, pages run on `js/sample-data.js` and compute totals for display only; the backend stays authoritative (ADR 0003). Reusable components as small ES modules (e.g., `js/components/dish-card.js`) added in later phases.
