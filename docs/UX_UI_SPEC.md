# UX/UI Specification

Status: **v1.0, the Stitch redesign** (ADR 0008). The site belongs to one caterer, טעם של יחד. The UI is Hebrew and RTL. The design reference is the Stitch export in `stitch_catering_website_ux_design/` (kept out of git); its tokens are in `culinary_elegance/DESIGN.md`.

## 1. Principles

- Hebrew RTL throughout: `<html lang="he" dir="rtl">`, prices and phone numbers in `<bdi>` so they read correctly.
- One responsive application: phones under 768 px, tablets 768–1179 px, computers from 1180 px.
- Accessibility target WCAG 2.2 AA: 4.5:1 text contrast, visible focus, 44×44 px touch targets, a label on every input, errors linked to their field (`aria-invalid`, `aria-describedby`), `aria-live` for status and filter results, full keyboard use, a skip link.
- CSS uses logical properties only. `prefers-reduced-motion` is respected.
- Never show a pending quotation as a confirmed booking. Status uses explicit text ("ממתין לאישור הקייטרינג").
- Data the site doesn't have is never invented: no ratings, no "chef recommended" badges, no preparation times. Unknown dietary facts and calories show "לא צוין"; filters match only confirmed values.
- The URL fragment holds the private order token, so in-page navigation never uses `#` links. Steps are kept in browser history, so Back and Forward move between steps.

## 2. Design system

Defined in `frontend/css/base.css`, from Stitch "Culinary Elegance":

| Token | Value | Use |
|---|---|---|
| `--primary` | `#00162d` | Main buttons, headings, selected states |
| `--secondary` | `#8b5000` | Accent text, links, icons (6:1 on white). The caterer's brand colour replaces it when readable on white |
| `--secondary-container` | `#fd9d2b` | Warm fills: the hero's main button, step markers, counters. Text on it uses `--on-secondary-container` |
| `--tertiary` / success | `#00513b` | Vegetarian and vegan tags, approved status |
| Surfaces | `#f9f9ff`, `#f1f3ff`, `#e8eeff`, white cards | Page, fields, chips, cards |
| Font | Rubik 300–800, self-hosted (`frontend/fonts/`) | All text |
| Radius | 8 / 12 / 16 / 24 px, pills for chips and steppers | |

Icons are Material Symbols SVGs in `frontend/img/icons/` (Apache 2.0), drawn as CSS masks (`css/icons.css`). There's no icon font and nothing from a CDN.

## 3. Customer screens

All at `/` (and `/c/{slug}/`), one page with JS-driven views.

| # | Screen | Stitch reference | Key elements |
|---|---|---|---|
| C0 | Homepage | `_9` | Full-height hero with `media/hero.mp4` (behaviour below), kashrut chip from data, headline, "לצפייה בתפריט" and "לתכנון האירוע שלכם". Feature strip, three real dishes from the menu, "מתכננים אירוע בקרוב?" card |
| C1 | Event details | `_3`, `_5` | Step 1 of 3. Customer, guests (counters for adults and children, diet counts out of them), notes, when and how. Inline Hebrew errors, focus moves to the first error. What's typed is kept when leaving the step; with an order, leaving saves it |
| C2 | Menu | `_8`, `_7`, `_1` | Category tabs (single choice, "הכל" first), diet chips combined with AND: בשרי, חלבי, פרווה, צמחוני, טבעוני, ללא גלוטן (only an allergen marked "free"). Live result count, empty state with "ניקוי הסינון". Every category uses the dessert page's card layout |
| C2a | Dish card | `_8`, `_1` | Photo on the outer edge with kashrut and unit badges, name, price per unit, description, tags (vegan / vegetarian, kashrut, calories), "מידע על אלרגנים", recommended quantity, "הוסף להזמנה" or a stepper with "בהזמנה" |
| C2b | Dish sheet | none | Large photo, facts, quantity, allergens (contains / free / unknown with a warning) |
| C3 | Live order | `_8`, `_4` | Customer and pickup/delivery, event date (opens C1), lines with photo, stepper and remove, totals from the backend, main action, the assistant button. Phones: bottom bar with total and "ההזמנה שלי (n)", opening a bottom sheet |
| C4 | Summary | `_4` | Step 3 of 3. Chosen dishes, event facts with "עריכה", meat + dairy warning (tick to continue) or block, private link with copy and WhatsApp, "not a final order" notice, submit |
| C5 | Status | none | Pending / approved / rejected with icon, help text, the caterer's note, refresh, phone, event facts, frozen lines, private link |
| C6 | AI assistant | none | Bottom sheet on phones, floating panel on computers. Proposal cards; Approve is the only path to a change |
| C7 | Not available | none | Hebrew message and "ניסיון נוסף" |

