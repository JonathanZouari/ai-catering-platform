from datetime import date

import pytest

pytest.importorskip("sklearn")  # only installed with `uv sync --group ml`

import pandas as pd  # noqa: E402

from ml.compare_splits import evaluate, features  # noqa: E402
from ml.generate_leads import generate  # noqa: E402


def test_evaluate_scores_both_methods():
    past = pd.DataFrame(generate(1500, seed=1))
    future = pd.DataFrame(generate(800, seed=2, start=date(2026, 1, 1)))
    assert not features(past).isna().any().any()

    results = evaluate(past, future)
    for method in ("random", "time"):
        for part in ("holdout", "cv_mean", "future"):
            assert 0.5 < results[method][part]["roc_auc"] <= 1.0
