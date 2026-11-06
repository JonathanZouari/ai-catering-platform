# Open Business Decisions

These must be answered by the business before the dependent features are built. Engineering will not invent answers. Unrelated infrastructure work continues meanwhile.

Format: **Question** · *Why it matters* · **Blocks**

| # | Topic | Question | Why it matters | Blocks |
|---|---|---|---|---|
| 1 | Customer authentication / guest checkout | **Partly decided (see log):** staff and customers log in with Supabase Auth, and the private order link stays. Still open: how does a new customer sign up and get linked to their existing customer record (phone OTP before linking)? Is an account required, or optional? | Determines ownership model, RLS policies, and how a customer returns to a draft/quote | Phase 3 order ownership, Phase 4 chat history |
| 2 | Payment & deposit | Is any deposit or payment collected in-app? | Payments are out of scope unless approved | Nothing in MVP unless approved |
| 3 | Serving & quantity formulas | Per category/dish, how much per adult / child? Rounding (e.g., whole trays)? Different for vegetarian/vegan guests? | Quantity recommendation must use business rules, not AI guesses | Phase 3 quantity engine (schema can hold rules; values unknown) |
| 5 | Availability & capacity | Capacity model decided (guests per day, see log). Still open: the default daily guest limit, minimum lead time, same-day orders? | Defines date/slot validation | Phase 2 availability rules, Phase 3 date picker |
| 6 | Quote modification & negotiation | Can the owner edit or counter-propose a quote, or only approve/reject? | Adds states and UI | Out of MVP until decided |
| 7 | Cancellation & revision | Can a customer cancel or edit after submission or approval? Deadlines? | Adds states and rules | Out of MVP until decided |
| 8 | Allergen verification & cross-contamination | What disclaimer text is shown? Is there a "may contain" level? Who verifies allergen data? | Safety and liability wording | Phase 2 allergen fields' semantics, Phase 4 agent wording |
| 9 | Kashrut certification | Mixing decided (see log). Still open: which certification(s)? Shown per dish or business-wide? | Affects data model and validation | Phase 2 dish fields, Phase 3 conflict checks |
| 10 | Disposable serving equipment | Are utensils/disposables orderable? Priced how? | Could be catalog items or separate | Out of MVP until decided |
| 11 | Alcohol | Offered at all? Age verification? | Legal implications | Out of MVP until decided |
| 13 | Notification channels | Email, SMS, WhatsApp, none? For which events (submitted, approved, rejected)? | Third-party providers and cost | Out of MVP until decided |
| 15 | Minimum order quantities | Minimum per dish, per order, or minimum guests? Minimum for delivery? | Validation rules | Phase 2/3 validation |
| 16 | LLM provider | Which model provider (e.g., Anthropic Claude) and budget? | API keys, tool-calling format, cost | Phase 4 |
| 17 | Currency | Single currency (e.g., ILS)? Display format? | Money formatting and storage | Phase 2 pricing fields (stored as integer agorot + `settings.currency`, default ILS, until decided) |
| 20 | Brand | Business name, logo, colors, fonts | Visual identity | Phase 3 UI polish (neutral tokens until then) |

## Decision log

When a decision is made, record it here and move the row out of the table above.

| Date | # | Decision | Decided by |
|---|---|---|---|
| 2026-10-29 | 12 | Interface language is **Hebrew only, RTL**. AI responses must also be in Hebrew. | Project owner (chat) |
| 2026-11-02 | 4 | Vegetarian, vegan and restricted guests are **subsets** of adults + children and mutually exclusive (a vegan is not also counted as vegetarian). | Proposed in DB planning (PR from galitbental), **pending owner confirmation** |
| 2026-11-02 | 5 (part) | Kitchen capacity is a **maximum number of guests per day**: a default in settings plus per-date overrides. Time slots have no capacity. Pending and approved orders count. | Proposed in DB planning (PR from galitbental), **pending owner confirmation** |
| 2026-11-02 | 14 (part) | Catalog prices **include VAT**. The VAT rate and VAT amount are frozen on the order at submission. | Proposed in DB planning (PR from galitbental), **pending owner confirmation** |
| 2026-11-02 | 19 | Delivery zones are **lists of cities**; each zone has one fee. The customer picks a city from the list. | Proposed in DB planning (PR from galitbental), **pending owner confirmation** |
| 2026-11-02 | 14 | Each order line is rounded half up to the agora; the total is the exact sum of lines plus the delivery fee, with no further rounding. | Proposed in DB planning (PR from galitbental), **pending owner confirmation** |
| 2026-11-02 | 9 (part) | Meat and dairy dishes **may be mixed** in one order, with a warning to the customer and a flag for the owner. | Proposed in DB planning (PR from galitbental), **pending owner confirmation** |
| 2026-11-02 | 18 | Weight-based dishes are priced **per 100 g**. | Proposed in DB planning (PR from galitbental), **pending owner confirmation** |
| 2026-11-02 | — | One phone number = one customer (`customers.phone` unique). | Proposed in DB planning (PR from galitbental), **pending owner confirmation** |
| 2026-11-02 | — | AI chat messages are deleted **90 days after the event date**; suggestions and their outcome stay with the order. Customers are told in the chat. | Proposed in DB planning (PR from galitbental), **pending owner confirmation** |
| 2026-11-05 | 1 (part) | Staff **and customers** log in with **Supabase Auth** (email + password). Staff = active `staff_users` row; customer = `customers.auth_user_id`. | Requested in a Claude Code session |
| 2026-11-05 | — | Staff see orders update **live** (Supabase Realtime on `orders` and `order_events`); customers see their own orders live. | Requested in a Claude Code session |
| 2026-11-06 | — | **SQLite dropped.** The database is Supabase Postgres in every environment; schema in `supabase/migrations/`, with enum types, `jsonb` and RLS (ADR-0002 revised). | Requested in a Claude Code session |
