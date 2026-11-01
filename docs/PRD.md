# Product Requirements Document — AI Catering Platform (MVP)

Status: **Draft v0.2** · Phase 2 deliverable · Replaces the single-business v0.1

Legend: **[CONFIRMED]** = decided by the product owner · **[RECOMMENDATION]** = engineering proposal, changeable · **[OPEN]** = needs a business decision (see `OPEN_DECISIONS.md`).

---

## 1. Purpose

A web platform for **many catering businesses**. Each caterer gets a branded link to send to their customers. A customer uses that link to build a catering order, gets a deterministic price quotation, and gets help from a Hebrew AI assistant that can *propose* (never silently apply) changes to their order. The caterer manages their own catalog and approves or rejects every quotation.

## 2. Users

| Persona | Description | Interface |
|---|---|---|
| Customer | A private individual planning a private event (birthday, family celebration, Bar/Bat Mitzvah, Shabbat, …), ordering from one caterer | Customer application, on the caterer's link |
| Caterer | Runs one catering business on the platform; manages menu, pricing, logistics, and approves quotations | Caterer dashboard |
| Platform operator | Us. Sets up pilot caterers by hand with an internal script; has no UI in the MVP | Internal tooling |

**[CONFIRMED]**

## 3. Confirmed decisions (summary)

| # | Decision | Product implication |
|---|---|---|
| 1 | Many caterers | Every business record belongs to exactly one caterer; caterers can never see each other's data |
| 2 | Caterer approval | Customer submits a quotation; only the caterer approves/rejects; AI can never approve |
| 3 | Private events only | No B2B, corporate accounts, invoicing, procurement |
| 4 | Free menu selection | Customer picks from that caterer's catalog; AI may recommend existing dishes only |
| 5 | Quantity calculation | Recommended quantities from guest composition, using platform default rules each caterer can edit |
| 6 | Mixed pricing | Per guest / per tray / per weight unit / per item; separate delivery fee; deterministic backend calculation |
| 7 | Proactive AI with explicit approval | AI proposes; customer approves each change; backend executes |
| 8 | Pickup & delivery | Dates/times, delivery zones, delivery fees; no staff/on-site service |
| 9 | Dietary info | Meat/dairy/pareve, vegetarian, vegan, known allergens, calories per portion; unknown ≠ allergen-free, and an empty calorie value is shown as unknown |
| 10 | Full caterer dashboard | Dishes, categories, prices, units, descriptions, images, dietary info, orders, approvals, availability, blocked dates, time slots, delivery zones/fees, business profile |
| 11 | Branded link per caterer | Customers enter at `/c/{slug}/`. No marketplace, directory, or caterer comparison |
| 12 | Manual onboarding | Pilot caterers are created by us. No self-serve signup or subscription billing in the MVP |
| 13 | Text chat only | Voice comes after the MVP |
| 14 | Hebrew product | UI and AI are Hebrew with RTL layout. Code and technical docs stay in English |
| 15 | No customer account | Customer gives name and phone and returns through a private link. The phone is not verified |
| 16 | No in-app payments | The flow ends at an approved quote. The caterer collects payment outside the app |
| 17 | Kashrut per caterer | Each caterer records their kashrut status and certificate, tags dishes, and chooses whether a meat + dairy order is blocked or only warned about |

## 4. Customer flow **[CONFIRMED]**

1. **Entry** — customer opens the caterer's link and sees that caterer's branding and menu.
2. **Event configuration** — name, phone, event type, event date, requested pickup/delivery time, guest composition (adults, children, vegetarian, vegan, other dietary restrictions), dietary requirements, pickup or delivery, delivery address when applicable.
3. **Menu browsing** — categories → dishes with price, pricing unit, dietary properties, calories, image, description.
4. **Quantity recommendation** — backend-computed from the caterer's rules.
5. **Pricing** — itemized calculation; total updates after every approved change.
6. **AI assistance** — Hebrew text chat embedded in the ordering flow, with access to the current order through controlled backend operations.
7. **Kashrut check** — a meat + dairy order is blocked or warned about, per the caterer's setting.
8. **Quote submission** — order becomes a quotation request (`pending_approval`).
9. **Caterer approval** — caterer approves/rejects. A pending quotation is never shown as a confirmed booking.

