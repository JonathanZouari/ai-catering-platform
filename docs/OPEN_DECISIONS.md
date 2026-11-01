# Open Business Decisions

These must be answered by the business before the dependent features are built. Engineering will not invent answers. Unrelated infrastructure work continues meanwhile.

Where a working default is listed, engineering may build on it, but it stays open until confirmed.

| # | Topic | Question | Why it matters | Working default | Blocks |
|---|---|---|---|---|---|
| 3 | Default quantity values | What are the platform default portions per category, per adult and child? Rounding (e.g., whole trays)? Different for vegetarian/vegan guests? | Decided that defaults exist and caterers can edit them; the values themselves are still needed | Drafted by engineering, flagged as unvalidated until a pilot caterer reviews them | Phase 5 quantity engine |
| 5 | Availability & capacity | Max orders/guests per day or per slot? Lead time? Same-day orders? | Defines date/slot validation | Set per caterer | Phase 4 availability rules, Phase 5 date picker |
| 6 | Quote modification & negotiation | Can the caterer edit or counter-propose a quote, or only approve/reject? | Adds states and UI | Approve/reject only | Out of MVP until decided |
| 7 | Cancellation & revision | Can a customer cancel or edit after submission or approval? Deadlines? | Adds states and rules | Not supported | Out of MVP until decided |
| 8 | Allergen verification & cross-contamination | What disclaimer text is shown? Is there a "may contain" level? Who verifies allergen data, the caterer or the platform? | Safety and liability wording, now also between platform and caterers | Contains / free / unknown, with a draft disclaimer pending legal review | Phase 4 allergen fields' semantics, Phase 7 agent wording |
| 13 | Notification channels | Email, SMS, WhatsApp, none? For which events (submitted, approved, rejected)? How does the customer get their private link back if they lose it? | Third-party providers and cost | None; link shown on screen and shareable | Out of MVP until decided |
| 15 | Minimum order quantities | Minimum per dish, per order, or minimum guests? Minimum for delivery? | Validation rules | Set per caterer | Phase 4/5 validation |
| 16 | LLM budget | What monthly AI cost per caterer is acceptable, and what happens at the limit? | Sets usage limits and model choice | Claude; model chosen once costs are measured | Phase 7 |
| 18 | Weight unit | kg, 100 g, or configurable per dish? | Per-weight pricing math | Configurable per dish | Phase 4 pricing units |
| 19 | Delivery zone definition | Zones by city list, postal code, or radius/polygon? | Address → zone lookup method | City list per caterer | Phase 4 delivery zones |
| 20 | Platform brand | Product name, domain, logo | Platform identity; caterer branding is per caterer | "Yummai" as placeholder | Phase 8 |
| 22 | Pilot caterer | Which real caterer is the first pilot? | Validates the defaults and the Phase 8 success criterion | None | Phase 8 |
| 23 | Platform revenue model | How will caterers pay for the platform after the pilot? | No MVP work, but pricing may shape limits and analytics | Free during pilot | Nothing in MVP |

## Decision log

| Date | # | Decision | Decided by |
|---|---|---|---|
| 2026-11-01 | — | Product is for many caterers, overturning the single-business assumption | Product owner |
| 2026-11-01 | — | Customers enter through a branded link per caterer; no marketplace | Product owner |
| 2026-11-01 | — | Multi-tenant from day one; pilot caterers onboarded by hand; no self-serve signup or billing | Product owner |
| 2026-11-01 | — | Calories per dish are in the MVP | Product owner |
| 2026-11-01 | — | Voice AI deferred; text chat only in the MVP | Product owner |
| 2026-11-01 | 1 | No customer account: name, phone, and a private link | Product owner |
| 2026-11-01 | 2 | No payments or deposits in the app | Product owner |
| 2026-11-01 | 3 | Platform default quantity rules, editable per caterer (default values remain open) | Product owner |
| 2026-11-01 | 9 | Kashrut per caterer: status and certificate on the caterer, meat/dairy/pareve per dish, mixing rule block or warn per caterer | Product owner |
| 2026-11-01 | 10 | Disposable serving ware deferred until after the MVP | Product owner |
| 2026-11-01 | 11 | Alcohol deferred until after the MVP | Product owner |
| 2026-11-01 | 12 | Product is Hebrew only with RTL; code and technical docs stay in English | Product owner |
| 2026-11-01 | 16 | Provider default is Anthropic Claude (budget remains open) | Engineering default |
| 2026-11-01 | 17 | Currency is ILS | Engineering default, confirm with pilot |
| 2026-11-02 | 4 | Vegetarian, vegan and restricted guests count within the adult and child totals | Product owner |
| 2026-11-02 | 14 | Catalog prices include VAT with no separate line; totals round half-up to 2 decimals (confirm with an accountant before launch) | Product owner |
| 2026-11-02 | 21 | "אס]קה" meant אספקה, already covered by pickup and delivery | Product owner |
