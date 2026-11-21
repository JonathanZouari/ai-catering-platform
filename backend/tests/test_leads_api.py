from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core import auth
from app.core.config import Settings
from app.main import app
from app.repositories import leads as repo

client = TestClient(app)


def valid_lead(**overrides):
    lead = {
        "full_name": "דנה לוי",
        "phone": "050-1234567",
        "event_type": "יום הולדת",
        "guests": 40,
        "event_date": (date.today() + timedelta(days=30)).isoformat(),
        "budget_per_guest": 120,
        "consent": True,
        "dishes_viewed": 9,
        "minutes_on_site": 7.5,
        "visits": 2,
        "source": "instagram",
        "used_chat": True,
    }
    return {**lead, **overrides}


@pytest.fixture
def runtime_file(tmp_path, monkeypatch):
    path = tmp_path / "leads.jsonl"
    monkeypatch.setattr(repo, "RUNTIME_FILE", path)
    monkeypatch.setattr(repo.add_lead, "__defaults__", (path,))
    monkeypatch.setattr(repo.form_leads, "__defaults__", (path,))
    return path


@pytest.fixture
def supabase_on(monkeypatch):
    settings = Settings(supabase_url="https://x.supabase.co", supabase_publishable_key="pk")
    monkeypatch.setattr(auth, "get_settings", lambda: settings)


def as_user(monkeypatch, role):
    user = {"id": "u1", "app_metadata": {"role": role} if role else {}}
    monkeypatch.setattr(auth, "fetch_supabase_user", lambda token: user if token == "ok" else None)  # noqa: S105


def test_valid_lead_is_stored_without_returning_a_score(runtime_file):
    r = client.post("/api/leads", json=valid_lead())
    assert r.status_code == 201
    assert r.json() == {"ok": True}
    assert "דנה לוי" in runtime_file.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "bad",
    [
        {"phone": "12345"},
        {"consent": False},
        {"event_type": "חתונה בירח"},
        {"guests": 0},
        {"event_date": (date.today() - timedelta(days=1)).isoformat()},
        {"dishes_viewed": 10_000},
        {"full_name": "  "},
    ],
)
def test_invalid_lead_is_rejected(runtime_file, bad):
    assert client.post("/api/leads", json=valid_lead(**bad)).status_code == 422
    assert not runtime_file.exists()


def test_storage_cap(runtime_file, monkeypatch):
    monkeypatch.setattr(repo, "MAX_RUNTIME_BYTES", 10)
    runtime_file.write_text("x" * 10)
    assert client.post("/api/leads", json=valid_lead()).status_code == 503


def test_admin_list_needs_a_token(supabase_on):
    assert client.get("/api/admin/leads").status_code == 401


def test_admin_list_rejects_a_bad_token(supabase_on, monkeypatch):
    as_user(monkeypatch, "admin")
    r = client.get("/api/admin/leads", headers={"Authorization": "Bearer forged"})
    assert r.status_code == 401


def test_admin_list_rejects_a_customer(supabase_on, monkeypatch):
    as_user(monkeypatch, None)
    r = client.get("/api/admin/leads", headers={"Authorization": "Bearer ok"})
    assert r.status_code == 403


def test_admin_list_without_supabase_is_closed(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: Settings())
    with pytest.raises(HTTPException) as e:
        auth.require_admin("Bearer ok")
    assert e.value.status_code == 503


def test_admin_sees_scored_leads_sorted(runtime_file, supabase_on, monkeypatch):
    as_user(monkeypatch, "admin")
    client.post("/api/leads", json=valid_lead())
    r = client.get("/api/admin/leads", headers={"Authorization": "Bearer ok"})
    assert r.status_code == 200
    leads = r.json()
    assert len(leads) == 41  # 40 demo + 1 from the form
    probs = [lead["probability"] for lead in leads]
    assert probs == sorted(probs, reverse=True)
    assert all(0 < p < 1 for p in probs)
    form_lead = next(lead for lead in leads if not lead["is_demo"])
    assert form_lead["days_until_event"] == 30
    assert form_lead["is_hot"] == (form_lead["probability"] >= 0.1)
