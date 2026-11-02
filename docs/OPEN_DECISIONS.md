# Open Business Decisions

These must be answered by the business before the dependent features are built. Engineering will not invent answers. Unrelated infrastructure work continues meanwhile.

Format: **Question** · *Why it matters* · **Blocks**

| # | Topic | Question | Why it matters | Blocks |
|---|---|---|---|---|
| 9 | Kashrut certification | Which certification(s)? Shown per dish or business-wide? Mixing meat & dairy dishes in one order allowed? | Affects data model and validation | Phase 2 dish fields, Phase 3 conflict checks |
| 10 | Disposable serving equipment | Are utensils/disposables orderable? Priced how? | Could be catalog items or separate | Out of MVP until decided |
| 11 | Alcohol | Offered at all? Age verification? | Legal implications | Out of MVP until decided |
| 12 | Interface languages | ~~Hebrew only, English only, or both? RTL required?~~ **Decided 2026-11-01: Hebrew, RTL** (chosen with the "Table Journal" design). English is not planned. | Layout, copy, and AI response language | Resolved (AI response language follows: Hebrew) |
| 16 | LLM provider | Which model provider (e.g., Anthropic Claude) and budget? | API keys, tool-calling format, cost | Phase 4 |
| 20 | Brand | Business name, logo, colors, fonts. **Decided 2026-11-01: name "Yummai", colors and fonts per the "Table Journal" direction (UX_UI_SPEC §2).** Still open: logo, real food photography | Visual identity | Logo and photos only (Unsplash placeholders until then) |

## Decision log

When a decision is made, record it here and move the row out of the table above.

| Date | # | Decision | Decided by |
|---|---|---|---|
| 2026-11-02 | 4 (rest) | Vegetarian and vegan guests are **separate** groups (a vegan is not also counted as vegetarian); vegetarian + vegan ≤ adults + children (migration 0006). | Business owner |
| 2026-11-02 | 14 | Catalog prices **include VAT**; no VAT is added. Each line = quantity × unit price rounded half-up to the agora; total = sum of the rounded lines. | Business owner |
| 2026-11-02 | 17 | ILS (₪) only, Hebrew number format. | Business owner |
| 2026-11-02 | 18 | Weight-priced dishes are priced and ordered per **kg**, in 0.5 kg steps. | Business owner |
| 2026-11-02 | 3 | Quantity recommendations: the owner sets per dish how many adults one unit serves (`serves_adults`); a child = **0.75** of an adult (owner setting); each dish counts only the guests who can eat it (vegan dish: all; vegetarian: all but vegans; other or unknown: all but vegetarians and vegans); round up to whole units / 0.5 kg; never below the dish minimum. Advice only. | Business owner |
| 2026-11-02 | 15 | Only the existing per-dish minimum quantity; no order-level or guest minimum. | Business owner |
| 2026-11-02 | 5 | Orders at least **3 days** before the event (owner setting `lead_days`); capacity is enforced **per time slot** (orders awaiting approval or approved count; empty capacity = unlimited). | Business owner |
| 2026-11-02 | 19 | Delivery zones are **lists of cities**, each with a fee; delivery only to listed cities. | Business owner |
| 2026-11-02 | 8 | Show allergens as contains / free / unknown exactly as entered, plus a fixed cross-contamination notice; no "may contain" level. | Business owner |
| 2026-11-02 | 7 | While awaiting approval the customer can withdraw the order back to draft, edit and resubmit; after approval, changes only by contacting the business. | Business owner |
| 2026-11-02 | 6 | The owner can propose a change to a submitted order; the customer approves or declines it (separate slice). | Business owner |
| 2026-11-02 | 13 | Email notifications to both sides: owner on new submissions, customer on approve / reject / owner proposal. | Business owner |
| 2026-11-02 | 2 | No payment or deposit in the app; the flow ends with an approved quote. | Business owner |
| 2026-11-02 | 4 | Vegetarian, vegan and restricted guests are counted **within** adults + children (each ≤ the total), enforced in the service and by a DB check (migration 0005). Vegan-within-vegetarian remains open. | Business owner |
| 2026-11-02 | 1 | Customers must create an account. Passwordless email login only: a 6-digit code sent by email (no password, no guest checkout, no phone OTP for now). Implemented with Supabase Auth (ADR 0005). | Business owner |
