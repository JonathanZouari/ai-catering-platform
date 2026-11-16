import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.lead_scoring import WebsiteInquiry, score_demo

ROOT = Path(__file__).resolve().parents[2]


def test_portable_model_matches_training_predictions():
    data = json.loads((ROOT / "frontend/demo/leads.json").read_text("utf-8"))
    assert data["synthetic_only"] is True
    for row in data["leads"]:
        inquiry = WebsiteInquiry(**{key: row[key] for key in WebsiteInquiry.model_fields})
        result = score_demo(inquiry)
        assert result["demo_probability"] == pytest.approx(row["demo_probability"], abs=1e-12)
        assert result["demo_class"] == row["demo_class"]
        assert result["synthetic_only"] is True
        assert row["email"].endswith("@example.invalid")
        assert "converted_within_30_days" not in row


def test_training_split_and_feature_leakage():
    rows = json.loads((ROOT / "docs/demo/leads-training-synthetic.json").read_text("utf-8"))
    assert len(rows) == len({r["id"] for r in rows}) == 1200
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    assert len(train) == 900
    assert len(test) == 300
    for split in (train, test):
        assert {r["converted_within_30_days"] for r in split} == {0, 1}
    model = json.loads((ROOT / "backend/app/models/lead_demo_logistic.json").read_text("utf-8"))
    assert model["features"] == [
        "guest_count",
        "days_until_event",
        "budget_per_guest",
        "date_provided",
        "budget_provided",
    ]
    assert model["metrics"]["brier_score"] < model["metrics"]["baseline_brier_score"]


@pytest.mark.parametrize(
    "values",
    [
        {"guest_count": -1},
        {"guest_count": True},
        {"guest_count": 500},
        {"guest_count": 20, "budget_per_guest": float("nan")},
        {"guest_count": 20, "days_until_event": -2},
        {"guest_count": 20, "converted_within_30_days": 1},
    ],
)
def test_invalid_or_outcome_features_rejected(values):
    with pytest.raises(ValidationError):
        WebsiteInquiry(**values)


def test_missing_optional_features_score_without_inventing_values():
    result = score_demo(WebsiteInquiry(guest_count=20))
    assert 0 < result["demo_probability"] < 1
    assert result["synthetic_only"] is True
