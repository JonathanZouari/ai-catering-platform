import math
from datetime import UTC, datetime

import pytest

from app.services.lead_scoring import (
    FEATURES,
    LeadModel,
    auc,
    brier,
    fit_logistic,
    lead_features,
    prior_contacts,
)
from scripts import train_lead_model
from scripts.score_leads import score_rows
from scripts.supabase_rest import SupabaseRest
from scripts.synthetic_leads import TRUE_EFFECTS, generate

BASE = {"created_at": "2026-11-01T09:00:00+00:00", "source": "landing_form"}


def feats(**overrides):
    return lead_features({**BASE, **overrides})


# ---- Features


def test_minimal_lead_has_only_unknowns():
    f = feats()
    assert set(f) == set(FEATURES)
    assert all(v == 0.0 for v in f.values())


def test_missing_created_at_is_an_error():
    with pytest.raises(ValueError):
        lead_features({"source": "manual"})


def test_accepts_iso_z_and_datetime_objects():
    a = lead_features({**BASE, "created_at": "2026-11-01T09:00:00Z", "event_date": "2026-11-03"})
    b = lead_features({**BASE, "created_at": datetime(2026, 11, 1, 9, tzinfo=UTC)})
    assert a["short_notice"] == 1.0
    assert b["date_known"] == 0.0


@pytest.mark.parametrize(
    ("event_date", "short", "passed"),
    [("2026-11-07", 1.0, 0.0), ("2026-11-08", 0.0, 0.0), ("2026-10-31", 0.0, 1.0)],
)
def test_short_notice_and_passed_boundaries(event_date, short, passed):
    f = feats(event_date=event_date)
    assert (f["date_known"], f["short_notice"], f["date_passed"]) == (1.0, short, passed)


@pytest.mark.parametrize(("guests", "known"), [(0, 0.0), (-5, 0.0), ("12", 0.0), (None, 0.0)])
def test_invalid_guest_counts_are_unknown(guests, known):
    assert feats(guest_count=guests)["guests_known"] == known


def test_guest_count_is_clipped_and_large_flagged():
    f = feats(guest_count=1_000_000)
    assert f["guests_log"] == pytest.approx(math.log1p(5000))
    assert f["large_event"] == 1.0
    assert feats(guest_count=150)["large_event"] == 0.0


def test_blank_strings_do_not_count_and_long_text_is_fine():
    f = feats(email="   ", message="\n\t")
    assert f["has_email"] == 0.0 and f["has_message"] == 0.0
    assert feats(message="א" * 1000)["has_message"] == 1.0


def test_sources_and_customer_flags():
    assert feats(source="ai_chat")["src_ai_chat"] == 1.0
    assert feats(source="manual")["src_manual"] == 1.0
    assert feats(customer_id="abc")["returning_customer"] == 1.0
    assert lead_features(BASE, prior_same_phone=2)["repeat_contact"] == 1.0


def test_prior_contacts_counts_earlier_same_phone_only():
    leads = [
        {"id": "b", "phone": "+972500000001", "created_at": "2026-11-02"},
        {"id": "a", "phone": "+972500000001", "created_at": "2026-11-01"},
        {"id": "c", "phone": "+972500000002", "created_at": "2026-11-03"},
    ]
    assert prior_contacts(leads) == {"a": 0, "b": 1, "c": 0}


# ---- Math


def test_auc_and_brier_known_values():
    assert auc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]) == 1.0
    assert auc([0.1, 0.2, 0.8, 0.9], [1, 1, 0, 0]) == 0.0
    assert auc([0.5, 0.5], [1, 0]) == 0.5
    assert brier([1.0, 0.0], [1, 0]) == 0.0
    with pytest.raises(ValueError):
        auc([0.3], [1])


def test_fit_rejects_bad_input():
    with pytest.raises(ValueError):
        fit_logistic([feats()], [1])  # one class only
    with pytest.raises(ValueError):
        fit_logistic([feats(), feats()], [1])  # length mismatch
    with pytest.raises(ValueError):
        fit_logistic([], [])


# ---- Training on synthetic history


@pytest.fixture(scope="module")
def synthetic_model():
    features, labels = train_lead_model.load_synthetic(600, 7)
    return train_lead_model.train(features, labels, synthetic=True)


