# Random vs time-based split: comparison

Each scenario is repeated 10 times. Each one trains on 5000 fresh 2025 leads
and scores on 5000 fresh 2026 leads that no split has seen. Values are means over
repeats. **Error** = |estimate - actual future score|: smaller means the method predicts
real-world performance more honestly. *CV closer in* counts the repeats where this
method's CV estimate beat the other method's. Higher is better for ROC-AUC and PR-AUC,
lower is better for Brier and LogLoss.

## Scenario 1: stable market (no drift)

| Metric | Method | Holdout estimate | CV estimate | Actual on future | Mean holdout error | Mean CV error | CV closer in |
|---|---|---|---|---|---|---|---|
| ROC-AUC | random | 0.767 | 0.756 | 0.753 | 0.019 | 0.011 | 6/10 |
| ROC-AUC | time | 0.751 | 0.745 | 0.753 | 0.012 | 0.015 | 4/10 |
| PR-AUC | random | 0.486 | 0.474 | 0.466 | 0.032 | 0.022 | 3/10 |
| PR-AUC | time | 0.481 | 0.457 | 0.465 | 0.038 | 0.017 | 7/10 |
| Brier | random | 0.139 | 0.142 | 0.140 | 0.004 | 0.003 | 7/10 |
| Brier | time | 0.145 | 0.145 | 0.140 | 0.006 | 0.005 | 3/10 |
| LogLoss | random | 0.435 | 0.443 | 0.439 | 0.013 | 0.009 | 6/10 |
| LogLoss | time | 0.452 | 0.454 | 0.440 | 0.015 | 0.015 | 4/10 |

## Scenario 2: market changes over time (drift)

| Metric | Method | Holdout estimate | CV estimate | Actual on future | Mean holdout error | Mean CV error | CV closer in |
|---|---|---|---|---|---|---|---|
| ROC-AUC | random | 0.758 | 0.749 | 0.737 | 0.023 | 0.014 | 3/10 |
| ROC-AUC | time | 0.742 | 0.736 | 0.733 | 0.013 | 0.011 | 7/10 |
| PR-AUC | random | 0.429 | 0.422 | 0.336 | 0.093 | 0.085 | 1/10 |
| PR-AUC | time | 0.391 | 0.395 | 0.330 | 0.067 | 0.066 | 9/10 |
| Brier | random | 0.127 | 0.129 | 0.109 | 0.018 | 0.020 | 5/10 |
| Brier | time | 0.120 | 0.131 | 0.110 | 0.010 | 0.020 | 5/10 |
| LogLoss | random | 0.404 | 0.411 | 0.360 | 0.044 | 0.051 | 8/10 |
| LogLoss | time | 0.390 | 0.417 | 0.364 | 0.025 | 0.053 | 2/10 |
