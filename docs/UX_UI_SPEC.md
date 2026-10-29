# UX/UI Specification (initial structure)

Status: **Draft v0.1**. High-fidelity prototypes (Claude Artifacts) come in the UI phase; brand, colors, and language are **[OPEN #12, #20]**.

## 1. Principles

- Mobile-first; breakpoints 640 / 1024 px **[RECOMMENDATION]**.
- Accessibility target WCAG 2.2 AA: 4.5:1 text contrast, visible focus, 44×44 px touch targets, labels on all inputs, `aria-live` for price totals and chat replies, full keyboard use.
- Direction-agnostic CSS (logical properties: `margin-inline-start`, etc.) so RTL can be enabled without rewrites.
- Premium but calm: generous whitespace, one accent color, restrained motion, `prefers-reduced-motion` respected.
- Never show a pending quotation as a confirmed booking — status badges use explicit text ("Awaiting business approval").

## 2. Design tokens — proposal "Charcoal & Gold" **[PROPOSAL for OPEN #20]**

Defined in `frontend/css/base.css` as CSS custom properties: color (`--color-bg`, `--color-surface`, `--color-surface-2`, `--color-border`, `--color-line`, `--color-text`, `--color-muted`, `--color-accent`, `--color-accent-glow`, `--color-on-accent`, `--color-success`, `--color-danger`, `--color-warning`), spacing scale (4-px based), radii, shadow levels, and two font stacks.

| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#111111` | Page background (charcoal) |
| `--color-surface` | `#1a1a1a` | Cards, info bar |
| `--color-text` | `#f4f1ea` | Body text, warm white (≈16:1 on bg) |
| `--color-muted` | `#a9a49a` | Secondary text (≈7.5:1 on bg) |
| `--color-accent` | `#d9b95c` | The single accent: gold icons, highlights, primary buttons (≈10:1 on bg) |
| `--color-accent-glow` | gold @ 35% | Soft glow on the info bar and button hover |
| `--font-display` | Bellefair | Elegant thin display font for headings (covers Latin **and Hebrew**) |
| `--font` | Heebo 300/400 | Body text (covers Latin **and Hebrew**, ready for #12) |

Visual motifs, inspired by elegant dark restaurant sites: large thin-serif hero title with one gold word; round food photos on the dark canvas with a subtle "flour dust" speckle (`.plate`); a glowing info bar with gold line icons (`.info-bar`); an outlined title with an offset echo (`.outline-title`); alternating photo/text dish rows (`.dish-row`); thin outlined buttons that glow gold on hover (`.btn`); a services row with gold line icons; a split feature card with a photo (`.feature-card`). The theme is dark-only; a light variant is not in scope unless requested. Food photos are Unsplash placeholders until the business supplies its own.

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
  customer/index.html   # C1–C5 (single page, JS-driven steps)
  admin/index.html      # A1–A5
  css/base.css          # tokens, reset, primitives
  js/api.js             # fetch wrapper, error format handling
  assets/
```
Reusable components as small ES modules (e.g., `js/components/dish-card.js`) added in later phases.
