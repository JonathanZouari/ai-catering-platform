# Lead data collection (request for the site)

Lead scoring (`backend/app/services/lead_scoring.py`, `/api/leads`, `/admin/leads.html`) can only
use what we know about a customer. Today that is city, email and sign-up date. On the existing
export these three predict **nothing** about whether a customer orders (logistic regression
AUC ≈ 0.48, i.e. random). The model needs behaviour data that exists *before* the order.

## What the site should capture when a customer arrives

Collected automatically where possible, so the customer is not asked more than necessary.

| Field | How to capture | Why it matters |
|---|---|---|
| `lead_source` | UTM parameters / `document.referrer`; "how did you hear about us?" (optional) on sign-up | Referrals convert very differently from paid ads |
| `first_contact_at` and `first_response_at` | Timestamp on lead creation; set when the owner first replies | Response time is one of the strongest predictors |
| `stated_budget` | Optional budget range on the event step | Serious leads state a budget |
| `event_date` (planned) at first contact | Already collected in the event step; store it on the lead too | Lead time (days ahead) changes conversion |
| `site_visits`, `interactions_count` | Count sessions and chat / form interactions per customer | Engagement |
| `requested_quote` | Flag when the customer asks for a quotation | Intent |
| `lost_reason` | Owner picks a reason when a quotation is rejected or a lead goes cold | Lets us tell model errors from external causes |

## Constraints

- **Privacy:** these are personal data. Show a consent notice and keep a deletion path
  (Israeli Privacy Protection Law). Do not log the data to third parties.
- **Only data known before the decision.** Do not add fields derived from the order itself
  (totals, order counts, lifetime value); they leak the answer and inflate the model.
- Store them on `customers` / a new `leads` table in Supabase, never in `localStorage` only.

## Status of the numbers in this repo

`backend/scripts/enrich_synthetic_data.py` generates **invented** values for these fields so
the training pipeline and dashboard can be demonstrated. The improvement they show (AUC ≈ 0.81)
is true by construction and is **not** evidence about real customers. Replace them with real data
as soon as the site collects it.
