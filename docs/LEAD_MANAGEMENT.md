# Lead management

Status: proposal (branch `feat/lead-management`). Nothing here is wired into the customer flow yet.

## 1. Goal and boundaries

The owner needs to see who asked about an event, follow up, and know where to spend time.
A **lead** is a person who showed interest but has no approved order yet.

- Admin-only (RLS `private.is_admin()`). Customers never see leads or scores.
- The score is **advisory**. It never changes price, quantity, order status or a quotation
  (ADR-0003). It only sorts and labels the owner's worklist.
- Scoring code lives in `services/`; any LLM involvement only drafts text, it does not score.

## 2. Funnel

`new → contacted → quoted → negotiating → won | lost`

- `won` requires `orders.id` (a lead converts when its order is `approved`).
- `lost` requires `lost_reason` (free text first, enum later once real reasons are known).
- Existing orders map to the funnel: `draft` ≈ new/contacted, `pending_approval` = quoted,
  `approved` = won, `rejected` = lost.

## 3. Where leads come from

| Source | Capture |
| --- | --- |
| Website form / event step abandoned | Create lead when the customer leaves name + phone, before an order exists |
| AI chat | Lead on first contact detail; `chat_started` activity |
| WhatsApp, phone, referral, Instagram, Google | Owner adds manually (admin form), source recorded |

Do not create a lead for every anonymous visitor. Capture only on explicit contact details
(privacy, Israeli privacy law amendment 13: store the minimum, state the purpose).

## 4. Data model

See `supabase/migrations/20261118090000_leads.sql`: `leads`, `lead_activities` (append-only),
`lead_scores` (one row per scoring run with the exact feature vector).

## 5. Scoring

Score at defined **moments**, never "now" with future information. A model trained on features
that only exist after the outcome (for example "quote accepted") is useless.

| Moment | Features available |
| --- | --- |
| At creation | source, event type, guests, days until event, budget, repeat customer, has phone/email |
| After first response | + response time, weekend/holiday date |
| After quote | + quote amount, quote/budget ratio, touches so far, days since quote |

Models compared in `backend/ml/` (see section 7): logistic regression (baseline, readable
coefficients), random forest, histogram gradient boosting. Metrics: ROC-AUC, PR-AUC, Brier
score, calibration, and lift in the top decile. Calibrated probabilities matter more than AUC,
because the owner reads "62%" as a number.

## 6. Honest limits

- Synthetic data is generated from a formula chosen by us. Model quality on it only proves the
  pipeline works. It says nothing about real conversion.
- A single catering business gets maybe tens of leads a month. Expect 100 to 300 labeled
  leads in the first year. Use the simple model first, require at least ~200 resolved leads
  before showing any score in the UI, and show the score as a band (high/medium/low), not a
  percent, until calibration is checked on real data.
- Scores can encode bias (for example, by neighborhood or phone prefix). Do not use
  protected or proxy attributes as features.

## 7. Synthetic data and model comparison

- `backend/ml/synthetic.py`: seeded generator, writes CSV. Conversion probability is a known
  logistic function of the features plus noise, so the true signal is recoverable.
- `backend/ml/compare_models.py`: trains the three models, prints a metrics table.
- Optional dependency group `ml` (numpy, scikit-learn). Not needed to run the app.

```bash
cd backend
uv sync --extra ml
uv run python -m ml.synthetic --n 3000 --seed 7 --out ml/out/leads.csv
uv run python -m ml.compare_models --data ml/out/leads.csv
```

## 8. Rollout

1. Migration + admin list/detail screen (no scoring).
2. Capture from website form and chat.
3. Activity log and stage changes.
4. Offline scoring with the best simple model, shown as a band behind a flag.
5. Re-train monthly on real resolved leads; compare to the baseline before switching.
