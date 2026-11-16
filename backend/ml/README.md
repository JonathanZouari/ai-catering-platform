# Lead scoring: synthetic data

Synthetic leads for prototyping a **logistic regression** model that predicts whether a lead
becomes a purchase. **The data is fake.** Labels come from a hidden logistic model
(`TRUE_EFFECTS` in `generate_leads.py`), so a trained model can be checked against known
coefficients. Categorical values mirror the PLACEHOLDER values in
`frontend/js/customer/mock-backend.js`.

```bash
cd backend
uv run python -m ml.generate_leads --rows 5000 --seed 42   # writes ml/data/leads_synthetic.csv
```

The checked-in `data/leads_synthetic.csv` uses 5000 rows and seed 42, with a purchase rate of about 21% and 50 columns.
Rows are sorted by `created_at`, so split train and test **by time**, not at random.

## Fields

| Field | Source | Meaning |
|---|---|---|
| `lead_id`, `created_at` | system | Lead id and submission time (ISO, local) |
| `full_name`, `phone`, `email` | contact form (invented) | Fake identity. Emails are `@example.com`. **Not model features** |
| `preferred_contact` | contact form | `whatsapp`/`phone`/`email` |
| `customer_type`, `company_name` | contact form | `private` or `business`. Company only for business |
| `age_group` | optional field | Empty = skipped. **No true effect**: keep it out of the score for fairness |
| `residence_city` | contact form | Where the customer lives (may differ from the event city) |
| `is_past_customer`, `past_orders`, `past_spend_ils` | CRM | Order history before this lead |
| `marketing_consent`, `requested_callback` | contact form | Checkboxes |
| `budget_per_guest_ils` | optional field | Stated budget, empty = not given. Under 70 hurts conversion |
| `kashrut`, `venue_type` | form | `none`/`kosher`/`mehadrin`; `home`/`hall`/`office`/`synagogue`/`outdoor` |
| `event_type` | form | One of `EVENT_TYPES` |
| `event_date`, `days_until_event` | form | Event date, days from submission to event |
| `slot`, `fulfillment`, `city` | form | Time slot, `pickup`/`delivery`, delivery city (empty for pickup) |
| `adults`, `children` | form | Guest counts |
| `vegetarian`, `vegan`, `restricted` | form | Guests with each dietary restriction |
| `notes_length` | form | Characters in the free-text notes (0 = none) |
| `has_phone`, `has_email` | form (proposed) | Contact details left. The current form has no contact step |
| `device`, `browser`, `os` | user agent, coarse | `browser` and `os` have **no** true effect (noise check) |
| `browser_language` | `navigator.language` | `he`/`en`/`ru`/`ar`/`other`, empty = not reported |
| `visit_hour`, `visit_weekday` | session | Hour 0-23, weekday 0 = Sunday |
| `traffic_source` | UTM / referrer | `google_ads`, `organic`, `instagram`, `facebook`, `referral`, `direct` |
| `time_on_site_sec`, `pages_viewed`, `viewed_menu` | session | Engagement before submitting |
| `form_fill_sec` | session | Time to fill the form. Under 15s looks like a bot |
| `returning_visitor`, `previous_visits` | first-party cookie | Prior visits |
| `used_ai_chat`, `ai_messages` | app | AI assistant use |
| `dishes_in_draft`, `draft_total_ils` | app | Draft order at submission time |
| `purchased` | label | 1 = the lead became an approved order |

## Modelling notes

- Use only what is known at submission time. Owner follow-up calls, quotation status and
  similar later events leak the label.
- Suggested transforms: `log1p` for guests, times and money. Cyclic or bucketed `visit_hour`.
  Bucket `days_until_event` (short, normal and far all matter). One-hot encode categoricals.
- Evaluate with ROC-AUC and PR-AUC plus a calibration curve or Brier score. The score is shown to
  the owner as a probability.

## Privacy (before collecting real data)

The session fields require a consent notice (Israeli Privacy Protection Law, Amendment 13).
Store only the derived values listed above, never the raw IP address or user-agent string.
The score is for the owner only and must never affect price (ADR-0003).