The customer returns to a draft or quote at any point through the order's private link.

## 5. Caterer dashboard capabilities **[CONFIRMED]**

- CRUD dishes and categories; descriptions and images (Supabase Storage).
- Prices and pricing units.
- Dietary metadata, including calories per portion.
- View orders; approve/reject quotations.
- Availability and blocked dates.
- Pickup and delivery time slots.
- Delivery zones and delivery fees.
- Quantity rules (edit the platform defaults).
- Business profile: name, logo, colors, kashrut status and certificate, meat + dairy mixing rule.

A caterer account sees only its own caterer's data. No caterer-facing AI agent. **[CONFIRMED]**

## 6. AI assistant requirements **[CONFIRMED]**

Can: answer questions about the caterer's available dishes, recommend existing dishes, flag potentially missing categories, suggest quantity adjustments, explain pricing impact, flag known dietary conflicts, quote stored calorie values, propose add/remove dish, propose quantity changes, propose order-detail updates.

Must not: invent dishes, prices, dietary properties, calories, availability; use data from another caterer; modify an order without explicit customer approval; approve orders; treat unknown allergen data as safe.

Details: `AI_AGENT_DESIGN.md`.

## 7. Order states **[RECOMMENDATION]**

`draft → pending_approval → approved | rejected`. No payment, cancellation, or revision states without approval.

## 8. Non-functional requirements

| Area | Requirement | Tag |
|---|---|---|
| Tenant isolation | No caterer can read or change another caterer's data; enforced in the backend and covered by automated tests | CONFIRMED |
| Source of truth | Database/backend authoritative for prices, quantities, order state | CONFIRMED |
| Determinism | All pricing/quantity math in backend code, not the LLM | CONFIRMED |
| Security | Secrets in env vars only; typed validation on every state change; no arbitrary DB ops from model output | CONFIRMED |
| Private links | Long random token, stored hashed; order IDs alone grant nothing | RECOMMENDATION |
| AI cost | Per-caterer usage limits on chat | RECOMMENDATION |
| UX | Hebrew RTL, mobile-first, responsive, accessible (WCAG 2.2 AA target), premium look | CONFIRMED / target RECOMMENDATION |
| Quote integrity | Price snapshot at submission | CONFIRMED |
| Testing | pytest, Ruff, API integration tests, AI action validation tests, cross-caterer access tests | CONFIRMED |
| Environments | `dev` → Railway dev + Supabase dev; `main` → Railway prod + Supabase prod | CONFIRMED (separate Supabase projects strongly preferred) |

## 9. Out of scope **[CONFIRMED]**

Marketplace or caterer directory · self-serve caterer signup · subscription billing · platform-operator UI · caterer-facing AI agent · voice AI · alcohol · disposable serving ware · corporate customers · staff/waiter management · advanced inventory · supplier procurement · accounting/invoicing · payment gateway · customer accounts · English UI · automated dish generation · autonomous order approval · native mobile apps.

Unresolved and **not** to be built until decided: customer notifications, cancellation/refund, caterer-proposed revisions, post-submission customer edits.

## 10. Success criteria for MVP (proposed) **[RECOMMENDATION]**

- A customer can open a caterer's link and build and submit a quotation end-to-end on a phone, in Hebrew.
- Every AI-originated change appears as a diff card and executes only after approval, exactly once, against the current order version.
- A caterer can manage their full catalog and approve/reject quotations without developer help.
- Submitted quotations are unaffected by later catalog price changes.
- Automated tests show no cross-caterer data access on any endpoint.
- A real pilot caterer receives a real quote request.
