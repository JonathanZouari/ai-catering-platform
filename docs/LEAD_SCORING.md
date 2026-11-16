# Lead scoring

The owner's **Leads** screen (`/admin/leads/`) lists customers who left their details and started an order but have not submitted it, with the model's estimate of the chance that they will.

> **Status: trained on synthetic data.** The business has too few orders to train on, so the current model was fitted to 50,000 made-up leads (`backend/app/ml/synthetic.py`). The scores show that the pipeline works; they say nothing about real customers until the model is retrained on real orders. The screen shows a notice while this is the case.

## Definitions

| Term | Meaning |
|---|---|
| Lead | An order in status `draft` whose event date has not passed |
| Purchased (target = 1) | `submitted_at` is set, whatever the owner decided afterwards |
| Did not purchase (target = 0) | A draft older than 14 days (`LEAD_CLOSED_DAYS`), or whose event date has passed |
| Still open | Any other draft. Left out of training |

## Inputs

Only what is known when the customer leaves their details. Items and totals are left out because they change afterwards, and a submitted order would show its final basket.

`guests`, `has_children`, `days_to_event` (event date minus the order's creation date), `is_delivery`, `has_phone`, `dietary_share` (vegetarian + vegan + restricted guests over all guests), and one 0/1 column per event type offered on the event form. Any other event type is the baseline.

`features()` in `backend/app/services/leads.py` builds this row for both training and scoring, so the two cannot drift apart. The event-type list repeats `EVENT_TYPES` in `frontend/js/event.js`; change both together and retrain.

## Models

`backend/app/ml/train.py` fits two models on the same 80/20 split:

- **Linear regression** on the 0/1 target. Its raw output can fall outside 0–1, so it is clipped.
- **Logistic regression**, whose output is always a probability.

It reports ROC AUC (ranking quality), Brier score (how close the probabilities are to the outcomes; lower is better) and the share of raw linear predictions outside 0–1, then keeps the model with the lower Brier score.

The result is `backend/app/ml/lead_model.json`: scaling values and coefficients for both models, the chosen one, the metrics, the data source and the training time. The server scores with plain arithmetic from this file, so scikit-learn is a dev dependency only and the Docker image is unchanged.

## Retraining

From `backend/`:

```bash
uv run python -m app.ml.train --source synthetic   # made-up data
uv run python -m app.ml.train --source db          # real orders from DATABASE_URL
```

`--source db` refuses to train on fewer than 200 closed leads or when only one outcome is present. Commit the updated `lead_model.json`; the screen's notice disappears once the source is `db`.

## Limits

- Orders store only their current state, so `has_phone` and the event details are read as they are now, not as they were when the lead was created.
- Showing draft customers' phone and email to the owner makes it easy to contact them. Whether that contact needs the customer's consent is a business and legal decision.
