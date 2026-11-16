import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.main import app

LEADS = "/api/admin/leads"
MISSING_ID = "00000000-0000-4000-8000-000000000000"


@pytest.mark.parametrize("app_env", ["production", "staging", "Production"])
def test_leads_api_is_hidden_outside_development(app_env):
    # The guard answers before the database is touched, so no database is needed here.
    app.dependency_overrides[get_settings] = lambda: Settings(app_env=app_env)
    app.dependency_overrides[get_db] = lambda: None
    try:
        client = TestClient(app)
        assert client.get(LEADS).status_code == 404
        assert client.patch(f"{LEADS}/{MISSING_ID}", json={"status": "won"}).status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_unknown_status_is_rejected_before_the_database():
    app.dependency_overrides[get_db] = lambda: None
    try:
        response = TestClient(app).patch(f"{LEADS}/{MISSING_ID}", json={"status": "deleted"})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_seed_loads_the_sample_leads(engine):
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT COUNT(*) FROM leads")) == 400


def test_open_leads_come_first_ordered_by_probability(client):
    leads = client.get(LEADS).json()
    assert len(leads) == 400
    open_leads = [lead for lead in leads if lead["status"] in ("new", "contacted", "quoted")]
    assert leads[: len(open_leads)] == open_leads
    probabilities = [lead["purchase_probability"] for lead in open_leads]
    assert all(0 < p < 1 for p in probabilities)
    assert probabilities == sorted(probabilities, reverse=True)


def test_closed_leads_have_no_probability(client):
    closed = [lead for lead in client.get(LEADS).json() if lead["status"] in ("won", "lost")]
    assert closed
    assert {lead["purchase_probability"] for lead in closed} == {None}


def test_budget_is_an_exact_string(client):
    assert client.get(LEADS).json()[0]["budget_per_guest"].endswith(".00")


def test_status_change_is_saved(client):
    lead = client.get(LEADS).json()[0]
    assert lead["status"] != "won"

    response = client.patch(f"{LEADS}/{lead['id']}", json={"status": "won"})
    assert response.status_code == 200
    assert response.json()["status"] == "won"
    assert response.json()["purchase_probability"] is None

    saved = next(item for item in client.get(LEADS).json() if item["id"] == lead["id"])
    assert saved["status"] == "won"


def test_reopening_a_closed_lead_brings_its_probability_back(client):
    closed = next(lead for lead in client.get(LEADS).json() if lead["status"] == "lost")
    reopened = client.patch(f"{LEADS}/{closed['id']}", json={"status": "contacted"}).json()
    assert 0 < reopened["purchase_probability"] < 1


def test_status_change_on_a_missing_lead_returns_404(client):
    assert client.patch(f"{LEADS}/{MISSING_ID}", json={"status": "won"}).status_code == 404


def test_malformed_lead_id_is_rejected(client):
    assert client.patch(f"{LEADS}/not-a-uuid", json={"status": "won"}).status_code == 422
