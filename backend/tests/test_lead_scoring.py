from app.services.lead_scoring import BASE, Features, band, score


def test_empty_features_give_the_base_rate_and_list_everything_unknown():
    result = score(Features())
    assert result.reasons == []
    assert 0.37 < result.probability < 0.38  # sigmoid(-0.5)
    assert "זמן עד האירוע" in result.unknown
    assert "כתובת אימייל" in result.unknown


def test_unknown_inputs_never_lower_the_score():
    known = score(Features(days_to_event=30)).probability
    empty = score(Features()).probability
    assert known > empty


def test_known_false_flags_are_not_unknown():
    result = score(Features(has_email=False))
    assert "כתובת אימייל" not in result.unknown


def test_soon_event_lowers_and_mid_range_event_raises():
    assert score(Features(days_to_event=1)).probability < score(Features()).probability
    assert score(Features(days_to_event=20)).probability > score(Features()).probability
    assert score(Features(days_to_event=400)).probability < score(Features()).probability


def test_rejected_proposals_count_only_without_an_accepted_one():
    rejected_only = score(Features(proposals_rejected=2)).probability
    both = score(Features(proposals_accepted=1, proposals_rejected=2)).probability
    assert rejected_only < score(Features()).probability < both


def test_best_case_stays_a_probability_and_reasons_are_ranked_and_capped():
    best = Features(
        days_to_event=20,
        guests=60,
        categories=4,
        chat_messages=5,
        proposals_accepted=1,
        has_email=True,
        delivery_resolved=True,
    )
    result = score(best)
    assert 0 < result.probability < 1
    assert len(result.reasons) == 5
    sizes = [abs(reason["points"]) for reason in result.reasons]
    assert sizes == sorted(sizes, reverse=True)


def test_features_hold_no_personal_data():
    assert set(Features().as_dict()) == {
        "days_to_event",
        "guests",
        "total",
        "categories",
        "chat_messages",
        "proposals_accepted",
        "proposals_rejected",
        "has_email",
        "delivery_resolved",
        "kashrut_acknowledged",
    }


def test_bands():
    assert (band(0.1), band(0.5), band(0.9)) == ("low", "medium", "high")
    assert BASE < 0
