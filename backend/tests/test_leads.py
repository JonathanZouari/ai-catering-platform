import pytest
from sqlalchemy import text
from test_admin_orders import code, submitted
from test_orders import ADMIN, Shop

LEADS = f"{ADMIN}/leads"


@pytest.fixture
def shop(client, make_tenant):
    return Shop(client, make_tenant("leads-a"))


@pytest.fixture
def other_shop(client, make_tenant):
    return Shop(client, make_tenant("leads-b"))


def get(shop, path=""):
    return shop.client.get(f"{LEADS}{path}", headers=shop.headers)


def patch_stage(shop, lead_id, stage):
    url = f"{LEADS}/{lead_id}/stage"
    return shop.client.patch(url, json={"stage": stage}, headers=shop.headers)


def add_note(shop, lead_id, note):
    return shop.client.post(f"{LEADS}/{lead_id}/notes", json={"note": note}, headers=shop.headers)


def test_leads_need_login(client):
    assert client.get(LEADS).status_code == 401


def test_drafts_are_not_leads_but_submitted_orders_are(shop):
    shop.order()
    assert get(shop).json() == []

    submitted(shop)
    leads = get(shop).json()
    assert len(leads) == 1
    lead = leads[0]
    assert lead["stage"] == "new"
    assert 0 < float(lead["score"]) < 1
    assert lead["band"] in {"low", "medium", "high"}


def test_detail_has_reasons_unknowns_and_contact(shop):
    submitted(shop)
    lead_id = get(shop).json()[0]["id"]
    detail = get(shop, f"/{lead_id}").json()
    assert detail["phone"]
    assert isinstance(detail["reasons"], list)
    assert isinstance(detail["unknown"], list)
    assert detail["events"] == []


def test_stage_change_is_recorded_and_the_outcome_is_written_once(shop, session):
    submitted(shop)
    lead_id = get(shop).json()[0]["id"]

    assert patch_stage(shop, lead_id, "qualified").status_code == 200
    won = patch_stage(shop, lead_id, "won")
    assert won.status_code == 200
    assert [e["stage"] for e in won.json()["events"]] == ["won", "qualified"]

    # Changing a decided stage keeps the first outcome as it was.
    patch_stage(shop, lead_id, "lost")
    rows = session.execute(
        text("select outcome, features from lead_outcomes where lead_id = :id"),
        {"id": lead_id},
    ).all()
    assert [row.outcome for row in rows] == ["won"]
    assert "full_name" not in rows[0].features and "phone" not in rows[0].features


def test_same_stage_adds_no_event(shop):
    submitted(shop)
    lead_id = get(shop).json()[0]["id"]
    assert patch_stage(shop, lead_id, "new").json()["events"] == []


def test_notes(shop):
    submitted(shop)
    lead_id = get(shop).json()[0]["id"]
    response = add_note(shop, lead_id, "  חזרתי ללקוח  ")
    assert response.status_code == 201
    assert response.json()["events"][0]["note"] == "חזרתי ללקוח"
    assert add_note(shop, lead_id, "").status_code == 422


def test_stage_filter(shop):
    submitted(shop)
    lead_id = get(shop).json()[0]["id"]
    patch_stage(shop, lead_id, "won")
    assert len(get(shop, "?stage=won").json()) == 1
    assert get(shop, "?stage=new").json() == []


def test_input_cannot_name_a_caterer_or_an_unknown_stage(shop, other_shop):
    submitted(shop)
    lead_id = get(shop).json()[0]["id"]
    body = {"stage": "won", "caterer_id": str(other_shop.tenant.id)}
    response = shop.client.patch(f"{LEADS}/{lead_id}/stage", json=body, headers=shop.headers)
    assert response.status_code == 422
    assert patch_stage(shop, lead_id, "bogus").status_code == 422


def test_another_caterers_lead_is_a_404(shop, other_shop):
    submitted(shop)
    lead_id = get(shop).json()[0]["id"]

    assert get(other_shop).json() == []
    for response in (
        get(other_shop, f"/{lead_id}"),
        patch_stage(other_shop, lead_id, "won"),
        add_note(other_shop, lead_id, "x"),
    ):
        assert code(response) == (404, "not_found")
    assert get(shop, f"/{lead_id}").json()["stage"] == "new"


def test_database_rejects_a_lead_pointing_at_another_caterers_order(shop, other_shop, session):
    order = shop.order()  # a draft has no lead yet, so only the caterer link can fail
    with pytest.raises(Exception, match="foreign key"):
        session.execute(
            text(
                "insert into leads (caterer_id, order_id, score, score_version) "
                "values (:c, :o, 0.5, 'x')"
            ),
            {"c": other_shop.tenant.id, "o": order.data["id"]},
        )
    session.rollback()


@pytest.mark.parametrize("table", ["leads", "lead_events", "lead_outcomes"])
def test_rls_caterer_reads_only_its_own_lead_rows(shop, other_shop, engine, table):
    from test_rls import as_user, ids

    for each in (shop, other_shop):
        submitted(each)
        lead_id = get(each).json()[0]["id"]
        patch_stage(each, lead_id, "won")
        add_note(each, lead_id, "note")

    for each in (shop, other_shop):
        with as_user(engine, each.tenant.user_id) as connection:
            assert ids(connection, table) == {each.tenant.id}
    with as_user(engine, None) as connection:
        with pytest.raises(Exception, match="permission denied"):
            connection.execute(text(f"select 1 from {table}"))  # noqa: S608
