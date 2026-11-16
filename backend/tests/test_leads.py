from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api import leads as leads_api
from app.main import app
from app.services.lead_scoring import LeadService

AS_OF = date(2026, 11, 16)
COLUMNS = (
    "customer_id full_name email phone customer_city customer_created_at order_id "
    "order_created_at status event_type event_date total_guests fulfillment_type menu_kashrut total"
).split()


def row(
    customer_id,
    *,
    status="",
    city="תל אביב-יפו",
    email="a@b.c",
    created="2026-11-01T10:00:00",
    event_date="",
    total="0",
    event_type="יום הולדת",
    guests="30",
):
    ordered = bool(status)
    return {
        **dict.fromkeys(COLUMNS, ""),
        "customer_id": customer_id,
        "full_name": f"לקוח {customer_id}",
        "email": email,
        "phone": "050-0000000",
        "customer_city": city,
        "customer_created_at": created,
        "order_id": f"o-{customer_id}" if ordered else "",
        "order_created_at": "2026-10-01T10:00:00" if ordered else "",
        "status": status,
        "event_type": event_type if ordered else "",
        "event_date": event_date,
        "total_guests": guests if ordered else "",
        "fulfillment_type": "delivery" if ordered else "",
        "menu_kashrut": "meat" if ordered else "",
        "total": total,
    }


@pytest.fixture
def service():
    rows = [
        row(f"won{i}", status="approved", event_date="2026-09-01", total="5000") for i in range(8)
    ]
    rows += [
        row(f"lost{i}", status="rejected", event_date="2026-09-01", total="5000") for i in range(2)
    ]
    rows += [
        row("pending", status="pending_approval", event_date="2026-12-20", total="6000"),
        row("rejected", status="rejected", event_date="2026-12-20", total="6000"),
        row("past", status="draft", event_date="2026-10-01", total="6000"),
        row("prospect"),
    ]
    return LeadService(rows)


def by_id(leads):
    return {lead.customer_id: lead for lead in leads}


def test_only_customers_without_approved_orders_are_leads(service):
    ids = set(by_id(service.leads(AS_OF)))
    assert ids == {"pending", "rejected", "past", "prospect", *{f"lost{i}" for i in range(2)}}


def test_scoring_rules(service):
    leads = by_id(service.leads(AS_OF))
    assert leads["pending"].probability > leads["rejected"].probability
    assert leads["pending"].probability > leads["past"].probability
    assert leads["past"].days_to_event < 0
    assert leads["prospect"].kind == "prospect"
    assert 0 < leads["prospect"].probability < leads["pending"].probability


def test_leads_sorted_and_expected_revenue(service):
    leads = service.leads(AS_OF)
    assert [lead.probability for lead in leads] == sorted(
        (x.probability for x in leads), reverse=True
    )
    pending = by_id(leads)["pending"]
    assert pending.expected_revenue == pytest.approx(pending.probability * 6000)


def test_forecast_totals(service):
    forecast = service.forecast(AS_OF)
    assert forecast["total_leads"] == 6
    assert sum(t["count"] for t in forecast["tiers"].values()) == 6
    assert [m["month"] for m in forecast["by_event_month"]] == ["2026-12"]


@pytest.fixture
def client(service):
    app.dependency_overrides = {}
    leads_api.get_lead_service.cache_clear()
    original = leads_api.get_lead_service
    leads_api.get_lead_service = lambda: service
    yield TestClient(app)
    leads_api.get_lead_service = original


def test_api_endpoints(client):
    listing = client.get("/api/leads", params={"as_of": "2026-11-16", "kind": "open_order"}).json()
    assert listing["total"] == 5
    assert all(item["kind"] == "open_order" for item in listing["items"])
    assert (
        client.get("/api/leads/forecast", params={"as_of": "2026-11-16"}).json()["total_leads"] == 6
    )
    assert client.get("/api/leads/pending", params={"as_of": "2026-11-16"}).status_code == 200
    assert client.get("/api/leads/missing").status_code == 404


def test_leads_require_admin_token_outside_development(client, monkeypatch):
    from app.core.config import Settings

    def settings(token):
        return lambda: Settings(app_env="production", admin_api_token=token, _env_file=None)

    monkeypatch.setattr(leads_api, "get_settings", settings(None))
    assert client.get("/api/leads").status_code == 503  # no token configured: closed

    monkeypatch.setattr(leads_api, "get_settings", settings("s3cret"))
    assert client.get("/api/leads").status_code == 401
    assert client.get("/api/leads", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = client.get("/api/leads", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