def test_training_recovers_strong_planted_effects(synthetic_model):
    for name, true in TRUE_EFFECTS.items():
        if abs(true) >= 0.8:
            learned = synthetic_model.coefficients[name]
            assert math.copysign(1, learned) == math.copysign(1, true), name
            assert abs(learned - true) < 0.6, (name, learned, true)
    assert abs(synthetic_model.coefficients["guests_log"]) < 0.3  # planted as no effect


def test_training_quality_and_flags(synthetic_model):
    assert synthetic_model.metrics["holdout_auc"] > 0.65
    assert synthetic_model.trained_on_synthetic is True
    assert synthetic_model.version.endswith("synthetic")


def test_training_is_deterministic(synthetic_model):
    features, labels = train_lead_model.load_synthetic(600, 7)
    again = train_lead_model.train(features, labels, synthetic=True)
    assert again.coefficients == synthetic_model.coefficients


def test_synthetic_generator_has_no_personal_data():
    rows, _, _ = generate(50, 1)
    assert not any("full_name" in r or "phone" in r for r in rows)


def test_probabilities_stay_in_bounds_and_reasons_are_hebrew(synthetic_model):
    worst = feats(event_date="2026-10-01", guest_count=5000)
    best = feats(
        source="ai_chat",
        email="a@b.co",
        customer_id="c",
        event_date="2026-12-15",
        guest_count=40,
        message="שלום",
    )
    p_worst, p_best = synthetic_model.probability(worst), synthetic_model.probability(best)
    assert 0.0 < p_worst < p_best < 1.0
    reasons = synthetic_model.reasons(best)
    assert 1 <= len(reasons) <= 3
    assert all(r["direction"] in ("up", "down") and r["label"] for r in reasons)
    assert [abs(r["impact"]) for r in reasons] == sorted(
        (abs(r["impact"]) for r in reasons), reverse=True
    )


def test_saved_model_round_trips_and_rejects_mismatch(synthetic_model, tmp_path):
    path = tmp_path / "m.json"
    synthetic_model.save(path)
    assert LeadModel.load(path) == synthetic_model
    path.write_text(path.read_text("utf-8").replace('"has_message"', '"other"'), "utf-8")
    with pytest.raises(ValueError, match="retrain"):
        LeadModel.load(path)


def test_committed_model_is_loadable_and_marked_synthetic():
    model = LeadModel.load()
    assert model.trained_on_synthetic is True


# ---- Real-data guard and scoring


def test_real_training_refuses_too_few_outcomes(monkeypatch):
    leads = [
        {**BASE, "id": i, "phone": f"+9725000000{i:02d}", "status": s}
        for i, s in enumerate(["converted"] * 3 + ["lost"] * 4 + ["new"] * 13)
    ]
    monkeypatch.setattr(SupabaseRest, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(SupabaseRest, "select", lambda self, *a, **k: leads)
    with pytest.raises(SystemExit, match="Not enough real outcomes"):
        train_lead_model.load_real()


def test_score_rows_only_open_leads(synthetic_model):
    leads = [
        {**BASE, "id": i, "phone": "+972500000001", "status": s}
        for i, s in enumerate(["new", "contacted", "converted", "lost"])
    ]
    rows = score_rows(leads, synthetic_model)
    assert [r["lead_id"] for r in rows] == [0, 1]
    assert all(0 <= r["probability"] <= 1 and r["trained_on_synthetic"] for r in rows)


def test_rest_client_requires_https():
    with pytest.raises(ValueError):
        SupabaseRest(url="http://example.com", key="k")


def test_reason_labels_match_the_lead(synthetic_model):
    small = synthetic_model.reasons(feats(guest_count=20, event_date="2026-12-01"), top=12)
    labels = {r["feature"]: r["label"] for r in small}
    assert labels.get("large_event", "עד 150 אורחים") == "עד 150 אורחים"
    assert labels.get("returning_customer", "לקוח חדש") == "לקוח חדש"
    unknown = {r["feature"] for r in synthetic_model.reasons(feats(), top=12)}
    assert unknown.isdisjoint({"large_event", "guests_log", "short_notice", "date_passed"})
