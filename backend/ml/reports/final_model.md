# Lead purchase model: final training report

Trained 2026-11-16 on synthetic data. Logistic regression, time-based.

## Protocol

- Development: 4000 leads, 2025-01-01T06:58 to 2025-10-18T20:48. Tuned C over [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0] with TimeSeriesSplit(5), scored by PR-AUC.
- Test period: 1000 leads, 2025-10-18T20:48 to 2025-12-31T23:05. Scored once.
- Chosen C = 0.1 (CV PR-AUC 0.477).
- Final model refit on all leads with that C: `models/lead_model.joblib`.

## Test-period scores (the numbers to report)

| Metric | Model | Baseline (always predict the base rate) |
|---|---|---|
| ROC-AUC | 0.736 | 0.500 |
| PR-AUC | 0.416 | 0.212 |
| Brier | 0.149 | 0.167 |
| LogLoss | 0.460 | - |

Top 20% of leads by score buy at 42.5% (vs 21.2% overall) and hold 40% of all buyers.

## Calibration on the test period

| Score group (low to high) | Leads | Predicted rate | Actual rate |
|---|---|---|---|
| 1 | 200 | 4.6% | 5.5% |
| 2 | 200 | 10.4% | 7.0% |
| 3 | 200 | 17.3% | 24.0% |
| 4 | 200 | 27.1% | 27.0% |
| 5 | 200 | 49.2% | 42.5% |

## Strongest features (final model)

Coefficients are log-odds per one standard deviation (numeric) or vs. the other
categories (one-hot). Positive raises the purchase probability.

| Feature | Coefficient |
|---|---|
| `cat__traffic_source_referral` | +0.480 |
| `cat__event_type_בר או בת מצווה` | +0.387 |
| `num__has_phone` | +0.361 |
| `cat__days_bucket_normal` | +0.356 |
| `cat__days_bucket_far` | -0.352 |
| `num__log_time_on_site` | +0.337 |
| `num__returning_visitor` | +0.310 |
| `cat__browser_firefox` | +0.273 |
| `cat__event_type_אחר` | -0.269 |
| `cat__venue_type_synagogue` | -0.266 |
| `num__bot_like_form` | -0.265 |
| `cat__browser_language_en` | -0.263 |
| `num__pages_viewed` | +0.251 |
| `cat__traffic_source_facebook` | -0.243 |
| `cat__browser_language_missing` | +0.237 |
| `cat__venue_type_office` | +0.231 |
| `cat__event_type_חגיגה פרטית` | -0.229 |
| `cat__device_tablet` | +0.227 |
| `cat__traffic_source_organic` | -0.217 |
| `num__has_draft` | +0.214 |
