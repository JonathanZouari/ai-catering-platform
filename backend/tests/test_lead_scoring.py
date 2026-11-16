from math import exp

import pytest

from app.services.lead_scoring import features, load_model, purchase_probability
from scripts.sample_leads import SEED_FILE, generate, to_sql
from scripts.train_lead_model import train

LEAD = {
    "guests": 50,
    "lead_days": 30,
    "budget_per_guest": 200,
    "is_returning": False,
    "event_type": "יום הולדת",
    "source": "google",
}


def test_probability_is_the_logistic_of_the_weighted_sum():
    model = {
        "intercept": -1.0,
        "coefficients": {"guests": 0.01, "is_returning": 2.0, "source=google": 0.5},
    }
    # -1 + 0.01 * 50 + 0.5 = 0; features without a coefficient add nothing.
    assert purchase_probability(LEAD, model) == pytest.approx(0.5)
    returning = {**LEAD, "is_returning": True}
    assert purchase_probability(returning, model) == pytest.approx(1 / (1 + exp(-2.0)))


def test_unseen_category_adds_nothing_to_the_score():
    model = {"intercept": 0.3, "coefficients": {"source=google": 5.0}}
    unseen = {**LEAD, "source": "billboard"}
    assert purchase_probability(unseen, model) == pytest.approx(1 / (1 + exp(-0.3)))


@pytest.mark.parametrize("guests, expected", [(10**9, 1.0), (-(10**9), 0.0)])
def test_extreme_score_does_not_overflow(guests, expected):
    model = {"intercept": 0.0, "coefficients": {"guests": 1.0}}
    assert purchase_probability({**LEAD, "guests": guests}, model) == expected


def test_shipped_model_scores_every_sample_lead():
    coefficients = load_model()["coefficients"]
    for lead in generate():
        assert set(features(lead)) <= set(coefficients)
        assert 0 < purchase_probability(lead) < 1


def test_sample_leads_are_reproducible_and_match_the_seed_file():
    assert generate() == generate()
    assert SEED_FILE.read_text(encoding="utf-8") == to_sql(generate())


def test_training_learns_the_sample_rule_and_matches_the_shipped_model():
    model = train(generate())
    shipped = load_model()
    assert set(model["coefficients"]) == set(shipped["coefficients"])
    # 0.5 is a coin flip; the sample rule is strong enough to clear 0.65 on the holdout.
    assert model["holdout_auc"] > 0.65
    # Signs the sample rule fixes: returning customers and referrals buy more often.
    assert model["coefficients"]["is_returning"] > 0
    assert model["coefficients"]["source=referral"] > model["coefficients"]["source=instagram"]
