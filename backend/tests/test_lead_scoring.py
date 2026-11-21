import csv

import pytest

from app.services.lead_scoring import MODEL_PATH, is_hot, load_model, purchase_probability

sklearn = pytest.importorskip("sklearn")


def _rows(name):
    with (MODEL_PATH.parent / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_scoring_matches_scikit_learn():
    """The exported numbers must give the same probability as the trained Pipeline."""
    from scripts.train_lead_model import build_pipeline, load_history, to_matrix

    rows, y = load_history()
    pipe = build_pipeline().fit(to_matrix(rows), y)
    from scripts.train_lead_model import export_model

    model = export_model(pipe, threshold=None)
    open_rows = _rows("leads_open.csv")
    expected = pipe.predict_proba(to_matrix(open_rows))[:, 1]
    for row, p in zip(open_rows, expected, strict=True):
        assert purchase_probability(row, model) == pytest.approx(p, abs=1e-9)


def test_more_engagement_raises_probability():
    base = _rows("leads_open.csv")[0]
    engaged = {**base, "dishes_viewed": 30, "visits": 5, "used_chat": 1}
    cold = {**base, "dishes_viewed": 0, "visits": 1, "used_chat": 0}
    assert purchase_probability(engaged) > purchase_probability(cold)


def test_unknown_category_is_ignored_not_an_error():
    lead = {**_rows("leads_open.csv")[0], "source": "tiktok"}
    assert 0 < purchase_probability(lead) < 1


def test_threshold():
    model = {**load_model(), "threshold": 0.3}
    assert is_hot(0.31, model) is True
    assert is_hot(0.29, model) is False
    assert is_hot(0.9, {**model, "threshold": None}) is None
