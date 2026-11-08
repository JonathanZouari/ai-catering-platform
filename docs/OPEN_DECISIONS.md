# Open Business Decisions

These must be answered by the business before the dependent features are built. Engineering will not invent answers. Unrelated infrastructure work continues meanwhile.

Format: **Question** · *Why it matters* · **Blocks**

| # | Topic | Question | Why it matters | Blocks |
|---|---|---|---|---|
| 12 | Interface languages | ~~Hebrew only, English only, or both? RTL required?~~ **Decided 2026-11-01: Hebrew, RTL** (chosen with the "Table Journal" design). English is not planned. | Layout, copy, and AI response language | Resolved (AI response language follows: Hebrew) |
| 20 | Brand | Business name, logo, colors, fonts. **Decided 2026-11-01: name "Yummai", colors and fonts per the "Table Journal" direction (UX_UI_SPEC §2).** Still open: logo, real food photography. **2026-11-08:** the owner can upload a photo per dish in the admin screen (Supabase Storage); until then dishes show Unsplash placeholders labelled "תמונה להמחשה" (illustrative photo), which an upload replaces | Visual identity | Logo and real dish photos only (placeholders until then) |

## Decision log

When a decision is made, record it here and move the row out of the table above.

| Date | # | Decision | Decided by |
|---|---|---|---|
| 2026-11-05 | 10 | Disposables (place settings, serving trays) are **optional catalog items** the customer adds and pays for: the owner keeps them in their own category, priced per guest or per item. No extra code. Reusable rentals are out of scope. | Business owner |
| 2026-11-05 | 11 | **Alcohol is sold** (the business is licensed) **to 18+ only**. The owner marks a dish as alcohol; submitting an order that contains one needs the customer's 18+ confirmation (`422 age_confirmation_required`), recorded in `orders.adult_confirmed_at`, and the owner checks ID on delivery or pickup. An owner proposal can't add alcohol to an order without that confirmation. Migration 0012. | Business owner |
| 2026-11-04 | 9 | The kitchen is **kosher with a certificate and serves meat only**: every dish is meat or pareve (fish and desserts are pareve), **no dairy**, so meat and dairy can never meet in an order. Unmarked dishes are pareve. Meat with fish is allowed. The certifying body is an owner setting shown to customers (menu page, home page footer). Migration 0011. | Business owner |
| 2026-11-04 | 16 | LLM provider: **Anthropic Claude**, model Claude Sonnet 5.5 (`claude-sonnet-5-5`, balanced cost). Budget control: a per-customer limit of messages to the assistant in any 24 hours, default **30**, owner-editable (0 turns the assistant off). | Business owner |
| 2026-11-02 | 4 (rest) | Vegetarian and vegan guests are **separate** groups (a vegan is not also counted as vegetarian); vegetarian + vegan ≤ adults + children (migration 0006). | Business owner |
| 2026-11-02 | 14 | Catalog prices **include VAT**; no VAT is added. Each line = quantity × unit price rounded half-up to the agora; total = sum of the rounded lines. | Business owner |
| 2026-11-02 | 17 | ILS (₪) only, Hebrew number format. | Business owner |
| 2026-11-02 | 18 | Weight-priced dishes are priced and ordered per **kg**, in 0.5 kg steps. | Business owner |
| 2026-11-02 | 3 | Quantity recommendations: the owner sets per dish how many adults one unit serves (`serves_adults`); a child = **0.75** of an adult (owner setting); each dish counts only the guests who can eat it (vegan dish: all; vegetarian: all but vegans; other or unknown: all but vegetarians and vegans); round up to whole units / 0.5 kg; never below the dish minimum. Advice only. | Business owner |
| 2026-11-02 | 15 | Only the existing per-dish minimum quantity; no order-level or guest minimum. | Business owner |
| 2026-11-02 | 5 | Orders at least **3 days** before the event (owner setting `lead_days`); capacity is enforced **per time slot** (orders awaiting approval or approved count; empty capacity = unlimited). | Business owner |
| 2026-11-08 | 19 | Delivery to **any Israeli locality**: zone cities keep the zone fee; every other locality (CBS list) costs one owner-set default fee (`business_settings.default_delivery_fee`, empty = zone cities only). | Business owner |
| 2026-11-02 | 19 | Delivery zones are **lists of cities**, each with a fee; delivery only to listed cities. | Business owner |
| 2026-11-02 | 8 | Show allergens as contains / free / unknown exactly as entered, plus a fixed cross-contamination notice; no "may contain" level. | Business owner |
| 2026-11-02 | 7 | While awaiting approval the customer can withdraw the order back to draft, edit and resubmit; after approval, changes only by contacting the business. | Business owner |
| 2026-11-02 | 6 | The owner can propose a change to a submitted order; the customer approves or declines it (separate slice). | Business owner |
| 2026-11-02 | 13 | Email notifications to both sides: owner on new submissions, customer on approve / reject / owner proposal. | Business owner |
| 2026-11-02 | 2 | No payment or deposit in the app; the flow ends with an approved quote. | Business owner |
| 2026-11-02 | 4 | Vegetarian, vegan and restricted guests are counted **within** adults + children (each ≤ the total), enforced in the service and by a DB check (migration 0005). Vegan-within-vegetarian remains open. | Business owner |
| 2026-11-02 | 1 | Customers must create an account. Passwordless email login only: a 6-digit code sent by email (no password, no guest checkout, no phone OTP for now). Implemented with Supabase Auth (ADR 0005). | Business owner |