Browsing the menu needs no details. Pressing "הוסף להזמנה" before there's an order opens C1 with a notice; after saving, that dish is added.

### Layout

- Header on every view: logo, name, kashrut status, navigation ("תפריט ואירוע", "ההזמנה שלי", "אודות"), phone pill when a phone is set.
- Computers: three columns. The side column on the right (welcome, steps, categories, a help card with the phone), the menu or form in the middle, the live order on the left (DESIGN.md). Both side columns stick below the header.
- Tablets: a steps strip above two columns, the content and the live order.
- Phones: a steps strip, one column, the bottom bar.

### Homepage video

`frontend/js/customer/hero.js`. The source footage ends in a bright streak, so it never loops natively.

- Speed 0.6. Two layers of the same in-memory copy (one download) take turns: just before the streak (`CUT = 4.15 s`) the waiting layer starts and fades in over 0.6 s on top of the playing one, so the picture never dips to a blank or solid colour.
- Text and buttons sit above the video and never move. A gradient behind the text keeps it readable.
- The still photo shows until the video can play, with reduced motion, when the codec isn't supported, and if loading fails. Leaving the homepage stops the loop and frees the memory.

## 4. Admin screens

At `/admin/`. A sidebar on computers (logo, name, kashrut, navigation with a count of orders waiting, "צפייה באתר", "יציאה"), a top bar with scrolling navigation on phones.

| # | Screen | Stitch reference | Key elements |
|---|---|---|---|
| A0 | Login | none | The site's logo and name, email and password, Hebrew error, link back to the site |
| A1 | Orders | `_2` | Today's date, a status filter with counts, counters (waiting, guests in waiting orders, approved, rejected), order cards with status colour, date, guests, total, "פתיחה". Detail: customer and event, lines, total, Approve / Reject with a note (required to reject) |
| A2 | Menu | none | Categories as cards, dishes with price, kashrut and calories, edit and delete, dish form with photo, dietary facts and allergens with an explicit Unknown |
| A4 | Availability | none | Time slots per weekday and type, blocked dates |
| A5 | Delivery | none | Zones with fees and cities |
| A6 | Business profile | none | Site link with copy, name, phone, alert email, brand colour, kashrut status and certificate, meat + dairy rule, logo |
| A7 | Quantity rules | none | Defaults per category, editable, with revert |

`_2` also shows kitchen statuses, revenue, manual orders, printing and search. The app has none of these, so they aren't shown.

## 5. Frontend structure

```
frontend/
  customer/index.html   # C0–C7, served at / and /c/{slug}/
  admin/index.html      # A0–A7
  css/base.css          # design system: tokens, fonts, buttons, fields, cards, steppers, dialogs
  css/icons.css         # one class per icon
  css/customer.css      # header, hero, layout, menu, live order, summary, chat
  css/admin.css         # sidebar, orders, dashboard forms
  js/customer/main.js   # views and order flow
  js/customer/hero.js   # homepage video loop
  js/customer/chat.js   # assistant
  fonts/                # Rubik (OFL)
  img/brand/logo.jpg    # the site's logo, used when the caterer hasn't uploaded one
  img/icons/            # Material Symbols (Apache 2.0)
  media/                # hero.mp4 and its still photo
```
