import importlib.util
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.ml import features, scoring, train

GENERATOR = Path(__file__).resolve().parents[2] / "supabase" / "tools" / "gen_leads_history.py"


@pytest.fixture(scope="module")
def synthetic_csv(tmp_path_factory) -> Path:
    spec = importlib.util.spec_from_file_location("gen_leads_history", GENERATOR)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    rows, _ = gen.generate(300)
    path = tmp_path_factory.mktemp("ml") / "leads.csv"
    gen.write_training_csv(rows, path, datetime(2026, 11, 16, tzinfo=UTC))
    return path


@pytest.fixture(scope="module")
def frame(synthetic_csv) -> pd.DataFrame:
    return features.load_training_frame(str(synthetic_csv))


@pytest.fixture(scope="module")
def artifact(frame) -> dict:
    return train.train(frame, data_source="synthetic")


def test_no_forbidden_feature():
    assert not set(features.FEATURES) & features.FORBIDDEN


def test_time_split_never_trains_on_the_future(frame):
    train_df, test_df = train.time_split(frame)
    assert train_df[features.TIME_COLUMN].max() <= test_df[features.TIME_COLUMN].min()
    assert len(train_df) + len(test_df) == len(frame)


def test_build_features_shape_and_missing_budget(frame):
    x = features.build_features(frame)
    assert list(x.columns) == features.FEATURES
    assert (x["missing_budget"] == x["budget_estimate"].isna().astype(int)).all()
    assert x["source"].notna().all()


def test_trained_model_beats_the_constant_baseline(artifact):
    m = artifact["metrics"]
    chosen = m["test"][m["chosen_model"]]
    assert chosen["roc_auc"] > 0.6
    assert chosen["brier"] < m["test"]["baseline"]["brier"]
    assert m["version"].startswith("synthetic-")
    assert "SYNTHETIC" in m["warning"]


def test_artifact_roundtrip_and_scoring(artifact, frame, tmp_path):
    model_path, metrics_path = train.save(artifact, tmp_path)
    assert json.loads(metrics_path.read_text(encoding="utf-8"))["version"] == artifact["version"]
    loaded = scoring.load_artifact(model_path)
    scores = scoring.score_rows(loaded, frame.head(10))
    assert len(scores) == 10
    for s in scores:
        assert 0 <= s.probability <= 1
        assert s.label == ("won" if s.probability >= loaded["threshold"] else "lost")
        assert s.model_version == artifact["version"]


def test_lead_to_row_matches_the_training_view_columns():
    row = features.lead_to_row(
        {
            "source": "whatsapp",
            "utm_medium": None,
            "approx_guests": 40,
            "budget_estimate": 500_000,
            "event_date": date(2026, 12, 1),
            "email": None,
            "message": "שלום",
            "consent_marketing": False,
        },
        "חתונה",
        datetime(2026, 11, 16, 9, 0, tzinfo=UTC),
    )
    assert set(row) == set(features.RAW_COLUMNS)
    assert row["budget_per_guest"] == 12_500
    assert row["lead_time_days"] == 15
    assert row["has_email"] is False and row["has_message"] is True
    score = scoring.score_rows(
        {"model": _FixedModel(0.8), "threshold": 0.5, "version": "t"}, pd.DataFrame([row])
    )[0]
    assert (score.probability, score.label) == (0.8, "won")


def test_lead_without_budget_or_date_scores_without_error(artifact):
    row = features.lead_to_row({"source": "landing_form"}, None, datetime(2026, 11, 16, tzinfo=UTC))
    (score,) = scoring.score_rows(artifact, pd.DataFrame([row]))
    assert 0 <= score.probability <= 1


def test_refuses_to_train_on_too_little_data(frame):
    with pytest.raises(train.NotEnoughDataError):
        train.train(frame.head(40), data_source="synthetic")


def test_artifact_with_other_features_is_rejected(artifact, tmp_path):
    import joblib

    bad = {**artifact, "features": ["source"]}
    path = tmp_path / "bad.joblib"
    joblib.dump(bad, path)
    with pytest.raises(ValueError, match="feature list"):
        scoring.load_artifact(path)


class _FixedModel:
    def __init__(self, p: float):
        self.p = p

    def predict_proba(self, x):
        import numpy as np

        return np.array([[1 - self.p, self.p]] * len(x))
