from datetime import date

import pytest

pytest.importorskip("sklearn")  # only installed with `uv sync --group ml`

import pandas as pd  # noqa: E402

from ml.compare_splits import features  # noqa: E402
from ml.generate_leads import generate  # noqa: E402
from ml.train_model import C_GRID, report, train  # noqa: E402


def test_train_beats_baseline_and_scores_new_leads():
    r = train(pd.DataFrame(generate(2000, seed=3)))
    assert r["best_c"] in C_GRID
    assert r["test"]["roc_auc"] > 0.6
    assert r["test"]["average_precision"] > r["base_rate_test"]
    assert "Test-period scores" in report(r)

    new = pd.DataFrame(generate(50, seed=4, start=date(2026, 1, 1)))
    p = r["model"].predict_proba(features(new))[:, 1]
    assert ((p > 0) & (p < 1)).all()
