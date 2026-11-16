import math
from datetime import UTC, date, datetime, timedelta

from app.core import clock
from app.ml import synthetic
from app.ml.train import LEAD_CLOSED_DAYS, label, train
from app.models.orders import Customer, Event, Order
from app.services import leads
from tests.conftest import AUTH

CREATED = datetime(2026, 11, 1, 9, tzinfo=UTC)


def add_lead(make_session, name="דנה", phone="050-0000000", status="draft", **event):
    """Insert an order with its customer and event; returns the order id."""
    details = {
        "event_type": "חתונה",
        "event_date": date(2026, 12, 1),
        "adults": 40,
        "children": 10,
        "vegan_guests": 5,
        **event,
    }
    with make_session() as db:
        customer = Customer(full_name=name, phone=phone, email=f"{name}@example.com")
        db.add(customer)
        db.flush()
        event_row = Event(customer_id=customer.id, **details)
        db.add(event_row)
        db.flush()
        order = Order(
            customer_id=customer.id,
            event_id=event_row.id,
            status=status,
            fulfillment_type="delivery",
            delivery_address="הרצל 1",
            requested_at=datetime(2026, 12, 1, 11, tzinfo=UTC),
            submitted_at=None if status == "draft" else CREATED,
            created_at=CREATED,
        )
        db.add(order)
        db.commit()
        return order.id


def test_features_describe_the_lead(make_session):
    order_id = add_lead(make_session)
    with make_session() as db:
        row = leads.features(db.get(Order, order_id))

    assert tuple(row) == leads.FEATURES
    assert row["guests"] == 50
    assert row["has_children"] == 1
    assert row["days_to_event"] == 30
    assert row["is_delivery"] == 1
    assert row["has_phone"] == 1
    assert row["dietary_share"] == 0.1
    assert row["type_wedding"] == 1
    assert row["type_brit"] == 0


def test_unknown_event_type_and_missing_phone(make_session):
    order_id = add_lead(make_session, phone=None, event_type="מסיבת גג")
    with make_session() as db:
        row = leads.features(db.get(Order, order_id))

    assert row["has_phone"] == 0
    assert not any(row[name] for name in leads.EVENT_TYPE_FEATURES.values())


def tiny_model(kind, coef, intercept):
    return {
        "chosen": kind,
        "features": ["x"],
        "mean": [1.0],
        "scale": [2.0],
        "models": {kind: {"coef": [coef], "intercept": intercept}},
    }


def test_logistic_score_is_a_sigmoid():
    # z = 0.5 + 2 * (3 - 1) / 2 = 2.5
    result = leads.score({"x": 3.0}, tiny_model("logistic", 2.0, 0.5))
    assert math.isclose(result, 1 / (1 + math.exp(-2.5)))


def test_linear_score_is_clipped_to_a_probability():
    assert leads.score({"x": 3.0}, tiny_model("linear", 2.0, 0.5)) == 1.0
    assert leads.score({"x": 3.0}, tiny_model("linear", -2.0, 0.5)) == 0.0
    assert math.isclose(leads.score({"x": 3.0}, tiny_model("linear", 0.2, 0.1)), 0.3)


def test_leads_require_token(client):
    assert client.get("/api/admin/leads").status_code == 401


def test_leads_list_only_open_drafts_sorted_by_score(client, make_session, monkeypatch):
    first = str(add_lead(make_session, name="א"))
    second = str(add_lead(make_session, name="ב", phone=None, event_type="ברית"))
    add_lead(make_session, name="ג", status="pending_approval")
    add_lead(make_session, name="ד", event_date=date(2026, 11, 14))  # event already passed
    monkeypatch.setattr(clock, "today", lambda: date(2026, 11, 15))

    body = client.get("/api/admin/leads", headers=AUTH).json()

    assert {lead["order_id"] for lead in body["leads"]} == {first, second}
    scores = [lead["score"] for lead in body["leads"]]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= value <= 1 for value in scores)
    assert body["model_source"] in ("synthetic", "db")
    lead = next(lead for lead in body["leads"] if lead["order_id"] == first)
    assert lead["customer_name"] == "א" and lead["guests"] == 50
    assert lead["phone"] == "050-0000000"


def test_committed_model_matches_features():
    leads.load_model.cache_clear()
    assert tuple(leads.load_model()["features"]) == leads.FEATURES


def test_training_learns_the_synthetic_rule():
    data, labels = synthetic.rows(2000)  # enough to learn the rule; keeps the test fast

    model = train(data, labels, "synthetic")

    assert tuple(model["features"]) == leads.FEATURES
    assert model["chosen"] in ("linear", "logistic")
    for kind in ("linear", "logistic"):
        assert model["metrics"][kind]["auc"] > 0.7, kind
        assert len(model["models"][kind]["coef"]) == len(leads.FEATURES)


def test_training_label(make_session):
    today = CREATED.date() + timedelta(days=LEAD_CLOSED_DAYS)
    bought = add_lead(make_session, name="א", status="approved")
    stale = add_lead(make_session, name="ב")
    with make_session() as db:
        assert label(db.get(Order, bought), today) == 1
        assert label(db.get(Order, stale), today) == 0
        # a fresh draft is still open, unless its event date has already passed
        assert label(db.get(Order, stale), today - timedelta(days=1)) is None
        assert label(db.get(Order, stale), date(2026, 12, 2)) == 0
